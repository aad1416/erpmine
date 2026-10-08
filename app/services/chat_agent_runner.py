from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, List, Optional

from agents import Agent, Runner, RunContextWrapper, function_tool

from app.config.setting import settings
from app.prompts.chat_agent import build_agent_instructions

if TYPE_CHECKING:
    from app.services.database_query_tool_service import DatabaseQueryToolService
    from app.services.document_retrieval_tool_service import DocumentRetrievalToolService

logger = logging.getLogger(__name__)


def _merge_sources(existing: List[dict], new_sources: List[dict]) -> None:
    seen = {(s.get("document_id"), s.get("chunk_index")) for s in existing}
    for s in new_sources:
        key = (s.get("document_id"), s.get("chunk_index"))
        if key not in seen:
            seen.add(key)
            existing.append(s)


@dataclass
class ChatToolContext:
    feature_id: int
    rag_top_k: int
    store_id: Optional[str]

    document_retrieval_tool_service: "DocumentRetrievalToolService"
    database_query_tool_service: Optional["DatabaseQueryToolService"]

    sources: List[dict] = field(default_factory=list)
    db_queries_audit: List[dict] = field(default_factory=list)
    user_accesses: List[str] = field(default_factory=list)


@function_tool
async def retrieve_documents(
    ctx: RunContextWrapper[ChatToolContext], query: str
) -> str:
    """Search uploaded documentation tied to this feature. Use when the user needs docs or policy text not in chat history. query — concise search phrase from the user's question."""

    ctx_obj = ctx.context
    result = await ctx_obj.document_retrieval_tool_service.retrieve(
        query=query,
        feature_id=ctx_obj.feature_id,
        top_k=ctx_obj.rag_top_k,
    )
    _merge_sources(ctx_obj.sources, result.sources)
    return result.content


@function_tool
async def query_database(ctx: RunContextWrapper[ChatToolContext], question: str) -> str:
    """Run read-only SQL against the Lyndom ERP (schema retrieval, SQL generation, execution). Use when the user needs transactional or numeric ERP data. Returns JSON per intent with row previews or errors."""

    ctx_obj = ctx.context
    if not ctx_obj.database_query_tool_service:
        return "DB RAG services are not available."

    result = await ctx_obj.database_query_tool_service.query(
        question=question,
        feature_id=ctx_obj.feature_id,
        store_id=ctx_obj.store_id,
        user_accesses=ctx_obj.user_accesses,
    )
    ctx_obj.db_queries_audit.extend(result.audit)
    return result.content


class ChatAgentRunner:
    """Thin wrapper around OpenAI Agents SDK for feature chat."""

    async def run(
        self,
        *,
        persona_prompt_text: str,
        model_name: str,
        run_input: str,
        ctx: ChatToolContext,
        use_rag: bool,
        use_db_request: bool,
    ) -> tuple[str, List[dict], List[dict]]:
        use_db_tool = use_db_request and settings.DB_RAG_ENABLED
        if use_db_request and not settings.DB_RAG_ENABLED:
            logger.warning(
                "use_db=true but DB_RAG_ENABLED=false; DB tool omitted for this turn"
            )

        instructions = build_agent_instructions(
            persona_prompt_text, use_rag=use_rag, use_db=bool(use_db_tool)
        )

        tools: List[Any] = []
        if use_rag:
            tools.append(retrieve_documents)
        if use_db_tool:
            tools.append(query_database)

        agent = Agent(
            name="feature_chat_agent",
            instructions=instructions,
            model=model_name,
            tools=tools,
        )

        result = await Runner.run(agent, run_input, context=ctx)
        raw_out = result.final_output

        answer = raw_out if isinstance(raw_out, str) else str(raw_out)
        return answer, ctx.sources, ctx.db_queries_audit
