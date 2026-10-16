"""Wraps the confirmed Create Field Service Ticket By AI contract
(app/support/04-ticket-api-contracts.md §0). Maps its four documented outcomes to four
distinct return values so the caller can't conflate them (§7.2)."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

import httpx

from app.config.email_attachments import (
    TICKET_ATTACHMENT_OWNER_TYPE,
    TICKET_ATTACHMENT_UPLOAD_PATH,
)
from app.config.setting import settings

logger = logging.getLogger(__name__)

TicketOutcomeKind = Literal[
    "created", "duplicate", "unit_not_found", "store_not_found", "error"
]


@dataclass
class TicketOutcome:
    kind: TicketOutcomeKind
    ticket_id: Optional[str] = None
    ticket_number: Optional[str] = None
    existing_ticket: Optional[dict] = None
    error_detail: Optional[str] = None


TicketAttachmentOutcomeKind = Literal["uploaded", "rejected", "error"]


@dataclass
class TicketAttachmentOutcome:
    kind: TicketAttachmentOutcomeKind
    ticket_file_id: Optional[str] = None
    error_detail: Optional[str] = None


class TicketClient:
    def __init__(self) -> None:
        self._base_url = settings.TICKET_API_BASE_URL
        self._token = settings.TICKET_API_BEARER_TOKEN

    async def create_ticket(
        self,
        *,
        unit_serial: str,
        issue_description: str,
        title: str,
        receiving_inbox_address: str,
        conversation_id: str,
    ) -> TicketOutcome:
        # Stable per conversation so task reclaim retries send the same x-id and the
        # API deduplicates correctly rather than creating a second ticket.
        idempotency_key = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL, f"{conversation_id}:{unit_serial}:create_ticket"
            )
        )
        body = {
            "description": issue_description,
            "title": title,
            "unitSerialNumber": unit_serial,
            "receivingInboxAddress": receiving_inbox_address,
        }
        headers = {
            "Authorization": f"Bearer {self._token}",
            "x-id": idempotency_key,
        }

        transport = httpx.AsyncHTTPTransport(retries=2)
        async with httpx.AsyncClient(
            base_url=self._base_url, timeout=15.0, transport=transport
        ) as client:
            try:
                response = await client.post(
                    "/store-panel/field-service-ticket/ai", json=body, headers=headers
                )
            except httpx.HTTPError as exc:
                logger.exception("Create ticket request failed")
                return TicketOutcome(kind="error", error_detail=str(exc))

        return self._parse_response(response)

    async def attach_file(
        self,
        *,
        ticket_id: str,
        attachment_id: str,
        file_name: str,
        content_type: str,
        file_path: str,
    ) -> TicketAttachmentOutcome:
        """Upload one original after ticket creation using a stable retry key."""
        path = Path(file_path)
        if not path.is_file():
            return TicketAttachmentOutcome(
                kind="rejected", error_detail="The canonical attachment is missing."
            )
        headers = {
            "Authorization": f"Bearer {self._token}",
            "x-id": str(uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"{ticket_id}:{attachment_id}:attach_ticket_file",
            )),
        }
        endpoint = TICKET_ATTACHMENT_UPLOAD_PATH.format(
            owner_type=TICKET_ATTACHMENT_OWNER_TYPE, ticket_id=ticket_id
        )
        transport = httpx.AsyncHTTPTransport(retries=2)
        async with httpx.AsyncClient(
            base_url=self._base_url, timeout=60.0, transport=transport
        ) as client:
            try:
                with path.open("rb") as handle:
                    response = await client.post(
                        endpoint,
                        data={"title": file_name, "isVisibleToClient": "true"},
                        files={"file": (file_name, handle, content_type)},
                        headers=headers,
                    )
            except (OSError, httpx.HTTPError) as exc:
                logger.exception("Ticket attachment upload failed for %s", attachment_id)
                return TicketAttachmentOutcome(
                    kind="error", error_detail=str(exc) or type(exc).__name__
                )

        if response.status_code in {200, 201}:
            try:
                data = response.json()
                if isinstance(data, list):
                    data = data[0] if data else {}
                ticket_file_id = data.get("id") if isinstance(data, dict) else None
            except ValueError:
                ticket_file_id = None
            if not ticket_file_id:
                return TicketAttachmentOutcome(
                    kind="error", error_detail="Ticket API success omitted file id"
                )
            return TicketAttachmentOutcome(kind="uploaded", ticket_file_id=ticket_file_id)
        if response.status_code in {400, 413, 415, 422}:
            return TicketAttachmentOutcome(
                kind="rejected",
                error_detail=f"Ticket API rejected the file (status {response.status_code}).",
            )
        return TicketAttachmentOutcome(
            kind="error", error_detail=f"unexpected attachment status {response.status_code}"
        )

    def _parse_response(self, response: httpx.Response) -> TicketOutcome:
        if response.status_code == 200:
            data = response.json()
            if not data.get("id"):
                return TicketOutcome(kind="error", error_detail="ticket API success omitted id")
            return TicketOutcome(
                kind="created",
                ticket_id=data.get("id"),
                ticket_number=data.get("number"),
            )

        if response.status_code == 409:
            data = response.json()
            existing = data.get("extraInfo", {}).get("existingFieldServiceTicket", {})
            return TicketOutcome(kind="duplicate", existing_ticket=existing)

        if response.status_code == 404:
            data = response.json()
            name = data.get("errorName") or data.get("name")
            if name == "UNIT_NOT_FOUND":
                return TicketOutcome(kind="unit_not_found")
            if name == "STORE_NOT_FOUND":
                return TicketOutcome(kind="store_not_found")
            return TicketOutcome(kind="error", error_detail=data.get("error"))

        return TicketOutcome(
            kind="error", error_detail=f"unexpected status {response.status_code}"
        )
