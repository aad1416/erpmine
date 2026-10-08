"""The RCA endpoint orchestrates resolve-agent -> fetch -> split -> analyze -> persist.

Two behaviors distinguish it from the summary endpoint: the target ticket is selected
from the unit's own ticket list (so a ticket on another unit is unreachable), and a
failed write-back returns the RCA with saved=False rather than a 502 — the technician
should still get the analysis when Lyndom is unavailable.
"""

import pytest
from fastapi import HTTPException

from app.schemas.unit_rca import UnitRCAReport
from app.services.unit_rca_service import UnitRCAService
from app.services.unit_ticket_client import FetchTicketsOutcome, WriteRCAOutcome

TARGET = {
    "id": "tk-1",
    "title": "Compressor short-cycling",
    "description": "Trips the breaker every 4 minutes",
    "unitSerialNumber": "SN-44821-B",
    "messages": [
        {
            "id": "m-1",
            "sender": {"id": "u-1", "username": "jdoe", "fullName": "Jane Doe"},
            "senderType": "Employee",
            "fieldServiceTicketId": "tk-1",
            "date": 1754000000000,
            "text": "Suction line is frosted.",
            "hasFile": False,
        }
    ],
}

OLDER = {
    "id": "tk-0",
    "title": "Compressor short-cycling",
    "description": "Same fault three months ago",
    "unitSerialNumber": "SN-44821-B",
}

REPORT = UnitRCAReport(
    problem_definition="Compressor short-cycles.",
    cause_identification="Low refrigerant charge; recurrence of tk-0.",
    preventive_action="Leak-check the suction line braze joint.",
)


class _StubFeature:
    id = 42


_UNSET = object()


class _StubFeatureService:
    def __init__(self, feature=_UNSET):
        self.feature = _StubFeature() if feature is _UNSET else feature
        self.calls = []

    def get_feature_by_entity_id(self, entity_id, store_id=None):
        self.calls.append((entity_id, store_id))
        return self.feature


class _StubClient:
    def __init__(self, fetch_outcome, write_outcome=None):
        self._fetch_outcome = fetch_outcome
        self._write_outcome = write_outcome or WriteRCAOutcome(kind="ok")
        self.written = []

    async def fetch_unit_tickets(self, unit_id):
        return self._fetch_outcome

    async def write_ticket_rca(self, ticket_id, report):
        self.written.append((ticket_id, report))
        return self._write_outcome


class _StubRunner:
    def __init__(self, report=REPORT):
        self.report = report
        self.last_ctx = None
        self.last_input = None

    async def run(self, *, system_prompt, model_name, run_input, ctx):
        self.last_ctx = ctx
        self.last_input = run_input
        return self.report, []


def _service(tickets=_UNSET, write_outcome=None, feature_service=None, runner=None):
    if tickets is _UNSET:
        tickets = [TARGET, OLDER]
    fetch = (
        tickets
        if isinstance(tickets, FetchTicketsOutcome)
        else FetchTicketsOutcome(kind="ok", tickets=tickets)
    )
    client = _StubClient(fetch, write_outcome)
    runner = runner or _StubRunner()
    service = UnitRCAService(
        feature_service=feature_service or _StubFeatureService(),
        unit_ticket_client=client,
        document_retrieval_tool_service=object(),
        agent_runner=runner,
    )
    return service, client, runner


@pytest.mark.asyncio
async def test_returns_rca_and_writes_it_back():
    service, client, _ = _service()
    result = await service.analyze("unit-1", "tk-1", "store-9")

    assert result.problem_definition == REPORT.problem_definition
    assert result.saved is True
    assert result.save_error is None
    assert client.written == [("tk-1", REPORT)]


@pytest.mark.asyncio
async def test_target_is_excluded_from_its_own_history():
    service, _, runner = _service()
    await service.analyze("unit-1", "tk-1", "store-9")

    # The target's transcript appears; the sibling ticket appears as history.
    assert "TARGET TICKET tk-1" in runner.last_input
    assert "Suction line is frosted." in runner.last_input
    assert "tk-0" in runner.last_input
    assert "1 earlier ticket(s)" in runner.last_input


@pytest.mark.asyncio
async def test_single_ticket_unit_yields_empty_history_and_still_analyzes():
    service, _, runner = _service(tickets=[TARGET])
    result = await service.analyze("unit-1", "tk-1", "store-9")

    assert result.saved is True
    assert "0 earlier ticket(s)" in runner.last_input
    assert "only ticket recorded on this unit" in runner.last_input


@pytest.mark.asyncio
async def test_unknown_ticket_id_is_404():
    service, _, _ = _service()
    with pytest.raises(HTTPException) as exc:
        await service.analyze("unit-1", "tk-missing", "store-9")
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_empty_ticket_list_is_404():
    service, _, _ = _service(tickets=[])
    with pytest.raises(HTTPException) as exc:
        await service.analyze("unit-1", "tk-1", "store-9")
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_fetch_failure_is_502():
    service, _, _ = _service(
        tickets=FetchTicketsOutcome(kind="error", error_detail="boom")
    )
    with pytest.raises(HTTPException) as exc:
        await service.analyze("unit-1", "tk-1", "store-9")
    assert exc.value.status_code == 502


@pytest.mark.asyncio
async def test_missing_field_service_agent_is_404():
    service, _, _ = _service(feature_service=_StubFeatureService(feature=None))
    with pytest.raises(HTTPException) as exc:
        await service.analyze("unit-1", "tk-1", "store-9")
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_agent_is_resolved_from_token_store_and_scopes_retrieval():
    feature_service = _StubFeatureService()
    service, _, runner = _service(feature_service=feature_service)
    await service.analyze("unit-1", "tk-1", "store-9")

    assert feature_service.calls == [("fieldservice", "store-9")]
    assert runner.last_ctx.feature_id == 42


@pytest.mark.asyncio
async def test_write_failure_returns_rca_unsaved_rather_than_raising():
    service, _, _ = _service(
        write_outcome=WriteRCAOutcome(kind="error", error_detail="unexpected status 503")
    )
    result = await service.analyze("unit-1", "tk-1", "store-9")

    assert result.saved is False
    assert result.save_error == "unexpected status 503"
    # The analysis still reaches the technician.
    assert result.cause_identification == REPORT.cause_identification


@pytest.mark.asyncio
async def test_write_ticket_not_found_returns_rca_unsaved():
    service, _, _ = _service(write_outcome=WriteRCAOutcome(kind="ticket_not_found"))
    result = await service.analyze("unit-1", "tk-1", "store-9")

    assert result.saved is False
    assert "tk-1" in result.save_error
