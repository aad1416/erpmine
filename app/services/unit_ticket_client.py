"""Wraps the AI endpoints the field service ticket tools need (ai-endpoints.md,
edit-field-service-ticket-ai.md): reading a unit's tickets, writing the generated
summary back onto the unit, and writing an RCA report back onto a ticket. Mirrors
TicketClient — outcomes are returned, never raised, so the calling service owns the
HTTP translation."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, Optional

import httpx

from app.config.setting import settings

if TYPE_CHECKING:
    from app.schemas.unit_rca import UnitRCAReport

logger = logging.getLogger(__name__)

FetchTicketsOutcomeKind = Literal["ok", "error"]
WriteSummaryOutcomeKind = Literal["ok", "unit_not_found", "error"]
WriteRCAOutcomeKind = Literal["ok", "ticket_not_found", "error"]


@dataclass
class FetchTicketsOutcome:
    kind: FetchTicketsOutcomeKind
    # An empty list is a valid "ok" — the endpoint declares no typed errors, so an
    # unknown unit id yields [] rather than a 404 (ai-endpoints.md §getUnit...AI).
    tickets: list[dict] = field(default_factory=list)
    error_detail: Optional[str] = None


@dataclass
class WriteSummaryOutcome:
    kind: WriteSummaryOutcomeKind
    error_detail: Optional[str] = None


@dataclass
class WriteRCAOutcome:
    kind: WriteRCAOutcomeKind
    error_detail: Optional[str] = None


class UnitTicketClient:
    def __init__(self) -> None:
        self._base_url = settings.TICKET_API_BASE_URL
        self._token = settings.TICKET_API_BEARER_TOKEN

    @property
    def _headers(self) -> dict[str, str]:
        # AI actor auth (authMode: 'AI') — the same Bearer api-token path TicketClient
        # uses for the sibling /ai endpoints, not a human user JWT.
        return {"Authorization": f"Bearer {self._token}"}

    def _client(self) -> httpx.AsyncClient:
        transport = httpx.AsyncHTTPTransport(retries=2)
        return httpx.AsyncClient(
            base_url=self._base_url, timeout=15.0, transport=transport
        )

    async def fetch_unit_tickets(self, unit_id: str) -> FetchTicketsOutcome:
        """List every field service ticket on a unit. Unpaginated — a plain array."""
        async with self._client() as client:
            try:
                response = await client.get(
                    f"/store-panel/field-service-ticket/by-unit/{unit_id}",
                    headers=self._headers,
                )
            except httpx.HTTPError as exc:
                logger.exception("Fetch unit tickets failed for unit %s", unit_id)
                return FetchTicketsOutcome(kind="error", error_detail=str(exc))

        if response.status_code != 200:
            return FetchTicketsOutcome(
                kind="error",
                error_detail=f"unexpected status {response.status_code}",
            )

        try:
            payload = response.json()
        except ValueError as exc:
            logger.exception("Fetch unit tickets returned non-JSON for unit %s", unit_id)
            return FetchTicketsOutcome(kind="error", error_detail=str(exc))

        if not isinstance(payload, list):
            return FetchTicketsOutcome(
                kind="error",
                error_detail=f"expected a list of tickets, got {type(payload).__name__}",
            )

        return FetchTicketsOutcome(kind="ok", tickets=payload)

    async def write_unit_summary(self, unit_id: str, summary: str) -> WriteSummaryOutcome:
        """Persist the generated summary onto the unit. The Unit response does not echo
        the summary back, so success is judged by status alone."""
        body = {"fieldServiceTicketsSummary": summary}
        async with self._client() as client:
            try:
                response = await client.patch(
                    f"/store-panel/unit/{unit_id}/ai",
                    json=body,
                    headers=self._headers,
                )
            except httpx.HTTPError as exc:
                logger.exception("Write unit summary failed for unit %s", unit_id)
                return WriteSummaryOutcome(kind="error", error_detail=str(exc))

        if response.status_code == 200:
            return WriteSummaryOutcome(kind="ok")

        if response.status_code == 404:
            # Branch on `name`, not `code` — codes are only unique within a module.
            try:
                name = response.json().get("name")
            except ValueError:
                name = None
            if name == "UNIT_NOT_FOUND":
                return WriteSummaryOutcome(kind="unit_not_found")

        return WriteSummaryOutcome(
            kind="error", error_detail=f"unexpected status {response.status_code}"
        )

    async def write_ticket_rca(
        self, ticket_id: str, report: "UnitRCAReport"
    ) -> WriteRCAOutcome:
        """Persist an RCA report onto a ticket. The body is flattened with an
        `rcaReportInfo` prefix while the model nests the same three values
        (edit-field-service-ticket-ai.md §Flat body, nested model). Returns
        SimpleMessage, not the updated ticket, so success is judged by status alone."""
        body = {
            "rcaReportInfoProblemDefinition": report.problem_definition,
            "rcaReportInfoCauseIdentification": report.cause_identification,
            # "preventine" is a typo baked into the wire contract and the model. It
            # must be sent exactly as spelled (edit-field-service-ticket-ai.md §Spelling).
            "rcaReportInfoPreventineActionIdentification": report.preventive_action,
        }
        async with self._client() as client:
            try:
                response = await client.patch(
                    f"/store-panel/field-service-ticket/{ticket_id}/ai",
                    json=body,
                    headers=self._headers,
                )
            except httpx.HTTPError as exc:
                logger.exception("Write ticket RCA failed for ticket %s", ticket_id)
                return WriteRCAOutcome(kind="error", error_detail=str(exc))

        if response.status_code == 200:
            return WriteRCAOutcome(kind="ok")

        if response.status_code == 404:
            # Branch on `name`, not `code` — codes are only unique within a module.
            try:
                name = response.json().get("name")
            except ValueError:
                name = None
            if name == "FIELD_SERVICE_TICKET_NOT_FOUND":
                return WriteRCAOutcome(kind="ticket_not_found")

        return WriteRCAOutcome(
            kind="error", error_detail=f"unexpected status {response.status_code}"
        )
