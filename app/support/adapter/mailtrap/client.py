"""Thin async httpx wrapper over Mailtrap's Inbound Email API
(11-mailtrap-adapter-plan.md §1). `Api-Token` header auth — no OAuth, unlike Gmail's
client.py. Uses `httpx.AsyncClient` directly (matches `app/services/ticket_client.py`'s
existing pattern) rather than a generated SDK, since Mailtrap has no Python client to reuse.
"""

from __future__ import annotations

from typing import Any

import httpx

MAILTRAP_API_BASE_URL = "https://mailtrap.io"


class MailtrapClient:
    def __init__(self, api_token: str, inbox_id: str):
        self._api_token = api_token
        self._inbox_id = inbox_id

    def _headers(self) -> dict[str, str]:
        return {"Api-Token": self._api_token}

    async def list_messages(self, last_id: str | None = None) -> dict[str, Any]:
        """Newest-first, cursor-paginated via `last_id` (11-mailtrap-adapter-plan.md §1)."""
        params = {"last_id": last_id} if last_id else None
        async with httpx.AsyncClient(base_url=MAILTRAP_API_BASE_URL, timeout=15.0) as client:
            response = await client.get(
                f"/api/inbound/inboxes/{self._inbox_id}/messages",
                params=params,
                headers=self._headers(),
            )
            response.raise_for_status()
            return response.json()

    async def get_message(self, message_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=MAILTRAP_API_BASE_URL, timeout=15.0) as client:
            response = await client.get(
                f"/api/inbound/inboxes/{self._inbox_id}/messages/{message_id}",
                headers=self._headers(),
            )
            response.raise_for_status()
            return response.json()

    async def reply(self, message_id: str, text: str) -> dict[str, Any]:
        """Threads to `message_id`, subject auto-prefixed `Re:` by Mailtrap, defaults to
        replying to the original sender. `from` is omitted — Mailtrap rejects it for
        Mailtrap-hosted inboxes, which this adapter always uses."""
        async with httpx.AsyncClient(base_url=MAILTRAP_API_BASE_URL, timeout=15.0) as client:
            response = await client.post(
                f"/api/inbound/inboxes/{self._inbox_id}/messages/{message_id}/reply",
                json={"text": text},
                headers=self._headers(),
            )
            response.raise_for_status()
            return response.json()

    async def delete_message(self, message_id: str) -> None:
        async with httpx.AsyncClient(base_url=MAILTRAP_API_BASE_URL, timeout=15.0) as client:
            response = await client.delete(
                f"/api/inbound/inboxes/{self._inbox_id}/messages/{message_id}",
                headers=self._headers(),
            )
            response.raise_for_status()
