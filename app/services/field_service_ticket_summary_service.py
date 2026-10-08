from types import SimpleNamespace

from fastapi import HTTPException, status
from pydantic import ValidationError

from app.config.setting import settings
from app.prompts.field_service_ticket_summary import (
    FIELD_SERVICE_TICKET_SUMMARY_SYSTEM_PROMPT,
    get_field_service_ticket_summary_prompt,
)
from app.schemas.field_service_ticket_summary import FieldServiceTicket
from app.services.agent_service import AgentService
from app.services.unit_ticket_client import UnitTicketClient


class FieldServiceTicketSummaryService:
    def __init__(
        self,
        agent_service: AgentService,
        unit_ticket_client: UnitTicketClient,
    ):
        self.agent_service = agent_service
        self.unit_ticket_client = unit_ticket_client

    async def summarize(self, unit_id: str) -> str:
        """Fetch a unit's tickets, summarize them, and persist the summary on the unit."""
        try:
            tickets = await self._fetch_tickets(unit_id)
            summary = await self._generate_summary(unit_id, tickets)
            await self._persist_summary(unit_id, summary)
            return summary
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error: {exc}",
            ) from exc

    async def _fetch_tickets(self, unit_id: str) -> list[FieldServiceTicket]:
        outcome = await self.unit_ticket_client.fetch_unit_tickets(unit_id)
        if outcome.kind == "error":
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Could not fetch tickets for unit {unit_id}: "
                f"{outcome.error_detail}",
            )
        try:
            return [FieldServiceTicket.model_validate(t) for t in outcome.tickets]
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Unexpected ticket payload for unit {unit_id}: {exc}",
            ) from exc

    async def _generate_summary(
        self, unit_id: str, tickets: list[FieldServiceTicket]
    ) -> str:
        prompt = get_field_service_ticket_summary_prompt(
            unit_id=unit_id,
            tickets=tickets,
        )
        persona = SimpleNamespace(
            prompt_text=FIELD_SERVICE_TICKET_SUMMARY_SYSTEM_PROMPT,
            model_name=settings.FIELD_SERVICE_TICKET_SUMMARY_MODEL,
        )
        return await self.agent_service.generate_async(prompt=prompt, persona=persona)

    async def _persist_summary(self, unit_id: str, summary: str) -> None:
        outcome = await self.unit_ticket_client.write_unit_summary(unit_id, summary)
        if outcome.kind == "unit_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No unit matches id {unit_id}",
            )
        if outcome.kind == "error":
            # Surfaced rather than swallowed: returning a summary that was never stored
            # would make the endpoint look like it succeeded.
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Summary generated but not saved to unit {unit_id}: "
                f"{outcome.error_detail}",
            )
