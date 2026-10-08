"""Models for the field service ticket summary tool.

The ticket and message models parse the Lyndom wire shape returned by
`getUnitFieldServiceTicketsEndpointAI` (ai-endpoints.md) — camelCase, with extra fields
we ignore. Messages follow FieldServiceTicketMessage (field-service-ticket-message.md).
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FieldServiceTicketMessageRole(str, Enum):
    ai = "ai"
    employee = "employee"
    client = "client"


# senderType is the only way to tell an AI message from a human employee one — both
# carry an employee-shaped sender (field-service-ticket-message.md §Three senderType
# values, two sender shapes).
_SENDER_TYPE_TO_ROLE = {
    "Employee": FieldServiceTicketMessageRole.employee,
    "Client": FieldServiceTicketMessageRole.client,
    "AI Agent": FieldServiceTicketMessageRole.ai,
}

_UNKNOWN_SENDER_NAME = "Unknown"


class FieldServiceTicketMessage(BaseModel):
    """A single message in a ticket thread, flattened for prompt rendering."""

    model_config = ConfigDict(extra="ignore")

    sender_name: str
    role: FieldServiceTicketMessageRole
    text: str
    date: int = Field(description="Message timestamp as epoch milliseconds")
    has_file: bool = False

    @model_validator(mode="before")
    @classmethod
    def _from_wire(cls, data):
        """Flatten the wire message: resolve the sender union to one display name and
        map senderType onto our role enum."""
        if not isinstance(data, dict):
            return data

        # Already in internal shape (e.g. constructed directly in tests).
        if "sender_name" in data or "role" in data:
            return data

        sender = data.get("sender") or {}
        # The union has no shared display-name field: internal users carry `fullName`,
        # clients carry `name`. Narrow on the shape of `sender`, not on senderType —
        # nothing guarantees the two agree.
        if isinstance(sender, dict):
            sender_name = sender.get("fullName") or sender.get("name")
        else:
            sender_name = None

        sender_type = data.get("senderType")
        return {
            **data,
            "sender_name": sender_name or _UNKNOWN_SENDER_NAME,
            "role": _SENDER_TYPE_TO_ROLE.get(
                sender_type, FieldServiceTicketMessageRole.employee
            ),
            "has_file": data.get("hasFile", data.get("has_file", False)),
        }


class FieldServiceTicket(BaseModel):
    """A ticket as returned by the by-unit endpoint, reduced to what the prompt needs."""

    model_config = ConfigDict(extra="ignore")

    id: str
    title: str = ""
    description: str = ""
    unit_serial_number: str | None = None
    # Defaulted so a ticket with no thread yet still parses; it degrades to a
    # description-only summary rather than failing.
    messages: list[FieldServiceTicketMessage] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _from_wire(cls, data):
        if not isinstance(data, dict):
            return data
        if "unitSerialNumber" in data and "unit_serial_number" not in data:
            data = {**data, "unit_serial_number": data.get("unitSerialNumber")}
        return data


class FieldServiceTicketSummaryRequest(BaseModel):
    unit_id: str


class FieldServiceTicketSummaryResponse(BaseModel):
    detail: str
