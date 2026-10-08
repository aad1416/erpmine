"""Prompts for OpenAI Agents SDK chat path (tools + slim run input)."""

from __future__ import annotations

import logging

from pydantic import TypeAdapter, ValidationError

from app.schemas.chats import Attachment


logger = logging.getLogger(__name__)

_ATTACHMENT_ADAPTER: TypeAdapter = TypeAdapter(Attachment)


CHAT_AGENT_TOOL_POLICY = """\
You may have tools for document search and/or live database queries.
- Call retrieve_documents when the user needs product/documentation/policy information not in chat history.
- Call query_database when the user needs transactional or numeric ERP data.
- Do not invent document citations or SQL results; use tool output only.
- After tools return, answer in the persona voice and cite sources when using documentation.
"""


def build_agent_instructions(persona_prompt_text: str, use_rag: bool, use_db: bool) -> str:
    parts = [persona_prompt_text.strip(), CHAT_AGENT_TOOL_POLICY.strip()]
    available: list[str] = []
    if use_rag:
        available.append("retrieve_documents")
    if use_db:
        available.append("query_database")
    if available:
        parts.append(f"Tools enabled for this turn: {', '.join(available)}.")
    else:
        parts.append(
            "No retrieval tools are enabled for this turn; "
            "answer from chat history and general knowledge only."
        )
    return "\n\n".join(parts)


def _format_output_line(item: dict) -> str | None:
    """One compact history-replay line for a prior Output, full SQL included so a
    follow-up turn's `sql=` re-run can use it verbatim. Never rows or specs
    (map decision D5 / ticket 04 history replay)."""
    try:
        attachment = _ATTACHMENT_ADAPTER.validate_python(item)
    except ValidationError:
        logger.warning("Skipping malformed attachment in history replay: %r", item)
        return None

    sql = attachment.provenance.sql
    if attachment.kind == "table":
        if attachment.truncated:
            detail = f"{attachment.row_count} rows ({len(attachment.rows)} shown)"
        else:
            detail = f"{attachment.row_count} rows"
    elif attachment.kind == "chart":
        spec = attachment.spec
        detail = f"{spec.type}, {len(spec.x.values)} categories × {len(spec.series)} series"
        if attachment.provenance.transforms:
            chain = " › ".join(step.transform for step in attachment.provenance.transforms)
            detail = f"{detail} — via {chain}"
    else:  # "file"
        detail = f"{attachment.filename}, {attachment.provenance.row_count} rows"

    return f'[Output: {attachment.kind} "{attachment.title}" — {detail} — SQL: {sql}]'


def build_run_input(history: list, user_message: str, max_history: int = 10) -> str:
    """Markdown user turn (history + current query); mirrors ChatService history block only."""
    prompt_parts: list[str] = []

    if history and len(history) > 0:
        prompt_parts.append("## Chat History\n")
        recent_history = history[-max_history:] if len(history) > max_history else history

        for msg in recent_history:
            role = "User" if msg.role == "user" else "Assistant"
            prompt_parts.append(f"**{role}:** {msg.content}\n")

            attachments = getattr(msg, "attachments", None)
            if role == "Assistant" and attachments:
                for item in attachments:
                    line = _format_output_line(item)
                    if line:
                        prompt_parts.append(f"  {line}\n")

        prompt_parts.append("\n")

    prompt_parts.append("## Current Query\n")
    prompt_parts.append(f"**User:** {user_message}\n")

    return "".join(prompt_parts)
