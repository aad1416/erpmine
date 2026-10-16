"""Thin async httpx wrapper over Mailtrap's Inbound Email API
(11-mailtrap-adapter-plan.md §1). `Api-Token` header auth — no OAuth, unlike Gmail's
client.py. Uses `httpx.AsyncClient` directly (matches `app/services/ticket_client.py`'s
existing pattern) rather than a generated SDK, since Mailtrap has no Python client to reuse.
"""

from __future__ import annotations

import ipaddress
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

MAILTRAP_API_BASE_URL = "https://mailtrap.io"


def _validate_attachment_url(url: str) -> None:
    """Reject direct requests to local services and unsafe redirect targets."""
    parsed = urlparse(url)
    hostname = parsed.hostname
    if parsed.scheme != "https" or not hostname or parsed.username or parsed.password:
        raise ValueError("Mailtrap returned an invalid attachment URL")
    if parsed.port not in (None, 443):
        raise ValueError("Mailtrap returned an invalid attachment URL")
    if hostname == "localhost" or hostname.endswith((".localhost", ".local", ".internal")):
        raise ValueError("Mailtrap returned a local attachment URL")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return
    if not address.is_global:
        raise ValueError("Mailtrap returned a nonpublic attachment URL")


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

    async def download_attachment(self, download_url: str, max_bytes: int) -> bytes:
        """Fetch a signed provider URL with a decoded-size limit."""
        _validate_attachment_url(download_url)
        chunks = []
        received = 0
        transport = httpx.AsyncHTTPTransport(retries=2)
        async with httpx.AsyncClient(
            timeout=30.0, follow_redirects=False, transport=transport
        ) as client:
            current_url = download_url
            for _ in range(4):
                _validate_attachment_url(current_url)
                async with client.stream("GET", current_url) as response:
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            raise ValueError("Mailtrap attachment redirect had no location")
                        current_url = urljoin(current_url, location)
                        continue
                    response.raise_for_status()
                    async for chunk in response.aiter_bytes():
                        received += len(chunk)
                        if received > max_bytes:
                            raise ValueError("Mailtrap attachment exceeds the download limit")
                        chunks.append(chunk)
                    return b"".join(chunks)
            raise ValueError("Mailtrap attachment redirected too many times")

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
