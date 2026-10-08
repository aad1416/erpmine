"""The one place a Mailbox's identity is built: its adapter name and its address."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MailboxKey:
    adapter: str
    mailbox: str

    def __post_init__(self) -> None:
        # Fail here rather than route a reply to an empty adapter or address.
        if not self.adapter or not self.mailbox:
            raise ValueError(
                f"a Mailbox needs an adapter and an address: {self.adapter!r}, {self.mailbox!r}"
            )

    @classmethod
    def of(cls, adapter: str, address: str) -> "MailboxKey":
        """Mailbox addresses are stored lower-cased."""
        return cls(adapter=adapter, mailbox=address.lower())

    @property
    def source_id(self) -> str:
        """Deprecated: the retired `"<adapter>:<mailbox>"` form. Only support monitoring
        uses it, for the monitoring panel outside this repo that still builds URLs from
        it. Nothing stores or parses it."""
        return f"{self.adapter}:{self.mailbox}"
