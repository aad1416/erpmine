"""The core AI call (02-architecture-decisions.md §7, §10) — single LLM tool-calling
turn, built the same way chat_agent_runner.py wraps agents.Agent/Runner/function_tool.

`tool_use_behavior="stop_on_first_tool"` is what enforces "exactly one tool call per
turn, no chaining" (§10.3) at the SDK level, rather than relying on prompt wording alone.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Literal, Optional

from agents import Agent, Runner, RunContextWrapper, function_tool

from app.config.setting import settings
from app.prompts.support_agent import build_support_agent_instructions

logger = logging.getLogger(__name__)


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

        agent = Agent(
            name="support_decision_agent",
            instructions=build_support_agent_instructions(),
            model=settings.SUPPORT_DECISION_MODEL,
            tools=tools,
            tool_use_behavior="stop_on_first_tool",
        )
        await Runner.run(agent, run_input, context=ctx)

        if ctx.tool_called is None:
            logger.error("Support decision agent turn produced no tool call")
        return ctx
