from datetime import datetime
from enum import Enum
from typing import List, Optional, Union

from pydantic import BaseModel, Field


class ThreadStatus(str, Enum):
    """Derived, not stored — computed per request from Conversation + its
    IngestionTask rows (support_monitoring_service.derive_status). Checked in this
    precedence order; first match wins."""

    ticketed = "ticketed"
    escalated = "escalated"
    in_progress = "in_progress"
    awaiting_customer = "awaiting_customer"
    new = "new"


class ThreadSummary(BaseModel):
    adapter: str = Field(
        ..., description="The Mailbox's Connection Method, e.g. 'imap', 'gmail', 'mailtrap'"
    )
    mailbox: str = Field(..., description="The Mailbox address the thread came in to")
    source_id: str = Field(
        ...,
        deprecated=True,
        description="Deprecated: '<adapter>:<mailbox>', built from adapter and mailbox. "
        "Use those instead; kept only until the monitoring panel stops reading it.",
    )
    conversation_id: str
    sender_address: Optional[str] = Field(
        None, description="Most recent inbound sender address for this thread"
    )
    unit_serial: Optional[str] = None
    ticket_id: Optional[str] = None
    status: ThreadStatus
    needs_attention: bool = Field(
        ..., description="True if this thread has any dead_letter task, of any task_type"
    )
    last_activity_at: datetime
    message_count: int
    open_task_count: int
    dead_letter_task_count: int


class ThreadListResponse(BaseModel):
    items: List[ThreadSummary]
    total: int
    limit: int
    offset: int


class TimelineMessageEntry(BaseModel):
    kind: str = "message"
    id: str
    direction: str = Field(..., description="'inbound' or 'outbound'")
    sender_address: Optional[str] = None
    body_text: str
    external_message_id: Optional[str] = None
    received_at: datetime
    synced_to_ticket_log: bool


class MessageTaskSummary(BaseModel):
    """Normalized view of a `message`-task's payload (raw inbound NormalizedMessage
    JSON) so callers never have to parse the blob themselves."""

    sender_address: Optional[str] = None
    sender_name: Optional[str] = None
    subject: Optional[str] = None
    body_preview: Optional[str] = None
    external_message_id: Optional[str] = None


class TicketTaskSummary(BaseModel):
    """Normalized view of a `create_ticket`-task's payload."""

    unit_serial: Optional[str] = None
    issue_description: Optional[str] = None
    title: Optional[str] = None
    customer_message: Optional[str] = None


class TimelineTaskEntry(BaseModel):
    kind: str = "task"
    id: str
    task_type: str = Field(..., description="message | create_ticket | send_message")
    status: str = Field(..., description="open | running | done | dead_letter")
    attempt_count: int
    created_at: datetime
    updated_at: datetime
    heartbeat_at: Optional[datetime] = None
    last_error: Optional[str] = Field(
        None, description="Set on every failed attempt, not just the final one"
    )
    dead_letter_reason: Optional[str] = Field(
        None,
        description=(
            "Set for definitive dead-letters (409_without_ticket_id, STORE_NOT_FOUND, "
            "escalation_cap_exhausted) — absent for retry-exhaustion dead-letters, "
            "where last_error is the relevant field instead"
        ),
    )
    message_summary: Optional[MessageTaskSummary] = Field(
        None, description="Populated when task_type == 'message'"
    )
    ticket_args: Optional[TicketTaskSummary] = Field(
        None, description="Populated when task_type == 'create_ticket'"
    )
    outbound_text: Optional[str] = Field(
        None, description="Populated when task_type == 'send_message'"
    )


TimelineEntry = Union[TimelineMessageEntry, TimelineTaskEntry]


class ThreadDetail(BaseModel):
    adapter: str = Field(
        ..., description="The Mailbox's Connection Method, e.g. 'imap', 'gmail', 'mailtrap'"
    )
    mailbox: str = Field(..., description="The Mailbox address the thread came in to")
    source_id: str = Field(
        ...,
        deprecated=True,
        description="Deprecated: '<adapter>:<mailbox>', built from adapter and mailbox. "
        "Use those instead; kept only until the monitoring panel stops reading it.",
    )
    conversation_id: str
    unit_serial: Optional[str] = None
    issue_description: Optional[str] = None
    ticket_id: Optional[str] = None
    question_round_count: int
    serial_correction_attempt_count: int
    status: ThreadStatus
    needs_attention: bool
    created_at: datetime
    updated_at: datetime
    timeline: List[TimelineEntry]
