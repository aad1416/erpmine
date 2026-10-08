from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, List, Optional

from agents import Agent, Runner, RunContextWrapper, function_tool

from app.config.setting import settings
from app.prompts.admin_chat import build_admin_agent_instructions
from app.schemas.personas import PersonaUpdate

if TYPE_CHECKING:
    from app.services.database_query_tool_service import DatabaseQueryToolService
    from app.services.document_retrieval_tool_service import DocumentRetrievalToolService
    from app.services.persona_service import PersonaService

logger = logging.getLogger(__name__)


def _merge_sources(existing: List[dict], new_sources: List[dict]) -> None:
    seen = {(s.get("document_id"), s.get("chunk_index")) for s in existing}
    for s in new_sources:
        key = (s.get("document_id"), s.get("chunk_index"))
        if key not in seen:
            seen.add(key)
            existing.append(s)


def _strip_wrapping_quotes(text: str) -> str:
    text = text.strip()
    if text.startswith('"""') and text.endswith('"""'):
        return text[3:-3].strip()
    if text.startswith('"') and text.endswith('"'):
        return text[1:-1].strip()
    return text


@dataclass
class AdminChatToolContext:
    feature_id: int
    rag_top_k: int
    store_id: Optional[str]
    admin_user_id: str

    document_retrieval_tool_service: "DocumentRetrievalToolService"
    database_query_tool_service: Optional["DatabaseQueryToolService"]
    persona_service: "PersonaService"

    sources: List[dict] = field(default_factory=list)
    db_queries_audit: List[dict] = field(default_factory=list)
    user_accesses: List[str] = field(default_factory=list)
    persona_update_result: Optional[dict] = None
    documents_tool_called: bool = False


@function_tool
async def retrieve_documents(
    ctx: RunContextWrapper[AdminChatToolContext], query: str
) -> str:
    """Search uploaded documentation tied to this feature. Use when the admin needs docs or policy text not in chat history. query — concise search phrase from the admin's question."""

    ctx_obj = ctx.context
    ctx_obj.documents_tool_called = True
    result = await ctx_obj.document_retrieval_tool_service.retrieve(
        query=query,
        feature_id=ctx_obj.feature_id,
        top_k=ctx_obj.rag_top_k,
    )
    _merge_sources(ctx_obj.sources, result.sources)
    return result.content


@function_tool
async def query_database(
    ctx: RunContextWrapper[AdminChatToolContext], question: str
) -> str:
    """Run read-only SQL against the Lyndom ERP (schema retrieval, SQL generation, execution). Use when the admin needs transactional or numeric ERP data. Returns JSON per intent with row previews or errors."""

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


@function_tool
async def update_persona(
    ctx: RunContextWrapper[AdminChatToolContext], new_prompt: str
) -> str:
    """Replace the feature's persona prompt. Use when the admin asks to change the assistant's behavior, tone, or rules. new_prompt — the complete standalone persona prompt (the current persona with the requested changes applied), never a diff or summary."""

    ctx_obj = ctx.context
    cleaned = _strip_wrapping_quotes(new_prompt)
    if not cleaned:
        return "Error: new_prompt is empty; persona was not updated."

    try:
        current_persona = ctx_obj.persona_service.get_persona_for_feature(
            ctx_obj.feature_id
        )
        if not current_persona:
            return f"Error: persona not found for feature {ctx_obj.feature_id}."

        old_prompt = current_persona.prompt_text

        persona_update = PersonaUpdate(
            prompt_text=cleaned,
            model_name=current_persona.model_name,
            updated_by_user_id=ctx_obj.admin_user_id,
        )
        ctx_obj.persona_service.update_persona(
            persona_id=current_persona.id, persona_update=persona_update
        )

        ctx_obj.persona_update_result = {
            "updated": True,
            "old_prompt": old_prompt,
            "new_prompt": cleaned,
        }
        return "Persona updated and saved successfully."
    except Exception as exc:  # noqa: BLE001
        logger.exception("update_persona failed")
        return f"Persona update failed: {exc}"


class AdminChatAgentRunner:
    """Thin wrapper around OpenAI Agents SDK for admin chat (persona management + retrieval tools)."""

    async def run(
        self,
        *,
        persona_prompt_text: str,
        model_name: str,
        run_input: str,
        ctx: AdminChatToolContext,
        use_db_request: bool,
    ) -> tuple[str, List[dict], List[dict], Optional[dict], bool]:
        use_db_tool = use_db_request and settings.DB_RAG_ENABLED
        if use_db_request and not settings.DB_RAG_ENABLED:
            logger.warning(
                "use_db=true but DB_RAG_ENABLED=false; DB tool omitted for this turn"
            )

        instructions = build_admin_agent_instructions(
            persona_prompt_text, use_db=bool(use_db_tool)
        )

        tools: List[Any] = [update_persona, retrieve_documents]
        if use_db_tool:
            tools.append(query_database)

        agent = Agent(
            name="admin_chat_agent",
            instructions=instructions,
            model=model_name,
            tools=tools,
        )

        result = await Runner.run(agent, run_input, context=ctx)
        raw_out = result.final_output

        answer = raw_out if isinstance(raw_out, str) else str(raw_out)
        return (
            answer,
            ctx.sources,
            ctx.db_queries_audit,
            ctx.persona_update_result,
            ctx.documents_tool_called,
        )
