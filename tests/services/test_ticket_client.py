"""Create Field Service Ticket By AI contract (04-ticket-api-contracts.md §0,
08-unit-test-strategy-checklist.md §7): all four response branches must be distinct."""

import pytest
import respx
from httpx import Response

from app.config.setting import settings
from app.services.ticket_client import TicketClient


@pytest.fixture(autouse=True)
def _ticket_api_settings(monkeypatch):
    monkeypatch.setattr(settings, "TICKET_API_BASE_URL", "https://api.example.com")
    monkeypatch.setattr(settings, "TICKET_API_BEARER_TOKEN", "test-token")


@pytest.mark.asyncio
@respx.mock
async def test_create_ticket_200_success():
    respx.post("https://api.example.com/store-panel/field-service-ticket/ai").mock(
        return_value=Response(200, json={"id": "tk-1", "number": "FS-100"})
    )
    outcome = await TicketClient().create_ticket(
        unit_serial="SN123",
        issue_description="broken",
        title="Broken unit",
        receiving_inbox_address="store@acme.com",
        conversation_id="test-conv-123",
    )
    assert outcome.kind == "created"
    assert outcome.ticket_id == "tk-1"
    assert outcome.ticket_number == "FS-100"


@pytest.mark.asyncio
@respx.mock
async def test_create_ticket_409_duplicate():
    respx.post("https://api.example.com/store-panel/field-service-ticket/ai").mock(
        return_value=Response(
            409,
            json={
                "name": "OPEN_FIELD_SERVICE_TICKET_ALREADY_EXISTS",
                "code": "E16003",
                "error": "Another Open Field Service Ticket For This Unit Already Exists",
                "statusCode": 409,
                "extraInfo": {
                    "existingFieldServiceTicket": {"id": "tk-old", "number": "FS-50", "status": "IN_PROGRESS"}
                },
            },
        )
    )
    outcome = await TicketClient().create_ticket(
        unit_serial="SN123",
        issue_description="broken",
        title="Broken unit",
        receiving_inbox_address="store@acme.com",
        conversation_id="test-conv-123",
    )
    assert outcome.kind == "duplicate"
    assert outcome.existing_ticket["number"] == "FS-50"


@pytest.mark.asyncio
@respx.mock
async def test_create_ticket_404_unit_not_found():
    respx.post("https://api.example.com/store-panel/field-service-ticket/ai").mock(
        return_value=Response(
            404,
            json={"errorName": "UNIT_NOT_FOUND", "errorCode": "E16001", "error": "not found"},
        )
    )
    outcome = await TicketClient().create_ticket(
        unit_serial="BADSN",
        issue_description="broken",
        title="Broken unit",
        receiving_inbox_address="store@acme.com",
        conversation_id="test-conv-123",
    )
    assert outcome.kind == "unit_not_found"


@pytest.mark.asyncio
@respx.mock
async def test_create_ticket_404_store_not_found_is_distinct_from_unit_not_found():
    respx.post("https://api.example.com/store-panel/field-service-ticket/ai").mock(
        return_value=Response(
            404,
            json={"errorName": "STORE_NOT_FOUND", "errorCode": "E06002", "error": "not found"},
        )
    )
    outcome = await TicketClient().create_ticket(
        unit_serial="SN123",
        issue_description="broken",
        title="Broken unit",
        receiving_inbox_address="unmapped@acme.com",
        conversation_id="test-conv-123",
    )
    assert outcome.kind == "store_not_found"
    assert outcome.kind != "unit_not_found"


@pytest.mark.asyncio
@respx.mock
async def test_create_ticket_sends_idempotency_key_header():
    route = respx.post("https://api.example.com/store-panel/field-service-ticket/ai").mock(
        return_value=Response(200, json={"id": "tk-1", "number": "FS-100"})
    )
    await TicketClient().create_ticket(
        unit_serial="SN123",
        issue_description="broken",
        title="Broken unit",
        receiving_inbox_address="store@acme.com",
        conversation_id="test-conv-123",
    )
    assert "x-id" in route.calls.last.request.headers


@pytest.mark.asyncio
@respx.mock
async def test_create_ticket_network_error_is_a_distinct_error_outcome():
    import httpx

    respx.post("https://api.example.com/store-panel/field-service-ticket/ai").mock(
        side_effect=httpx.ConnectError("connection failed")
    )
    outcome = await TicketClient().create_ticket(
        unit_serial="SN123",
        issue_description="broken",
        title="Broken unit",
        receiving_inbox_address="store@acme.com",
        conversation_id="test-conv-123",
    )
    assert outcome.kind == "error"
