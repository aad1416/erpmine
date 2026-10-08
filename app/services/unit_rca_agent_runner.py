"""Agents SDK wrapper for the unit RCA tool.

Mirrors ChatAgentRunner, with two deliberate differences: the only tool is document
retrieval (no ERP/database access), and the run is typed — `output_type` makes the SDK
return a validated UnitRCAReport, so the three RCA fields reach the PATCH body without
parsing prose back apart.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List

from agents import Agent, RunContextWrapper, Runner, function_tool

from app.schemas.unit_rca import UnitRCAReport

if TYPE_CHECKING:
    from app.services.document_retrieval_tool_service import DocumentRetrievalToolService

logger = logging.getLogger(__name__)


@dataclass
class UnitRCAToolContext:
    feature_id: int
    rag_top_k: int
    document_retrieval_tool_service: "DocumentRetrievalToolService"
    sources: List[dict] = field(default_factory=list)


def _merge_sources(existing: List[dict], new_sources: List[dict]) -> None:
    seen = {(s.get("document_id"), s.get("chunk_index")) for s in existing}
    for s in new_sources:
        key = (s.get("document_id"), s.get("chunk_index"))
        if key not in seen:
            seen.add(key)
            existing.append(s)


@function_tool
async def search_equipment_documentation(
    ctx: RunContextWrapper[UnitRCAToolContext], query: str
) -> str:
    """Search this equipment's manuals, datasheets and service documentation. Use it to identify failure modes, specifications, and repair procedures before concluding a root cause. Call it more than once to narrow in on a component or error code. query — a concise technical search phrase, e.g. "compressor short cycling low refrigerant"."""

    ctx_obj = ctx.context
    result = await ctx_obj.document_retrieval_tool_service.retrieve(
        query=query,
        feature_id=ctx_obj.feature_id,
        top_k=ctx_obj.rag_top_k,
    )
    _merge_sources(ctx_obj.sources, result.sources)
    return result.content


class UnitRCAAgentRunner:
    """Runs the RCA agent loop and returns a structured report."""

    async def run(
        self,
        *,
        system_prompt: str,
        model_name: str,
        run_input: str,
        ctx: UnitRCAToolContext,
    ) -> tuple[UnitRCAReport, List[dict]]:
        agent = Agent(
            name="unit_rca_agent",
            instructions=system_prompt,
            model=model_name,
            tools=[search_equipment_documentation],
            output_type=UnitRCAReport,
        )

        result = await Runner.run(agent, run_input, context=ctx)
        report = result.final_output

        if not isinstance(report, UnitRCAReport):
            # output_type should guarantee this; treat a miss as a server error rather
            # than shipping a half-formed RCA to the ticket.
            raise TypeError(
                f"RCA agent returned {type(report).__name__}, expected UnitRCAReport"
            )

        return report, ctx.sources
