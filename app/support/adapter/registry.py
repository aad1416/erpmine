"""The Mailbox Registry: the running Mailbox Adapters, one per Connection Method, looked
up by adapter name.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.support.adapter.base import (
    MailboxAdapter,
    MessageSink,
    discover,
    registered_adapter_classes,
)
from app.support.adapter.mailbox_key import MailboxKey

logger = logging.getLogger(__name__)


class MailboxRegistry:
    def __init__(self, adapters: dict[str, MailboxAdapter]) -> None:
        self._adapters = adapters

    @classmethod
    def load(cls, db: Session) -> "MailboxRegistry":
        """Builds every registered adapter from its Mailbox Connection table, then
        refuses a Mailbox address found in two adapters' tables: a Mailbox uses exactly
        one Connection Method (ADR 0002)."""
        adapters: dict[str, MailboxAdapter] = {}
        for adapter_class in registered_adapter_classes().values():
            adapters[adapter_class.name] = adapter_class.load(db)
        _check_no_shared_mailboxes(db, adapters)
        return cls(adapters)

    def get(self, name: str) -> MailboxAdapter | None:
        return self._adapters.get(name)

    def __contains__(self, name: str) -> bool:
        return name in self._adapters

    async def start(self, sink: MessageSink) -> None:
        for adapter in self._adapters.values():
            await adapter.start(sink)
            logger.info("Mailbox Adapter %s started", adapter.name)

    async def stop(self) -> None:
        """Stops every adapter even if one fails to, so none is left running."""
        for adapter in self._adapters.values():
            try:
                await adapter.stop()
            except Exception:
                logger.exception("Mailbox Adapter %s failed to stop", adapter.name)

    def router(self) -> APIRouter:
        router = APIRouter()
        for adapter in self._adapters.values():
            adapter_router = adapter.router()
            if adapter_router is not None:
                router.include_router(adapter_router)
        return router


def configured_mailboxes(db: Session) -> list[MailboxKey]:
    """Every Mailbox in every adapter's Mailbox Connection table, by adapter name then
    address. Reads only the address column, so no credential is decrypted."""
    return sorted(
        (
            MailboxKey.of(adapter_name, mailbox)
            for adapter_name, adapter_class in discover().items()
            for mailbox in _mailbox_addresses(db, adapter_class.credentials_model)
        ),
        key=lambda mailbox_key: (mailbox_key.adapter, mailbox_key.mailbox),
    )


def _check_no_shared_mailboxes(db: Session, adapters: dict[str, MailboxAdapter]) -> None:
    adapter_names_by_mailbox: dict[str, list[str]] = {}
    for adapter in adapters.values():
        for mailbox in _mailbox_addresses(db, adapter.credentials_model):
            adapter_names_by_mailbox.setdefault(mailbox, []).append(adapter.name)
    shared = {
        mailbox: adapter_names
        for mailbox, adapter_names in adapter_names_by_mailbox.items()
        if len(adapter_names) > 1
    }
    if shared:
        details = "; ".join(
            f"{mailbox} in {', '.join(sorted(adapter_names))}"
            for mailbox, adapter_names in sorted(shared.items())
        )
        raise RuntimeError(
            "A Mailbox is configured for more than one Connection Method, which is not "
            f"supported (ADR 0002). Remove it from all but one: {details}"
        )


def _mailbox_addresses(db: Session, credentials_model: type) -> set[str]:
    """A Mailbox Connection table is keyed by the Mailbox address alone."""
    primary_key_columns = inspect(credentials_model).primary_key
    if len(primary_key_columns) != 1:
        raise RuntimeError(
            f"{credentials_model.__name__} must be keyed by the Mailbox address alone"
        )
    (address_column,) = primary_key_columns
    # Lower-cased, as MailboxKey stores addresses.
    return {address.lower() for (address,) in db.query(address_column).all()}
