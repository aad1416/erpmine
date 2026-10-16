"""The core AI call (02-architecture-decisions.md §7, §10).

The agent may read only the attachments it needs, then one terminal decision tool ends
the turn. `StopAtTools` enforces that ask/create/reply boundary at SDK level.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Literal, Optional

from agents import (
    Agent,
    ModelSettings,
    Runner,
    RunContextWrapper,
    StopAtTools,
    ToolOutputFileContent,
    ToolOutputImage,
    ToolOutputText,
    function_tool,
)

from app.config.setting import settings
from app.prompts.support_agent import build_support_agent_instructions

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.db.models.EmailAttachment import EmailAttachment
    from app.services.email_attachment_service import EmailAttachmentService


@dataclass
class SupportToolContext:
    """Captures which tool the model called and with what arguments.
    conversation_service.py applies the actual side effects (DB writes, ticket API call,
    dispatch) after the agent run completes — the tool functions themselves only record
    intent, the same separation `ChatToolContext` uses for `sources`/`db_queries_audit`.
    """

    tool_called: Optional[str] = None
    ask_question_text: Optional[str] = None
    ask_question_reason: Optional[str] = None
    reply_text: Optional[str] = None
    create_ticket_args: Optional[dict] = None
    attachment_service: Optional["EmailAttachmentService"] = None
    attachments: dict[str, "EmailAttachment"] = field(default_factory=dict)
    attachment_tokens_read: int = 0
    attachment_reads: set[tuple[str, bool]] = field(default_factory=set)
    visual_read_attempted: bool = False


@function_tool
async def ask_question(
    ctx: RunContextWrapper[SupportToolContext],
    question_text: str,
    reason: Literal["baseline", "serial_correction"],
) -> str:
    """Ask the customer for the unit serial and/or issue explanation, or to correct a
    serial that didn't match any known unit. question_text — the question to send to
    the customer. reason — "baseline" for a normal gathering question, or
    "serial_correction" if this follows a create_ticket attempt that came back with an
    unrecognized serial."""
    ctx.context.tool_called = "ask_question"
    ctx.context.ask_question_text = question_text
    ctx.context.ask_question_reason = reason
    return "ok"


@function_tool
async def create_ticket(
    ctx: RunContextWrapper[SupportToolContext],
    unit_serial: str,
    issue_description: str,
    title: str,
    customer_message: str,
) -> str:
    """Open a field service ticket once both the unit serial and a usable issue
    explanation are known. title — a short, specific ticket title. issue_description —
    the customer's explanation, cleaned up but not paraphrased away. customer_message —
    the confirmation text to send back, written assuming the ticket is created
    successfully."""
    ctx.context.tool_called = "create_ticket"
    ctx.context.create_ticket_args = {
        "unit_serial": unit_serial,
        "issue_description": issue_description,
        "title": title,
        "customer_message": customer_message,
    }
    return "ok"


@function_tool
async def reply(ctx: RunContextWrapper[SupportToolContext], text: str) -> str:
    """Send a plain reply for anything that isn't a question you need answered or a
    ticket action — thanks, small talk, spam, or a holding message when giving up."""
    ctx.context.tool_called = "reply"
    ctx.context.reply_text = text
    return "ok"


@function_tool
async def read_email_attachment(
    ctx: RunContextWrapper[SupportToolContext], attachment_id: str, visual: bool = False
):
    """Read one captured customer email file when its contents are needed to
    understand the problem or serial number. Captured files are probably related even
    when their names are generic, so do not infer irrelevance from metadata alone. Use an
    id from the attachment manifest. Set visual=true for images and when a mixed PDF's
    images/layout matter. Videos cannot be viewed and will return that limitation; their
    originals are still sent to the ticket."""
    from app.config.email_attachments import MAX_ATTACHMENT_TOKENS_PER_AGENT_RUN
    from app.services.email_attachment_service import EmailAttachmentUnavailableError

    context = ctx.context
    attachment = context.attachments.get(attachment_id)
    if not attachment or not context.attachment_service:
        return ToolOutputText(text="That attachment is not available.")

    should_use_visual = attachment.kind in {"image", "pdf_scanned"} or (
        attachment.kind == "pdf_mixed" and visual
    )
    read_key = (attachment_id, should_use_visual)
    if read_key in context.attachment_reads:
        return ToolOutputText(text="This attachment was already provided in this run.")

    if should_use_visual:
        try:
            file_id = await context.attachment_service.ensure_openai_file(attachment)
        except EmailAttachmentUnavailableError as exc:
            return ToolOutputText(text=str(exc))
        context.attachment_reads.add(read_key)
        context.visual_read_attempted = True
        if attachment.kind == "image":
            return ToolOutputImage(file_id=file_id, detail="auto")
        return ToolOutputFileContent(file_id=file_id)

    if visual and attachment.kind != "pdf_mixed":
        return ToolOutputText(
            text="This file has no supported visual representation for the support AI."
        )

    text = await context.attachment_service.read_text(attachment)
    next_tokens = context.attachment_tokens_read + attachment.token_count
    if next_tokens > MAX_ATTACHMENT_TOKENS_PER_AGENT_RUN:
        return ToolOutputText(
            text="Reading this file would exceed the attachment text limit for this run."
        )
    context.attachment_tokens_read = next_tokens
    context.attachment_reads.add(read_key)
    return ToolOutputText(
        text=f"Contents/status of {attachment.file_name!r}:\n\n{text}"
    )


class DecisionAgent:
    async def run(
        self,
        *,
        run_input: str,
        ctx: SupportToolContext,
        allow_gathering_tools: bool,
    ) -> SupportToolContext:
        """`allow_gathering_tools=False` withholds ask_question/create_ticket entirely
        (round-cap/serial-correction-cap exhausted, §10.1's escalation behavior) so the
        model can only call reply — enforcing the cap structurally rather than trusting
        the prompt's stated limits."""
        tools: List = [reply]
        if allow_gathering_tools:
            tools = [ask_question, create_ticket, reply]
        if ctx.attachments:
            tools.append(read_email_attachment)

        agent = Agent(
            name="support_decision_agent",
            instructions=build_support_agent_instructions(),
            model=settings.SUPPORT_DECISION_MODEL,
            tools=tools,
            tool_use_behavior=StopAtTools(
                stop_at_tool_names=["ask_question", "create_ticket", "reply"]
            ),
            # A support turn must end in an explicit action. Without required tool
            # choice, a model can occasionally return plain text despite the prompt,
            # leaving ctx.tool_called unset and causing an unnecessary escalation.
            model_settings=ModelSettings(
                parallel_tool_calls=False,
                tool_choice="required",
            ),
            # A read_email_attachment call is only evidence gathering. The SDK
            # otherwise resets required tool choice after that first tool call,
            # allowing the next turn to end as plain text with no action.
            reset_tool_choice=False,
        )
        try:
            await Runner.run(agent, run_input, context=ctx, max_turns=8)
        except Exception:
            if not ctx.visual_read_attempted:
                raise
            # Do not let a future non-visual model turn a customer attachment into a
            # hard ingestion failure. Retry the decision without the reading tool and
            # explicitly require human review of the original evidence.
            logger.warning(
                "Support model %s could not consume a visual email attachment",
                settings.SUPPORT_DECISION_MODEL,
                exc_info=True,
            )
            ctx.tool_called = None
            fallback_tools: List = [reply]
            if allow_gathering_tools:
                fallback_tools = [ask_question, create_ticket, reply]
            fallback_agent = Agent(
                name="support_decision_agent_visual_fallback",
                instructions=build_support_agent_instructions(),
                model=settings.SUPPORT_DECISION_MODEL,
                tools=fallback_tools,
                tool_use_behavior=StopAtTools(
                    stop_at_tool_names=["ask_question", "create_ticket", "reply"]
                ),
                model_settings=ModelSettings(
                    parallel_tool_calls=False,
                    tool_choice="required",
                ),
                reset_tool_choice=False,
            )
            await Runner.run(
                fallback_agent,
                run_input
                + "\n\nThe visual attachment could not be inspected by the current model. "
                "Do not claim to have seen it. It will still be forwarded for human review.",
                context=ctx,
                max_turns=4,
            )

        if ctx.tool_called is None:
            logger.error("Support decision agent turn produced no tool call")
        return ctx
