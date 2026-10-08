import json
import logging
from typing import List, Optional, Set, TypedDict
from types import SimpleNamespace
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


from app.config.setting import settings
from app.services.agent_service import AgentService
from app.services.embedding_service import EmbeddingService
from app.vector_db.chroma_client import ChromaClient
from app.prompts.db_rag import (
    get_query_expansion_prompt,
    get_db_rag_query_expansion_persona,
    get_table_selection_prompt,
    get_db_rag_table_selection_persona,
)
from app.dependencies.vector_store import get_collection_by_name
from app.utils.table_docs_loader import load_table_docs_markdown
from app.utils.access_table_mapper import filter_tables_by_access

logger = logging.getLogger(__name__)


class TableSchemaResult(TypedDict):
    selected_tables: List[str]
    schema_markdown: str


class DBRagRetrievalService:
    """
    Service responsible for vector-searching available table documentation
    and optionally using an LLM to select the most relevant tables.
    """

    def __init__(
        self,
        chroma_client: ChromaClient,
        embedding_service: EmbeddingService,
        agent_service: AgentService,
    ):
        self.embedding_service = embedding_service
        self.agent_service = agent_service

    async def get_relevant_schemas(
        self,
        user_message: str,
        feature_id: int,
        use_llm_table_selection: bool = settings.DB_RAG_USE_LLM_TABLE_SELECTION,
        accessible_tables: Optional[Set[str]] = None,
    ) -> TableSchemaResult:
        """
        Retrieves table documentation chunks from ChromaDB and optionally
        filters them via an LLM to find the minimal required set of schemas.

        Args:
            user_message: Raw user query.
            feature_id: The ID of the feature (unused here but kept for signature parity).
            use_llm_table_selection: Whether to ask the LLM to filter the retrieved tables.

        Returns:
            TableSchemaResult dict with selected table names and concatenated schema markdown.
        """
        collection_name = "database_retrieval_docs"

        try:
            collection = get_collection_by_name(collection_name)
            if not collection:
                logger.warning(
                    f"Collection {collection_name} not found. Cannot retrieve DB schemas."
                )
                return {"selected_tables": [], "schema_markdown": ""}
        except Exception as e:
            logger.error(f"Error accessing collection {collection_name}: {e}")
            return {"selected_tables": [], "schema_markdown": ""}

        # Step A: Query Expansion
        # Rephrase the raw user query into a plain-English technical search phrase
        # to improve vector retrieval precision before hitting ChromaDB.
        try:
            all_docs = get_collection_by_name(collection_name)
            all_table_names = (
                ", ".join(
                    sorted(
                        set(
                            m["table_name"]
                            for m in (
                                all_docs.get(where={"active": "true"}).get("metadatas")
                                or []
                            )
                        )
                    )
                )
                if all_docs
                else ""
            )
        except Exception:
            all_table_names = ""

        try:
            expansion_prompt = get_query_expansion_prompt(user_message, all_table_names)
            expansion_persona = SimpleNamespace(**get_db_rag_query_expansion_persona())
            search_query = await self.agent_service.generate_async(
                prompt=expansion_prompt,
                persona=expansion_persona,
            )
            search_query = search_query.strip()
            logger.info(f"Query expanded to: {search_query[:120]}...")
        except Exception as e:
            logger.warning(
                f"Query expansion failed, falling back to raw user message. Error: {e}"
            )
            search_query = user_message

        # Step B: Fused Hybrid Search (RRF: Vector + Lexical)
        try:
            # 1. Fetch all active docs in collection to build dynamic lexical index
            raw_col = collection.get(
                include=["documents", "metadatas"], where={"active": "true"}
            )
            raw_docs = raw_col.get("documents", [])
            raw_metas = raw_col.get("metadatas", [])
            raw_ids = raw_col.get("ids", [])

            if not raw_docs:
                logger.warning(
                    "No active documents found in database schema collection."
                )
                return {"selected_tables": [], "schema_markdown": ""}

            id_to_meta = {raw_ids[i]: raw_metas[i] for i in range(len(raw_ids))}
            id_to_content = {raw_ids[i]: raw_docs[i] for i in range(len(raw_ids))}

            # 2. Parallel Vector Search (get top 100 to allow robust fusion)
            query_embedding = self.embedding_service.embed_query(search_query)
            vec_res = collection.query(
                query_embeddings=[query_embedding],
                n_results=100,
                where={"active": "true"},
            )
            v_ids = vec_res.get("ids", [[]])[0] if vec_res else []
            vector_ranks = {d_id: r + 1 for r, d_id in enumerate(v_ids)}

            # 3. Parallel Lexical (TF-IDF) Search
            vectorizer = TfidfVectorizer(
                stop_words="english", analyzer="word", ngram_range=(1, 2)
            )
            matrix = vectorizer.fit_transform(raw_docs)
            query_vec = vectorizer.transform([search_query])
            lex_sim = (matrix * query_vec.T).toarray().flatten()
            lex_order = np.argsort(-lex_sim)
            lex_ranks = {raw_ids[idx]: r + 1 for r, idx in enumerate(lex_order)}

            # 4. Reciprocal Rank Fusion (RRF) Blending
            alpha = settings.DB_RAG_RRF_ALPHA
            rrf_k = 60

            fusion_scores = {}
            all_doc_ids = set(vector_ranks.keys()).union(set(lex_ranks.keys()))
            for doc_id in all_doc_ids:
                v_rank = vector_ranks.get(doc_id, 9999)
                l_rank = lex_ranks.get(doc_id, 9999)
                score = (alpha * (1.0 / (rrf_k + v_rank))) + (
                    (1.0 - alpha) * (1.0 / (rrf_k + l_rank))
                )
                fusion_scores[doc_id] = score

            sorted_doc_ids = [
                x[0]
                for x in sorted(fusion_scores.items(), key=lambda x: x[1], reverse=True)
            ]

            # Resolve to ordered unique table names
            unified_tables = []
            seen = set()
            for d_id in sorted_doc_ids:
                m = id_to_meta.get(d_id)
                if m and m.get("table_name"):
                    tbl = m.get("table_name")
                    if tbl not in seen:
                        seen.add(tbl)
                        unified_tables.append(tbl)

            # 5. Retrieve natural Top-K tables first
            top_k = settings.DB_RAG_TOP_K or 20
            final_retrieved_tables = []
            for t in unified_tables:
                if len(final_retrieved_tables) >= top_k:
                    break
                final_retrieved_tables.append(t)

            # 6. Origin static pinning: add 'stores' if it wasn't in the Top-K naturally
            target_pinned = "stores"
            if target_pinned not in final_retrieved_tables:
                # Verify the table physically exists in the collection before forcing
                if any(m.get("table_name") == target_pinned for m in raw_metas):
                    final_retrieved_tables.append(target_pinned)
                    logger.info(
                        f"Static Pinning Activated: Forced '{target_pinned}' into retrieval pool."
                    )

            # 7. Construct candidate payloads for intermediate selection stage
            retrieved_candidates = []
            for t in final_retrieved_tables:
                # Pull best matching content block
                matching_ids = [
                    d_id
                    for d_id in sorted_doc_ids
                    if id_to_meta.get(d_id, {}).get("table_name") == t
                ]
                if matching_ids:
                    retrieved_candidates.append(
                        {
                            "table_name": t,
                            "content": id_to_content.get(matching_ids[0], ""),
                        }
                    )
                else:
                    # Handle fallback retrieval for pinned tables that missed search
                    for r_id, r_meta in id_to_meta.items():
                        if r_meta.get("table_name") == t:
                            retrieved_candidates.append(
                                {
                                    "table_name": t,
                                    "content": id_to_content.get(r_id, ""),
                                }
                            )
                            break

            all_candidate_names = list(final_retrieved_tables)
            logger.info(
                f"Hybrid retrieval gathered {len(all_candidate_names)} table candidates."
            )

        except Exception as e:
            logger.error(f"Failed running hybrid Fused RRF Search: {e}")
            return {"selected_tables": [], "schema_markdown": ""}

        if not retrieved_candidates:
            logger.info("No table candidates resolved through hybrid search.")
            return {"selected_tables": [], "schema_markdown": ""}

        # Step C: LLM Selection (Optional)
        selected_tables = []
        if use_llm_table_selection:
            # Format summaries block
            summaries_block = "\n\n".join(
                [
                    f"### Table: {c['table_name']}\n{c['content']}"
                    for c in retrieved_candidates
                ]
            )

            prompt = get_table_selection_prompt(user_message, summaries_block)
            persona = SimpleNamespace(**get_db_rag_table_selection_persona())

            try:
                response_text = await self.agent_service.generate_async(
                    prompt=prompt,
                    persona=persona,
                )

                cleaned = response_text.strip()
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:]
                elif cleaned.startswith("```"):
                    cleaned = cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]

                parsed = json.loads(cleaned.strip())
                llm_tables = parsed.get("tables", [])

                # Filter against hallucinated names (case-insensitive for robustness)
                lower_candidates = {name.lower(): name for name in all_candidate_names}
                selected_tables = []
                for t in llm_tables:
                    if t.lower() in lower_candidates:
                        selected_tables.append(lower_candidates[t.lower()])

                logger.info(f"LLM table selection resolved to: {selected_tables}")

            except Exception as e:
                logger.error(
                    f"LLM table selection failed, falling back to all retreived. Error: {e}"
                )
                selected_tables = all_candidate_names
        else:
            selected_tables = all_candidate_names

        # Pinning critical context tables (only when user has access to them)
        pinned_tables = ["stores", "categories", "vending"]
        for p in filter_tables_by_access(pinned_tables, accessible_tables):
            if p not in selected_tables:
                selected_tables.append(p)

        if not selected_tables:
            return {"selected_tables": [], "schema_markdown": ""}

        # Step D: Load full table-docs from disk (## Columns, FKs) for SQL generation.
        # Chroma holds retrieval-docs only — optimized for search, not column whitelists.
        max_schema_tables = settings.DB_RAG_SQL_MAX_SCHEMA_TABLES or len(
            selected_tables
        )
        tables_for_sql = selected_tables[:max_schema_tables]

        # Strip tables the user is not permitted to see before loading schemas.
        tables_for_sql = filter_tables_by_access(tables_for_sql, accessible_tables)
        if len(selected_tables) > len(tables_for_sql):
            logger.info(
                "Loading table-docs for %d/%d selected tables (DB_RAG_SQL_MAX_SCHEMA_TABLES=%d)",
                len(tables_for_sql),
                len(selected_tables),
                max_schema_tables,
            )
        schema_md, loaded_from_disk = load_table_docs_markdown(tables_for_sql)

        if not schema_md.strip():
            logger.warning(
                "No table-docs loaded from disk; falling back to Chroma retrieval snippets"
            )
            try:
                full_schema_results = collection.get(
                    where={
                        "$and": [
                            {"active": "true"},
                            {"table_name": {"$in": selected_tables}},
                        ]
                    }
                )
                schema_docs = full_schema_results.get("documents", [])
                schema_md = "\n\n".join([str(doc) for doc in schema_docs if doc])
            except Exception as e:
                logger.error(f"Error fetching retrieval docs from Chroma: {e}")
                chosen_texts = [
                    c["content"]
                    for c in retrieved_candidates
                    if c["table_name"] in selected_tables
                ]
                schema_md = "\n\n".join(chosen_texts)
        elif len(loaded_from_disk) < len(tables_for_sql):
            missing = set(tables_for_sql) - set(loaded_from_disk)
            logger.warning("Table-docs missing on disk for: %s", sorted(missing))

        return {
            "selected_tables": selected_tables,
            "schema_markdown": schema_md,
        }
