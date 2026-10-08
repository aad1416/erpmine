"""FieldServiceTicketMessage has three senderType values but only two sender shapes
(field-service-ticket-message.md): 'Employee' and 'AI Agent' both carry an employee-shaped
sender, so the display name must be read off the sender union's shape while the role comes
from senderType."""

from app.prompts.field_service_ticket_summary import (
    get_field_service_ticket_summary_prompt,
)
from app.schemas.field_service_ticket_summary import (
    FieldServiceTicket,
    FieldServiceTicketMessageRole,
)


def _message(sender, sender_type, text="hello"):
    return {
        "id": "m-1",
        "sender": sender,
        "senderType": sender_type,
        "fieldServiceTicketId": "tk-1",
        "date": 1754000000000,
        "text": text,
        "hasFile": False,
    }


def _ticket(**overrides):
    base = {"id": "tk-1", "title": "Compressor", "description": "desc"}
    base.update(overrides)
    return FieldServiceTicket.model_validate(base)


def test_employee_sender_uses_full_name():
    ticket = _ticket(
        messages=[
            _message({"id": "u-1", "username": "jdoe", "fullName": "Jane Doe"}, "Employee")
        ]
    )
    message = ticket.messages[0]
    assert message.sender_name == "Jane Doe"
    assert message.role is FieldServiceTicketMessageRole.employee


def test_client_sender_uses_name():
    ticket = _ticket(messages=[_message({"id": "c-1", "name": "Acme Corp"}, "Client")])
    message = ticket.messages[0]
    assert message.sender_name == "Acme Corp"
    assert message.role is FieldServiceTicketMessageRole.client


def test_ai_agent_shares_employee_sender_shape_but_gets_ai_role():
    ticket = _ticket(
        messages=[
            _message({"id": "u-9", "username": "ai", "fullName": "AI Agent"}, "AI Agent")
        ]
    )
    message = ticket.messages[0]
    assert message.sender_name == "AI Agent"
    assert message.role is FieldServiceTicketMessageRole.ai


def test_missing_messages_key_parses_to_empty_list():
    # A ticket with no thread yet omits the key rather than sending [].
    assert _ticket().messages == []


def test_unit_serial_number_is_read_from_wire_field():
    assert _ticket(unitSerialNumber="SN-1").unit_serial_number == "SN-1"


def test_extra_wire_fields_are_ignored():
    ticket = _ticket(storeId="st-1", severity="HIGH", rcaReportInfo={})
    assert ticket.id == "tk-1"


def test_prompt_falls_back_to_unit_id_when_no_tickets_carry_a_serial():
    prompt = get_field_service_ticket_summary_prompt(unit_id="unit-1", tickets=[_ticket()])
    assert "unit unit-1" in prompt


def test_prompt_renders_title_in_ticket_heading():
    prompt = get_field_service_ticket_summary_prompt(unit_id="unit-1", tickets=[_ticket()])
    assert "### Ticket tk-1 — Compressor" in prompt
