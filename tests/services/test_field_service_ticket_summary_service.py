"""The summary endpoint orchestrates fetch -> summarize -> persist. Upstream failures
must not be reported as success: a summary that was generated but never stored is a 502,
not a 200."""

import pytest
from fastapi import HTTPException

from app.services.field_service_ticket_summary_service import (
    FieldServiceTicketSummaryService,
)
from app.services.unit_ticket_client import FetchTicketsOutcome, WriteSummaryOutcome

TICKET = {
    "id": "tk-1",
    "title": "Compressor short-cycling",
    "description": "Trips the breaker",
    "unitSerialNumber": "SN-44821-B",
    "messages": [
        {
            "id": "m-1",
            "sender": {"id": "u-1", "username": "jdoe", "fullName": "Jane Doe"},
            "senderType": "Employee",
            "fieldServiceTicketId": "tk-1",
            "date": 1754000000000,
            "text": "Replaced the low-pressure switch.",
            "hasFile": False,
        }
    ],
}


class _StubAgentService:
    def __init__(self, result="## Ticket tk-1 — Compressor short-cycling"):
        self.result = result
        self.last_prompt = None

    async def generate_async(self, prompt, persona):
        self.last_prompt = prompt
        return self.result


class _StubClient:
    def __init__(self, fetch_outcome, write_outcome=None):
        self._fetch_outcome = fetch_outcome
        self._write_outcome = write_outcome or WriteSummaryOutcome(kind="ok")
        self.written = []

    async def fetch_unit_tickets(self, unit_id):
        return self._fetch_outcome

    async def write_unit_summary(self, unit_id, summary):
        self.written.append((unit_id, summary))
        return self._write_outcome


def _service(fetch_outcome, write_outcome=None, agent=None):
    agent = agent or _StubAgentService()
    client = _StubClient(fetch_outcome, write_outcome)
    service = FieldServiceTicketSummaryService(
        agent_service=agent, unit_ticket_client=client
    )
    return service, agent, client


@pytest.mark.asyncio
async def test_summarize_returns_markdown_and_persists_it():
    service, agent, client = _service(
        FetchTicketsOutcome(kind="ok", tickets=[TICKET])
    )
    detail = await service.summarize("unit-1")

    assert detail == agent.result
    assert client.written == [("unit-1", agent.result)]


@pytest.mark.asyncio
async def test_summarize_prompt_includes_title_and_transcript():
    service, agent, _ = _service(FetchTicketsOutcome(kind="ok", tickets=[TICKET]))
    await service.summarize("unit-1")

    assert "Compressor short-cycling" in agent.last_prompt
    assert "Replaced the low-pressure switch." in agent.last_prompt
    # Serial comes from the ticket, not the unit id.
    assert "SN-44821-B" in agent.last_prompt


@pytest.mark.asyncio
async def test_summarize_with_no_tickets_still_summarizes_and_persists():
    service, agent, client = _service(FetchTicketsOutcome(kind="ok", tickets=[]))
    detail = await service.summarize("unit-1")

    assert detail == agent.result
    assert client.written == [("unit-1", agent.result)]


@pytest.mark.asyncio
async def test_fetch_failure_raises_502():
    service, _, _ = _service(FetchTicketsOutcome(kind="error", error_detail="boom"))
    with pytest.raises(HTTPException) as exc_info:
        await service.summarize("unit-1")
    assert exc_info.value.status_code == 502


@pytest.mark.asyncio
async def test_write_unit_not_found_raises_404():
    service, _, _ = _service(
        FetchTicketsOutcome(kind="ok", tickets=[TICKET]),
        WriteSummaryOutcome(kind="unit_not_found"),
    )
    with pytest.raises(HTTPException) as exc_info:
        await service.summarize("unit-1")
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_write_failure_raises_502_rather_than_returning_unsaved_summary():
    service, _, _ = _service(
        FetchTicketsOutcome(kind="ok", tickets=[TICKET]),
        WriteSummaryOutcome(kind="error", error_detail="boom"),
    )
    with pytest.raises(HTTPException) as exc_info:
        await service.summarize("unit-1")
    assert exc_info.value.status_code == 502


@pytest.mark.asyncio
async def test_malformed_ticket_payload_raises_502():
    service, _, _ = _service(
        FetchTicketsOutcome(kind="ok", tickets=[{"no_id_field": True}])
    )
    with pytest.raises(HTTPException) as exc_info:
        await service.summarize("unit-1")
    assert exc_info.value.status_code == 502
