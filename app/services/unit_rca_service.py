import logging

from fastapi import HTTPException, status
from pydantic import ValidationError

from app.config.setting import settings
from app.prompts.unit_rca import UNIT_RCA_SYSTEM_PROMPT, get_unit_rca_prompt
from app.schemas.field_service_ticket_summary import FieldServiceTicket
from app.schemas.unit_rca import UnitRCAResponse
from app.services.document_retrieval_tool_service import DocumentRetrievalToolService
from app.services.feature_service import FeatureService
from app.services.unit_rca_agent_runner import UnitRCAAgentRunner, UnitRCAToolContext
from app.services.unit_ticket_client import UnitTicketClient

logger = logging.getLogger(__name__)

# The field service agent seeded per store (scripts/seed_system_agents.py). Its feature
# id scopes document retrieval to that store's equipment documentation.
FIELD_SERVICE_AGENT_SLUG = "fieldservice"

# Matches the codebase default for chat retrieval; not a setting.
_RAG_TOP_K = 5


class UnitRCAService:
    def __init__(
        self,
        feature_service: FeatureService,
        unit_ticket_client: UnitTicketClient,
        document_retrieval_tool_service: DocumentRetrievalToolService,
        agent_runner: UnitRCAAgentRunner,
    ):
        self.feature_service = feature_service
        self.unit_ticket_client = unit_ticket_client
        self.document_retrieval_tool_service = document_retrieval_tool_service
        self.agent_runner = agent_runner

    async def analyze(
        self, unit_id: str, ticket_id: str, store_id: str
    ) -> UnitRCAResponse:
        """Analyze one ticket against its unit's history and the store's equipment
        documentation, then write the RCA back onto the ticket."""
        try:
            feature_id = self._resolve_agent_feature_id(store_id)
            tickets = await self._fetch_tickets(unit_id)
            target, history = self._split_target(tickets, unit_id, ticket_id)
            report = await self._generate_report(unit_id, target, history, feature_id)
            return await self._persist_report(ticket_id, report)
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Unit RCA failed for ticket %s on unit %s", ticket_id, unit_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error: {exc}",
            ) from exc

    def _resolve_agent_feature_id(self, store_id: str) -> int:
        """Resolve the store's field service agent. store_id comes from the caller's
        token, never the request body — a caller-supplied feature id would let one
        store read another's documents."""
        feature = self.feature_service.get_feature_by_entity_id(
            FIELD_SERVICE_AGENT_SLUG, store_id=store_id
        )
        if feature is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    f"No {FIELD_SERVICE_AGENT_SLUG} agent is configured for this store"
                ),
            )
        return feature.id

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

    def _split_target(
        self, tickets: list[FieldServiceTicket], unit_id: str, ticket_id: str
    ) -> tuple[FieldServiceTicket, list[FieldServiceTicket]]:
        """Select the ticket under analysis; the rest is the unit's issue history.
        Selecting from the unit's own list means a ticket belonging to another unit is
        unreachable — the pairing is validated by construction."""
        target = next((t for t in tickets if t.id == ticket_id), None)
        if target is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No ticket {ticket_id} on unit {unit_id}",
            )
        history = [t for t in tickets if t.id != ticket_id]
        return target, history

    async def _generate_report(
        self,
        unit_id: str,
        target: FieldServiceTicket,
        history: list[FieldServiceTicket],
        feature_id: int,
    ):
        prompt = get_unit_rca_prompt(unit_id=unit_id, target=target, history=history)
        ctx = UnitRCAToolContext(
            feature_id=feature_id,
            rag_top_k=_RAG_TOP_K,
            document_retrieval_tool_service=self.document_retrieval_tool_service,
        )
        report, sources = await self.agent_runner.run(
            system_prompt=UNIT_RCA_SYSTEM_PROMPT,
            model_name=settings.UNIT_RCA_MODEL,
            run_input=prompt,
            ctx=ctx,
        )
        logger.info(
            "Unit RCA for ticket %s consulted %d documentation chunk(s)",
            target.id,
            len(sources),
        )
        return report

    async def _persist_report(self, ticket_id: str, report) -> UnitRCAResponse:
        """Write the RCA onto the ticket. A write failure does not fail the request:
        the technician still gets the analysis, flagged as unsaved."""
        outcome = await self.unit_ticket_client.write_ticket_rca(ticket_id, report)
        if outcome.kind == "ok":
            return UnitRCAResponse(**report.model_dump())

        save_error = (
            f"No ticket matches id {ticket_id}"
            if outcome.kind == "ticket_not_found"
            else outcome.error_detail
        )
        logger.warning("RCA generated but not saved to ticket %s: %s", ticket_id, save_error)
        return UnitRCAResponse(**report.model_dump(), saved=False, save_error=save_error)
