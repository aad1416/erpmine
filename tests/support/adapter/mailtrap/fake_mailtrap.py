"""An in-memory Mailtrap Inbound Email API, standing in for `MailtrapClient`.

`FakeMailtrap` holds inboxes by inbox ID; `FakeMailtrap.client` has `MailtrapClient`'s
constructor signature, so a test patches it in for the real client. Pages are newest
first, paginated by `last_id`, as Mailtrap's are.
"""

from __future__ import annotations

from dataclasses import dataclass, field

PAGE_SIZE = 2


@dataclass
class FakeInbox:
    api_token: str
    messages: list[dict] = field(default_factory=list)  # oldest first
    replies: list[tuple[str, str]] = field(default_factory=list)
    list_calls: int = 0
    failing: bool = False

    def receive(
        self, message_id: str, received_at: str, thread_id: str | None = "t1"
    ) -> None:
        self.messages.append(
            {
                "id": message_id,
                "thread_id": thread_id,
                "from": "Customer <customer@example.com>",
                "subject": "Where is my order",
                "received_at": received_at,
                "text_body": f"body {message_id}",
                "html_body": None,
                "attachments": [],
            }
        )


class FakeMailtrapError(Exception):
    pass


class FakeMailtrap:
    def __init__(self) -> None:
        self.inboxes: dict[str, FakeInbox] = {}

    def add_inbox(self, inbox_id: str, api_token: str) -> FakeInbox:
        inbox = FakeInbox(api_token=api_token)
        self.inboxes[inbox_id] = inbox
        return inbox

    def client(self, api_token: str, inbox_id: str) -> "FakeMailtrapClient":
        return FakeMailtrapClient(self, api_token, inbox_id)


class FakeMailtrapClient:
    def __init__(self, api: FakeMailtrap, api_token: str, inbox_id: str) -> None:
        self._api = api
        self._api_token = api_token
        self._inbox_id = inbox_id

    def _inbox(self) -> FakeInbox:
        inbox = self._api.inboxes.get(self._inbox_id)
        if inbox is None:
            raise FakeMailtrapError(f"404: no inbox {self._inbox_id}")
        if inbox.failing or inbox.api_token != self._api_token:
            raise FakeMailtrapError("401: invalid API token")
        return inbox

    async def list_messages(self, last_id: str | None = None) -> dict:
        inbox = self._api.inboxes.get(self._inbox_id)
        if inbox is not None:
            inbox.list_calls += 1
        inbox = self._inbox()
        newest_first = list(reversed(inbox.messages))
        start = 0
        if last_id is not None:
            start = [message["id"] for message in newest_first].index(last_id) + 1
        page = newest_first[start : start + PAGE_SIZE]
        more = start + PAGE_SIZE < len(newest_first)
        return {
            "data": [dict(message) for message in page],
            "last_id": page[-1]["id"] if page and more else None,
        }

    async def get_message(self, message_id: str) -> dict:
        for message in self._inbox().messages:
            if message["id"] == message_id:
                return dict(message)
        raise FakeMailtrapError(f"404: no message {message_id}")

    async def reply(self, message_id: str, text: str) -> dict:
        self._inbox().replies.append((message_id, text))
        return {"message_ids": [f"reply-to-{message_id}"]}
