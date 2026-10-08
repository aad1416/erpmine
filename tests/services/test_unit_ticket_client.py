"""getUnitFieldServiceTicketsEndpointAI, editUnitEndpointAIStore and
editFieldServiceTicketAIEndpointStore contracts (ai-endpoints.md,
edit-field-service-ticket-ai.md): the fetch endpoint declares no typed errors, so an
empty list is a valid result rather than a not-found; the write endpoints distinguish
UNIT_NOT_FOUND and FIELD_SERVICE_TICKET_NOT_FOUND respectively."""

import httpx
import pytest
import respx
from httpx import Response

from app.config.setting import settings
from app.schemas.unit_rca import UnitRCAReport
from app.services.unit_ticket_client import UnitTicketClient

FETCH_URL = "https://api.example.com/store-panel/field-service-ticket/by-unit/unit-1"
WRITE_URL = "https://api.example.com/store-panel/unit/unit-1/ai"
RCA_URL = "https://api.example.com/store-panel/field-service-ticket/tk-1/ai"


@pytest.fixture(autouse=True)
def _ticket_api_settings(monkeypatch):
    monkeypatch.setattr(settings, "TICKET_API_BASE_URL", "https://api.example.com")
    monkeypatch.setattr(settings, "TICKET_API_BEARER_TOKEN", "test-token")


@pytest.mark.asyncio
@respx.mock
async def test_fetch_unit_tickets_returns_tickets():
    respx.get(FETCH_URL).mock(
        return_value=Response(
            200,
            json=[
                {
                    "id": "tk-1",
                    "title": "Compressor short-cycling",
                    "description": "Trips the breaker",
                    "unitSerialNumber": "SN-44821-B",
                    "messages": [
                        {
                            "id": "m-1",
                            "sender": {"id": "c-1", "name": "Jane Doe"},
                            "senderType": "Client",
                            "fieldServiceTicketId": "tk-1",
                            "date": 1754000000000,
                            "text": "Unit is down again.",
                            "hasFile": False,
                        }
                    ],
                }
            ],
        )
    )
    outcome = await UnitTicketClient().fetch_unit_tickets("unit-1")
    assert outcome.kind == "ok"
    assert len(outcome.tickets) == 1
    assert outcome.tickets[0]["title"] == "Compressor short-cycling"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_unit_tickets_empty_list_is_ok_not_not_found():
    # An unknown unit id yields [] on this endpoint, never a typed UNIT_NOT_FOUND.
    respx.get(FETCH_URL).mock(return_value=Response(200, json=[]))
    outcome = await UnitTicketClient().fetch_unit_tickets("unit-1")
    assert outcome.kind == "ok"
    assert outcome.tickets == []


@pytest.mark.asyncio
@respx.mock
async def test_fetch_unit_tickets_sends_bearer_token():
    route = respx.get(FETCH_URL).mock(return_value=Response(200, json=[]))
    await UnitTicketClient().fetch_unit_tickets("unit-1")
    assert route.calls.last.request.headers["Authorization"] == "Bearer test-token"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_unit_tickets_network_error_is_an_error_outcome():
    respx.get(FETCH_URL).mock(side_effect=httpx.ConnectError("connection failed"))
    outcome = await UnitTicketClient().fetch_unit_tickets("unit-1")
    assert outcome.kind == "error"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_unit_tickets_non_list_payload_is_an_error_outcome():
    respx.get(FETCH_URL).mock(return_value=Response(200, json={"unexpected": "shape"}))
    outcome = await UnitTicketClient().fetch_unit_tickets("unit-1")
    assert outcome.kind == "error"


@pytest.mark.asyncio
@respx.mock
async def test_write_unit_summary_sends_summary_field():
    route = respx.patch(WRITE_URL).mock(return_value=Response(200, json={"id": "unit-1"}))
    outcome = await UnitTicketClient().write_unit_summary("unit-1", "## Ticket tk-1 — X")
    assert outcome.kind == "ok"

    request = route.calls.last.request
    import json

    assert json.loads(request.content) == {
        "fieldServiceTicketsSummary": "## Ticket tk-1 — X"
    }
    assert request.headers["Authorization"] == "Bearer test-token"


@pytest.mark.asyncio
@respx.mock
async def test_write_unit_summary_404_unit_not_found():
    respx.patch(WRITE_URL).mock(
        return_value=Response(
            404,
            json={
                "name": "UNIT_NOT_FOUND",
                "code": "E16001",
                "error": "not found",
                "statusCode": 404,
            },
        )
    )
    outcome = await UnitTicketClient().write_unit_summary("unit-1", "summary")
    assert outcome.kind == "unit_not_found"


@pytest.mark.asyncio
@respx.mock
async def test_write_unit_summary_network_error_is_an_error_outcome():
    respx.patch(WRITE_URL).mock(side_effect=httpx.ConnectError("connection failed"))
    outcome = await UnitTicketClient().write_unit_summary("unit-1", "summary")
    assert outcome.kind == "error"


def _report():
    return UnitRCAReport(
        problem_definition="Compressor short-cycles every 4 minutes.",
        cause_identification="Low refrigerant charge from a pinhole leak.",
        preventive_action="Add leak-check to the 6-month PM checklist.",
    )


@pytest.mark.asyncio
@respx.mock
async def test_write_ticket_rca_sends_flattened_body():
    route = respx.patch(RCA_URL).mock(return_value=Response(200, json={"message": "ok"}))
    outcome = await UnitTicketClient().write_ticket_rca("tk-1", _report())
    assert outcome.kind == "ok"

    import json

    request = route.calls.last.request
    # The body is flattened with an rcaReportInfo prefix, and "preventine" is a typo
    # baked into the wire contract — it must go out exactly as misspelled.
    assert json.loads(request.content) == {
        "rcaReportInfoProblemDefinition": "Compressor short-cycles every 4 minutes.",
        "rcaReportInfoCauseIdentification": "Low refrigerant charge from a pinhole leak.",
        "rcaReportInfoPreventineActionIdentification": (
            "Add leak-check to the 6-month PM checklist."
        ),
    }
    assert request.headers["Authorization"] == "Bearer test-token"


@pytest.mark.asyncio
@respx.mock
async def test_write_ticket_rca_404_ticket_not_found():
    respx.patch(RCA_URL).mock(
        return_value=Response(
            404,
            json={
                "name": "FIELD_SERVICE_TICKET_NOT_FOUND",
                "code": "E16002",
                "error": "not found",
                "statusCode": 404,
            },
        )
    )
    outcome = await UnitTicketClient().write_ticket_rca("tk-1", _report())
    assert outcome.kind == "ticket_not_found"


@pytest.mark.asyncio
@respx.mock
async def test_write_ticket_rca_unexpected_status_is_an_error_outcome():
    respx.patch(RCA_URL).mock(return_value=Response(500, json={}))
    outcome = await UnitTicketClient().write_ticket_rca("tk-1", _report())
    assert outcome.kind == "error"


@pytest.mark.asyncio
@respx.mock
async def test_write_ticket_rca_network_error_is_an_error_outcome():
    respx.patch(RCA_URL).mock(side_effect=httpx.ConnectError("connection failed"))
    outcome = await UnitTicketClient().write_ticket_rca("tk-1", _report())
    assert outcome.kind == "error"
