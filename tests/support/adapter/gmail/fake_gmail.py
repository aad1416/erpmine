"""An in-memory Gmail API for the Gmail adapter's Seam 1 tests: one `FakeGmailMailbox`
per address, each with its history, messages and threads, reached through
`FakeGmail.factory` in place of `GmailClient`."""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from email.message import EmailMessage

from app.support.adapter.gmail.client import GmailCredentialsConfig, HistoryExpiredError


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


class FakeGmailMailbox:
    """One Gmail account. Set `fail` to make every call raise it (e.g. a RefreshError for
    a revoked token), `watch_error` to make only users.watch() raise, and
    `fetch_errors[message_id]` to make fetching that message raise that many times."""

    def __init__(self, address: str, history_id: int = 100) -> None:
        self.address = address
        self.history_id = history_id
        self.oldest_history_id = 0  # a startHistoryId below this has expired
        self.records: list[dict] = []
        self.messages: dict[str, dict] = {}
        self.thread_order: list[str] = []  # message IDs in the order they arrived
        self.sent: list[tuple[EmailMessage, str | None]] = []
        self.watches: list[str] = []
        self.history_reads = 0
        self.fetches: list[str] = []
        self.fail: Exception | None = None
        self.watch_error: Exception | None = None
        self.send_error: Exception | None = None
        self.send_error_after_sending = False  # the call fails, but Gmail sent it
        self.fetch_errors: dict[str, int] = {}
        self.credentials: GmailCredentialsConfig | None = None

    def receive(
        self,
        message_id: str,
        thread_id: str = "thread-1",
        sender: str = "Jane Doe <jane@example.com>",
        subject: str = "Compressor noise",
        body: str = "The unit is making noise.",
        labels: tuple[str, ...] = ("INBOX", "UNREAD"),
        rfc_message_id: str | None = None,
        references: str | None = None,
    ) -> None:
        headers = [
            {"name": "From", "value": sender},
            {"name": "Subject", "value": subject},
            {"name": "Message-ID", "value": rfc_message_id or f"<{message_id}@example.com>"},
        ]
        if references:
            headers.append({"name": "References", "value": references})
        self._add(
            {
                "id": message_id,
                "threadId": thread_id,
                "labelIds": list(labels),
                "internalDate": "1700000000000",
                "payload": {
                    "headers": headers,
                    "mimeType": "text/plain",
                    "body": {"data": _b64(body)},
                },
            }
        )

    def _add(self, raw_message: dict) -> None:
        self.history_id += 1
        self.messages[raw_message["id"]] = raw_message
        self.thread_order.append(raw_message["id"])
        self.records.append(
            {
                "id": str(self.history_id),
                "messagesAdded": [
                    {"message": {"id": raw_message["id"], "threadId": raw_message["threadId"]}}
                ],
            }
        )

    def sent_in(self, thread_id: str) -> list[EmailMessage]:
        return [message for message, sent_thread in self.sent if sent_thread == thread_id]


class FakeGmailClient:
    def __init__(self, mailbox: FakeGmailMailbox) -> None:
        self._mailbox = mailbox
        self.user_email = mailbox.address

    def _check(self) -> None:
        if self._mailbox.fail is not None:
            raise self._mailbox.fail

    def history_list(self, start_history_id: str) -> list[dict]:
        self._check()
        self._mailbox.history_reads += 1
        if int(start_history_id) < self._mailbox.oldest_history_id:
            raise HistoryExpiredError(start_history_id)
        return [record for record in self._mailbox.records if int(record["id"]) > int(start_history_id)]

    def get_current_history_id(self) -> str:
        self._check()
        return str(self._mailbox.history_id)

    def get_message_full(self, message_id: str) -> dict:
        self._check()
        self._mailbox.fetches.append(message_id)
        if self._mailbox.fetch_errors.get(message_id):
            self._mailbox.fetch_errors[message_id] -= 1
            raise RuntimeError("Gmail API unavailable")
        return self._mailbox.messages[message_id]

    def send_message(self, message: EmailMessage, thread_id: str | None) -> dict:
        self._check()
        if self._mailbox.send_error is not None and not self._mailbox.send_error_after_sending:
            raise self._mailbox.send_error
        self._mailbox.sent.append((message, thread_id))
        # Gmail files the reply in the thread and adds it to the history, labelled SENT.
        headers = [{"name": name, "value": value} for name, value in message.items()]
        sent_id = f"sent-{len(self._mailbox.sent)}"
        self._mailbox._add(
            {
                "id": sent_id,
                "threadId": thread_id,
                "labelIds": ["SENT"],
                "internalDate": "1700000001000",
                "payload": {"headers": headers, "mimeType": "text/plain", "body": {}},
            }
        )
        if self._mailbox.send_error is not None:
            raise self._mailbox.send_error
        return {"id": sent_id, "threadId": thread_id}

    def get_thread_metadata(self, thread_id: str, header_names: list[str]) -> dict:
        self._check()
        wanted = {name.lower() for name in header_names}
        thread_messages = [
            self._mailbox.messages[message_id]
            for message_id in self._mailbox.thread_order
            if self._mailbox.messages[message_id]["threadId"] == thread_id
        ]
        return {
            "id": thread_id,
            "messages": [
                {
                    "id": raw_message["id"],
                    "labelIds": raw_message["labelIds"],
                    "payload": {
                        "headers": [
                            header
                            for header in raw_message["payload"]["headers"]
                            if header["name"].lower() in wanted
                        ]
                    },
                }
                for raw_message in thread_messages
            ],
        }

    def watch(self, topic_name: str) -> dict:
        self._check()
        if self._mailbox.watch_error is not None:
            raise self._mailbox.watch_error
        self._mailbox.watches.append(topic_name)
        return {"historyId": str(self._mailbox.history_id), "expiration": "1900000000000"}


@dataclass
class FakeGmail:
    mailboxes: dict[str, FakeGmailMailbox] = field(default_factory=dict)

    def add(self, address: str, **options) -> FakeGmailMailbox:
        mailbox = FakeGmailMailbox(address, **options)
        self.mailboxes[address.lower()] = mailbox
        return mailbox

    def factory(
        self, credentials: GmailCredentialsConfig, user_email: str, timeout: float
    ) -> FakeGmailClient:
        mailbox = self.mailboxes[user_email]
        mailbox.credentials = credentials
        return FakeGmailClient(mailbox)
