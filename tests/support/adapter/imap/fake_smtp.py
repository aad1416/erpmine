"""Stand-in for `aiosmtplib.send`: records what would have gone over the wire. No
network, no SMTP server."""

from __future__ import annotations

from dataclasses import dataclass, field
from email.message import EmailMessage


@dataclass
class SentMail:
    message: EmailMessage
    sender: str
    recipients: list[str]
    options: dict


@dataclass
class FakeSmtp:
    sent: list[SentMail] = field(default_factory=list)
    fail_with: Exception | None = None
    # Runs inside send, before the message counts as delivered — to observe state then.
    on_send: object = None

    async def send(self, message, *, sender, recipients, **options):
        if self.on_send is not None:
            self.on_send(message)
        if self.fail_with is not None:
            raise self.fail_with
        self.sent.append(SentMail(message, sender, list(recipients), options))
        return {}, "OK"
