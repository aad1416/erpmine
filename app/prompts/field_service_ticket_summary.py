"""Prompt templates for the field service ticket summary tool."""

from datetime import datetime, timezone

from app.schemas.field_service_ticket_summary import (
    FieldServiceTicket,
    FieldServiceTicketMessage,
    FieldServiceTicketMessageRole,
)

FIELD_SERVICE_TICKET_SUMMARY_SYSTEM_PROMPT = (
    "You are a support operations assistant that summarizes the service history of a "
    "single unit for technicians. You read every ticket raised on that unit and "
    "report each distinct issue and how it ended as flowing prose. You summarize "
    "only what is present in the ticket details and transcripts. You never invent "
    "facts and you never give recommendations or next steps."
)

_ROLE_LABELS = {
    FieldServiceTicketMessageRole.client: "Customer",
    FieldServiceTicketMessageRole.employee: "Support staff",
    FieldServiceTicketMessageRole.ai: "AI assistant",
}

_NO_MESSAGES_PLACEHOLDER = (
    "(No messages have been exchanged on this ticket. Derive the problem from the "
    "ticket description alone, and report the resolution as not resolved with no "
    "messages exchanged.)"
)

_NO_TICKETS_PLACEHOLDER = "(No tickets were provided.)"

_INSTRUCTIONS = """Write a Markdown summary of the unit's whole service history in \
English, using exactly this structure:

## <title>

<one short paragraph per distinct issue>

Roles in the transcripts:
- Customer: the client who reported the issue.
- Support staff: the employee responding to the customer.
- AI assistant: automated responses.

Rules:
- The title is one short line you write yourself: a descriptive characterization of \
the whole history (for example "Mostly loose-hardware and calibration fixes; one \
power failure still unresolved"). Do not use a fixed phrase, and do not put ticket \
ids or ticket counts in it.
- Write one short paragraph per distinct issue, in the order the issues occurred. \
Each paragraph states what went wrong on the unit, taken from the ticket \
description and the conversation, and then how it was fixed — or, if it was not \
fixed, how it ended up.
- If several tickets report the same issue with the same solution, merge them into \
a single paragraph and state that the issue occurred that many times.
- If an issue has no recorded fix, end its paragraph with the last action taken and \
what it is still waiting on.
- Do not put ticket ids or ticket titles in the output, and do not format the \
summary as a list of tickets.
- Do not narrate the conversations message by message.
- Use only information present above. Do not invent facts.
- Do not include recommendations or suggested next steps.
- Write in English regardless of the transcripts' language."""


def render_transcript(messages: list[FieldServiceTicketMessage]) -> str:
    """Render messages as an ordered, role-labeled transcript. Shared with the unit
    RCA prompt so both tools present transcripts to the model identically."""
    if not messages:
        return _NO_MESSAGES_PLACEHOLDER

    ordered = sorted(messages, key=lambda message: message.date)
    lines: list[str] = []
    for message in ordered:
        timestamp = datetime.fromtimestamp(
            message.date / 1000, tz=timezone.utc
        ).strftime("%Y-%m-%d %H:%M UTC")
        role_label = _ROLE_LABELS[message.role]
        attachment = " [attachment]" if message.has_file else ""
        lines.append(
            f"[{timestamp}] {message.sender_name} ({role_label}):{attachment} "
            f"{message.text}"
        )
    return "\n".join(lines)


def _render_ticket(ticket: FieldServiceTicket) -> str:
    """Render a single ticket block with its title, description and transcript."""
    heading = f"### Ticket {ticket.id}"
    if ticket.title:
        heading = f"{heading} — {ticket.title}"
    return (
        f"{heading}\n"
        f"Ticket description:\n{ticket.description}\n\n"
        f"Conversation transcript (chronological):\n"
        f"{render_transcript(ticket.messages)}"
    )


def resolve_unit_label(unit_id: str, tickets: list[FieldServiceTicket]) -> str:
    """Prefer the unit's serial number, which only the tickets carry. Falls back to the
    unit id when there are no tickets or none records a serial."""
    for ticket in tickets:
        if ticket.unit_serial_number:
            return ticket.unit_serial_number
    return unit_id


def get_field_service_ticket_summary_prompt(
    unit_id: str,
    tickets: list[FieldServiceTicket],
) -> str:
    """Build the user prompt for the field service ticket summary tool."""
    if not tickets:
        tickets_block = _NO_TICKETS_PLACEHOLDER
    else:
        tickets_block = "\n\n".join(_render_ticket(ticket) for ticket in tickets)

    unit_label = resolve_unit_label(unit_id, tickets)
    return (
        "Summarize the service history of a single unit. All tickets below belong "
        f"to unit {unit_label}. There are {len(tickets)} ticket(s), each "
        "with its own id, title, description and conversation transcript.\n\n"
        f"{tickets_block}\n\n"
        f"{_INSTRUCTIONS}"
    )
