from typing import Dict, Any, Optional, List
import logging

from chromadb import Collection
from app.config.setting import settings
from app.repositories.feature_classrooms import FeatureClassroomRepository
from app.repositories.classroom_item_assignments import (
    ClassroomItemAssignmentRepository,
)

logger = logging.getLogger(__name__)
VECTOR_STORE_DISTANCE_SPACE = settings.VECTOR_STORE_DISTANCE_SPACE


class RAGService:
    """
    RAG Service - Retrieval Augmented Generation (Retrieval Only)

    Retrieves relevant chunks from:
      1. The feature's own collection  (feature_{feature_id})
      2. Every classroom-item collection reachable from the feature via:
         feature --(collections)--> classroom --(classroom_item_assignments)--> item
         Each item has its own vector collection  (item_{ClassroomItem.id})

    Results from all collections are merged and re-ranked by relevance
    before being returned to the caller.
    """

    def __init__(
        self,
        chroma_client=None,
        embedding_service=None,
        feature_classroom_repository: Optional[FeatureClassroomRepository] = None,
        item_assignment_repository: Optional[
            ClassroomItemAssignmentRepository
        ] = None,
    ):
        self.chroma_client = chroma_client
        self.embedding_service = embedding_service
        self.feature_classroom_repo = feature_classroom_repository
        self.item_assignment_repo = item_assignment_repository

    def retrieve(
        self,
        query: str,
        feature_id: int,
        top_k: int = 5,
        include_sources: bool = True,
        similarity_threshold: float = settings.RAG_SIMILARITY_THRESHOLD,
    ) -> Dict[str, Any]:
        if not self.embedding_service:
            raise RuntimeError("EmbeddingService is not configured")

        try:
            query_embedding = self.embedding_service.embed_query(query)
        except Exception as exc:
            logger.exception("Failed to embed query for retrieval")
            raise RuntimeError("Failed to embed query for retrieval") from exc

        if not query_embedding:
            return self._empty_result()

        # Build the list of collection names to search:
        # always start with the feature's own direct-document collection.
        collection_names: List[str] = [f"feature_{feature_id}"]

        if (
            self.feature_classroom_repo is not None
            and self.item_assignment_repo is not None
        ):
            classrooms = self.feature_classroom_repo.get_classrooms_for_feature(
                feature_id
            )
            seen_item_ids: set = set()
            for classroom in classrooms:
                items = self.item_assignment_repo.get_items_for_classroom(
                    classroom.id
                )
                for item in items:
                    if item.id in seen_item_ids:
                        continue
                    seen_item_ids.add(item.id)
                    collection_names.append(f"item_{item.id}")

        # Query every collection and accumulate raw (doc, metadata, distance) tuples.
        raw_hits: List[tuple] = []
        for name in collection_names:
            try:
                collection = self._get_collection(name)
            except RuntimeError:
                # Collection may not exist yet (e.g. no documents uploaded).
                logger.debug("Skipping missing/unavailable collection: %s", name)
                continue

            embedding_dim = len(query_embedding)
            self._ensure_collection_embedding_metadata(collection, embedding_dim)

            try:
                results = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=top_k,
                    include=["documents", "metadatas", "distances"],
                    where={"active": "true"},
                )
            except Exception as exc:
                logger.exception("Vector search failed for collection %s", name)
                continue

            docs = results.get("documents", [[]])[0]
            metas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0]
            raw_hits.extend(zip(docs, metas, distances))

        if not raw_hits:
            return self._empty_result()

        # Re-rank all hits globally by distance (ascending = more similar).
        raw_hits.sort(key=lambda t: t[2])

        # Re-pack into the shape _format_results expects.
        merged = {
            "documents": [[h[0] for h in raw_hits]],
            "metadatas": [[h[1] for h in raw_hits]],
            "distances": [[h[2] for h in raw_hits]],
        }
        return self._format_results(merged, include_sources, similarity_threshold)

    def _get_collection(self, collection_name: str) -> Collection:
        """Get a ChromaDB collection by its exact name."""
        if not self.chroma_client:
            raise RuntimeError("Chroma client is not configured")

        try:
            collection = self.chroma_client.client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": VECTOR_STORE_DISTANCE_SPACE},
            )
            self._ensure_collection_distance_space(collection)
            return collection
        except Exception as exc:
            logger.exception(
                "Failed to access collection '%s'", collection_name
            )
            raise RuntimeError("Failed to access vector store collection") from exc

    def _ensure_collection_distance_space(self, collection: Collection) -> None:
        metadata = getattr(collection, "metadata", None)
        if not isinstance(metadata, dict):
            metadata = {}

        space = metadata.get("hnsw:space")
        if space != VECTOR_STORE_DISTANCE_SPACE:
            raise RuntimeError(
                "Vector store collection distance space mismatch. "
                f"Expected '{VECTOR_STORE_DISTANCE_SPACE}', got '{space}'. "
                "Please delete and reindex the collection."
            )

    def _ensure_collection_embedding_metadata(
        self, collection: Collection, embedding_dim: int
    ) -> None:
        if embedding_dim <= 0:
            raise RuntimeError("Invalid embedding dimension for collection")

        if not self.embedding_service:
            raise RuntimeError("EmbeddingService is not configured")

        expected = self.embedding_service.get_embedding_signature()
        expected["embedding_dim"] = str(embedding_dim)

        existing = getattr(collection, "metadata", None)
        if not isinstance(existing, dict):
            existing = {}

        mismatches = []
        for key, expected_value in expected.items():
            existing_value = existing.get(key)
            if existing_value is None:
                continue
            if str(existing_value) != str(expected_value):
                mismatches.append(f"{key}={existing_value} expected={expected_value}")

        if mismatches:
            raise RuntimeError(
                "Embedding configuration mismatch. Reindex the collection. "
                + "; ".join(mismatches)
            )

        if any(key not in existing for key in expected):
            if hasattr(collection, "modify"):
                try:
                    collection.modify(metadata={**existing, **expected})
                except Exception:
                    pass

    def _format_results(
        self,
        results: Dict[str, Any],
        include_sources: bool,
        similarity_threshold: float,
    ) -> Dict[str, Any]:
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        formatted_docs = []
        sources = []
        seen_sources = set()

        for doc, metadata, distance in zip(documents, metadatas, distances):
            relevance_score = 1 - distance if distance else 1.0

            if relevance_score < similarity_threshold:
                continue

            formatted_docs.append(
                {
                    "content": doc,
                    "metadata": metadata,
                    "relevance_score": relevance_score,
                    "rank": len(formatted_docs) + 1,
                }
            )

            if include_sources and metadata:
                document_id = metadata.get("document_id")
                chunk_index = metadata.get("chunk_index")
                table_id = metadata.get("table_id")
                row_start = metadata.get("row_start")
                row_end = metadata.get("row_end")

                source_key = (document_id, chunk_index, table_id, row_start, row_end)

                if source_key not in seen_sources:
                    seen_sources.add(source_key)
                    sources.append(
                        {
                            "document_id": document_id,
                            "file_id": metadata.get("file_id"),
                            "filename": metadata.get("filename"),
                            "file_type": metadata.get("file_type"),
                            "chunk_type": metadata.get("chunk_type"),
                            "chunk_index": chunk_index,
                            "table_id": table_id,
                            "row_start": row_start,
                            "row_end": row_end,
                            "section_path": metadata.get("section_path"),
                            "page": metadata.get("page"),
                            "page_label": metadata.get("page_label"),
                        }
                    )

        markdown = self._format_as_markdown(formatted_docs)

        return {
            "documents": [doc["content"] for doc in formatted_docs],
            "metadata": [doc["metadata"] for doc in formatted_docs],
            "sources": sources,
            "formatted": markdown,
            "count": len(formatted_docs),
        }

    def _format_as_markdown(self, formatted_docs: List[Dict]) -> str:
        if not formatted_docs:
            return "No relevant documents found."

        markdown_parts = ["## Retrieved Documents\n"]

        for doc in formatted_docs:
            content = doc["content"]
            metadata = doc["metadata"]
            score = doc["relevance_score"]

            markdown_parts.append(
                f"### Document {doc['rank']} (Relevance: {score:.2f})"
            )

            if metadata:
                filename = metadata.get("filename", "Unknown")
                markdown_parts.append(f"**Source:** {filename}")
                section_path = metadata.get("section_path")
                if section_path:
                    markdown_parts.append(f"**Section:** {section_path}")

            markdown_parts.append(f"\n{content}\n")
            markdown_parts.append("---\n")

        return "\n".join(markdown_parts)

    def _empty_result(self) -> Dict[str, Any]:
        return {
            "documents": [],
            "metadata": [],
            "sources": [],
            "formatted": "No relevant documents found.",
            "count": 0,
        }

    async def retrieve_async(
        self,
        query: str,
        feature_id: int,
        top_k: int = 5,
        include_sources: bool = True,
        similarity_threshold: float = settings.RAG_SIMILARITY_THRESHOLD,
    ) -> Dict[str, Any]:
        return self.retrieve(
            query, feature_id, top_k, include_sources, similarity_threshold
        )
