"""The Mailbox Adapter contract, its registration decorator and adapter discovery.

One Mailbox Adapter instance runs per Connection Method and serves every Mailbox in its
Mailbox Connection table. An adapter folder registers its class with a decorator:

    @adapter("imap", credentials=ImapMailbox)
    class ImapAdapter(MailboxAdapter):
        ...

`discover()` imports every adapter folder's `adapter` module, so adding a Connection
Method never means editing a registration list. A subclass that isn't decorated, such as
a test fake, is never registered.

Delivery contract: an adapter hands each message to the sink given to `start` at least
once, and treats a message as handed over only after the sink returns. Whether it keeps
an outbox to meet that is the adapter's own choice.
"""

from __future__ import annotations

import importlib
import importlib.util
import pkgutil
from abc import ABC, abstractmethod
from types import ModuleType
from typing import Any, Awaitable, Callable, ClassVar

from fastapi import APIRouter
from sqlalchemy.orm import Session

import app.support.adapter as adapter_package
from app.support.adapter.schemas import NormalizedMessage

MessageSink = Callable[[NormalizedMessage], Awaitable[None]]

_adapter_classes: dict[str, type["MailboxAdapter"]] = {}


class MailboxAdapter(ABC):
    """`name` and `credentials_model` are set by the `@adapter` decorator."""

    name: ClassVar[str]
    credentials_model: ClassVar[type]

    @classmethod
    def load(cls, db: Session) -> "MailboxAdapter":
        """Builds the one instance from every row of the Mailbox Connection table. An
        empty table still gives an instance, serving no Mailboxes."""
        return cls(db.query(cls.credentials_model).all())

    @abstractmethod
    def __init__(self, credential_rows: list[Any]) -> None:
        """Must not connect to a Mail Provider: that happens in `start`."""

    @abstractmethod
    async def start(self, sink: MessageSink) -> None:
        """Begins receiving for every Mailbox. Polling, push or both is the adapter's
        choice, and one Mailbox failing must not stop the others."""

    @abstractmethod
    async def stop(self) -> None:
        """Stops receiving and releases connections."""

    @abstractmethod
    async def send_message(
        self, mailbox: str, conversation_id: str, text: str, idempotency_key: str
    ) -> None:
        """Sends a reply from `mailbox` in `conversation_id`. A repeated
        `idempotency_key` must not reach the customer twice."""

    def router(self) -> APIRouter | None:
        """The adapter's HTTP routes, such as a push webhook, or None."""
        return None


def adapter(name: str, *, credentials: type) -> Callable[[type[MailboxAdapter]], type[MailboxAdapter]]:
    def register(adapter_class: type[MailboxAdapter]) -> type[MailboxAdapter]:
        if name in _adapter_classes:
            raise ValueError(
                f"Mailbox Adapter name {name!r} is registered twice: by "
                f"{_adapter_classes[name].__qualname__} and {adapter_class.__qualname__}"
            )
        adapter_class.name = name
        adapter_class.credentials_model = credentials
        _adapter_classes[name] = adapter_class
        return adapter_class

    return register


def registered_adapter_classes() -> dict[str, type[MailboxAdapter]]:
    return dict(_adapter_classes)


def discover(package: ModuleType = adapter_package) -> dict[str, type[MailboxAdapter]]:
    """Imports each sub-package's `adapter` module and returns every registered adapter
    class by name. A folder without an `adapter` module (a placeholder) is skipped; one
    whose `adapter` module registered nothing raises, so a forgotten decorator can't
    silently disable a Connection Method."""
    for module_info in pkgutil.iter_modules(package.__path__):
        if not module_info.ispkg:
            continue
        adapter_module_name = f"{package.__name__}.{module_info.name}.adapter"
        if importlib.util.find_spec(adapter_module_name) is None:
            continue
        importlib.import_module(adapter_module_name)
        # By module rather than a before/after count, so a second discover() doesn't
        # mistake an already-imported module for an empty one.
        if not any(
            adapter_class.__module__ == adapter_module_name
            for adapter_class in _adapter_classes.values()
        ):
            raise RuntimeError(
                f"{adapter_module_name} registered no Mailbox Adapter: decorate its "
                "adapter class with @adapter(<name>, credentials=<Mailbox Connection model>)"
            )
    return registered_adapter_classes()
