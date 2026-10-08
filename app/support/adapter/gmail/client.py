"""Thin wrapper around the Gmail API for one Mailbox (02-architecture-decisions.md §12.4,
§11.2). Its calls block, so the adapter runs them off the event loop.

Credentials are built once, behind one function, from the Mailbox's OAuth refresh token
and the app-wide OAuth client. Kept behind `_build_credentials` so swapping to a
service-account/domain-wide-delegation flow later is a one-function change, not a rewrite
of the adapter.
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any

import httplib2
from google.oauth2.credentials import Credentials
from google_auth_httplib2 import AuthorizedHttp
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


class HistoryExpiredError(Exception):
    """Raised when Gmail's stored historyId is too old to resume from (§11.2)."""


@dataclass
class GmailCredentialsConfig:
    client_id: str
    client_secret: str
    refresh_token: str


def _build_credentials(config: GmailCredentialsConfig) -> Credentials:
    return Credentials(
        token=None,
        refresh_token=config.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=config.client_id,
        client_secret=config.client_secret,
        scopes=GMAIL_SCOPES,
    )


class GmailClient:
    def __init__(self, config: GmailCredentialsConfig, user_email: str, timeout: float):
        self._config = config
        self.user_email = user_email
        self._timeout = timeout
        self._service = None

    def _get_service(self):
        if self._service is None:
            authorized_http = AuthorizedHttp(
                _build_credentials(self._config), http=httplib2.Http(timeout=self._timeout)
            )
            self._service = build("gmail", "v1", http=authorized_http, cache_discovery=False)
        return self._service

    def history_list(self, start_history_id: str) -> list[dict[str, Any]]:
        """Returns raw history records since `start_history_id`. Raises
        HistoryExpiredError if Gmail no longer has history that far back."""
        service = self._get_service()
        records: list[dict[str, Any]] = []
        page_token = None
        try:
            while True:
                response = (
                    service.users()
                    .history()
                    .list(
                        userId="me",
                        startHistoryId=start_history_id,
                        historyTypes=["messageAdded"],
                        pageToken=page_token,
                    )
                    .execute()
                )
                records.extend(response.get("history", []))
                page_token = response.get("nextPageToken")
                if not page_token:
                    break
        except HttpError as exc:
            if exc.resp.status == 404:
                raise HistoryExpiredError(str(exc)) from exc
            raise
        return records

    def get_current_history_id(self) -> str:
        service = self._get_service()
        profile = service.users().getProfile(userId="me").execute()
        return profile["historyId"]

    def get_message_full(self, message_id: str) -> dict[str, Any]:
        service = self._get_service()
        return (
            service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )

    def send_message(self, message: EmailMessage, thread_id: str | None) -> dict[str, Any]:
        service = self._get_service()
        body: dict[str, Any] = {"raw": base64.urlsafe_b64encode(message.as_bytes()).decode()}
        if thread_id:
            body["threadId"] = thread_id
        return service.users().messages().send(userId="me", body=body).execute()

    def get_thread_metadata(self, thread_id: str, header_names: list[str]) -> dict[str, Any]:
        """The thread's messages, oldest first, each with its `labelIds` and only the
        named headers."""
        service = self._get_service()
        return (
            service.users()
            .threads()
            .get(userId="me", id=thread_id, format="metadata", metadataHeaders=header_names)
            .execute()
        )

    def watch(self, topic_name: str) -> dict[str, Any]:
        service = self._get_service()
        return (
            service.users()
            .watch(userId="me", body={"topicName": topic_name, "labelIds": ["INBOX"]})
            .execute()
        )

