"""Prompt templates for the unit RCA tool.

Reuses the summary tool's transcript rendering so both tools present tickets to the
model in the same shape; only the framing and instructions differ.
"""

from app.prompts.field_service_ticket_summary import (
    render_transcript,
    resolve_unit_label,
)
from app.schemas.field_service_ticket_summary import FieldServiceTicket

UNIT_RCA_SYSTEM_PROMPT = (
    "You are a field service engineer performing root cause analysis on a single "
    "equipment ticket. You write for a technician who is standing at the unit and "
    "needs to act. You have a document search tool covering this equipment's manuals, "
    "datasheets and service documentation — you use it before drawing conclusions, "
    "because the ticket text alone rarely explains why a component fails. You "
    "distinguish the symptom from the underlying cause, and you never invent part "
    "numbers, tolerances or procedures that the documentation does not state."
)

_NO_HISTORY_PLACEHOLDER = (
    "(This is the only ticket recorded on this unit. Treat the fault as first-time "
    "unless the documentation says it is a known failure mode for this model.)"
)


_INSTRUCTIONS = """\
Produce a root cause analysis of the TARGET TICKET as three fields.

Before you conclude, search the documentation. A single search is rarely enough — \
search again for the specific component, symptom, or error code once you know what \
you are looking for. Base the cause and the corrective action on what the \
documentation states.

problem_definition
  The observable fault on this unit, stated concretely. Include what fails, under \
what conditions, and any measured values present in the ticket. This is the symptom, \
not the cause.

cause_identification
  Why the fault occurs. Name the failing component or mechanism and the reason it \
failed. If the unit's history shows this same failure before, say so explicitly and \
treat recurrence as evidence — a fault that returns after a repair points to an \
unaddressed root cause, not to bad luck. If the evidence supports more than one \
cause, give the most likely one first and state what would confirm it.

preventive_action
  What the technician should do now, as concrete steps, followed by what prevents a \
recurrence. Cite the documentation for procedures and specifications you rely on.

Rules:
- Use only the ticket text, the unit's history, and the documentation you retrieved. \
Do not invent part numbers, torque values, pressures or procedures.
- If the documentation does not cover the fault, say so in cause_identification \
rather than guessing, and base the action on the ticket evidence alone.
- Write in English regardless of the transcripts' language.
- Write plain prose in each field. Do not use Markdown headings."""


def _render_target_ticket(ticket: FieldServiceTicket) -> str:
    """Render the ticket under analysis, with its full transcript."""
    heading = f"## TARGET TICKET {ticket.id}"
    if ticket.title:
        heading = f"{heading} — {ticket.title}"
    return (
        f"{heading}\n"
        f"Ticket description:\n{ticket.description}\n\n"
        f"Conversation transcript (chronological):\n"
        f"{render_transcript(ticket.messages)}"
    )


def _render_history_ticket(ticket: FieldServiceTicket) -> str:
    """Render a prior ticket. Condensed relative to the target: the description
    carries the fault, and full transcripts for every past ticket would crowd out the
    ticket actually under analysis."""
    heading = f"### Ticket {ticket.id}"
    if ticket.title:
        heading = f"{heading} — {ticket.title}"
    return f"{heading}\n{ticket.description}"


def get_unit_rca_prompt(
    unit_id: str,
    target: FieldServiceTicket,
    history: list[FieldServiceTicket],
) -> str:
    """Build the user prompt for the unit RCA tool."""
    if history:
        history_block = "\n\n".join(
            _render_history_ticket(ticket) for ticket in history
        )
    else:
        history_block = _NO_HISTORY_PLACEHOLDER

    unit_label = resolve_unit_label(unit_id, [target, *history])
    return (
        f"Perform a root cause analysis for unit {unit_label}.\n\n"
        f"{_render_target_ticket(target)}\n\n"
        f"## PRIOR ISSUE HISTORY FOR THIS UNIT ({len(history)} earlier ticket(s))\n"
        "Use this to judge whether the target fault is recurring.\n\n"
        f"{history_block}\n\n"
        f"{_INSTRUCTIONS}"
    )
