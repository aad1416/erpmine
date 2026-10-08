"""Models for the unit RCA tool.

The RCA report mirrors the three `rcaReportInfo` fields on the Lyndom ticket model
(edit-field-service-ticket-ai.md). Ticket and message wire models are reused from
`field_service_ticket_summary` rather than redefined — both tools read the same
`getUnitFieldServiceTicketsEndpointAI` payload.
"""

from pydantic import BaseModel, Field


class UnitRCARequest(BaseModel):
    unit_id: str
    ticket_id: str


class UnitRCAReport(BaseModel):
    """The agent's structured conclusion. Field names are the corrected spellings;
    the upstream wire names are misspelled and translated in UnitTicketClient."""

    problem_definition: str = Field(
        description="What is actually wrong with the unit, stated as an observable fault."
    )
    cause_identification: str = Field(
        description="The underlying root cause, not the symptom."
    )
    preventive_action: str = Field(
        description="What the technician should do now, and what prevents a recurrence."
    )


class UnitRCAResponse(UnitRCAReport):
    # The RCA is returned even when the write-back fails, so the technician is not
    # blocked by a Lyndom outage; `saved` tells the caller whether the ticket was
    # actually updated.
    saved: bool = True
    save_error: str | None = None
