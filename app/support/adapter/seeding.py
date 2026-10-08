"""Copies env-configured Mailboxes into the adapters' Mailbox Connection tables.

Each adapter folder may have a `seed.py` that registers one seeder:

    @seeder("imap")
    def seed_imap_mailboxes() -> list[ImapMailbox]:
        return [ImapMailbox(mailbox=..., app_password=...)]

A seeder reads its adapter's settings and returns unsaved rows. `seed_mailbox_connections`
upserts them by primary key (the Mailbox address), so running it twice changes nothing.
Only the attributes a seeder set are compared and written: a column it leaves out, like
the adapter's cursor, keeps its stored value on update.

Run it with `scripts/seed_support_mailboxes.py`.
"""

from __future__ import annotations

import importlib
import importlib.util
import pkgutil
from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy import inspect
from sqlalchemy.orm import Session

import app.support.adapter as adapter_package

Seeder = Callable[[], list[Any]]

_seeders: dict[str, Seeder] = {}


def seeder(adapter_name: str) -> Callable[[Seeder], Seeder]:
    def register(seed_function: Seeder) -> Seeder:
        if adapter_name in _seeders:
            raise ValueError(f"a Mailbox seeder is already registered for {adapter_name!r}")
        _seeders[adapter_name] = seed_function
        return seed_function

    return register


def discover_seeders() -> dict[str, Seeder]:
    """Imports every adapter folder's `seed` module, if it has one, and returns the
    registered seeders by adapter name."""
    for module_info in pkgutil.iter_modules(adapter_package.__path__):
        if not module_info.ispkg:
            continue
        seed_module_name = f"{adapter_package.__name__}.{module_info.name}.seed"
        if importlib.util.find_spec(seed_module_name) is not None:
            importlib.import_module(seed_module_name)
    return dict(_seeders)


@dataclass(frozen=True)
class SeedResult:
    """One seeded Mailbox. Carries no column values, so it's safe to print."""

    adapter: str
    mailbox: str
    action: str  # "inserted" | "updated" | "unchanged"


def seed_mailbox_connections(
    session: Session, seeders: dict[str, Seeder], dry_run: bool = False
) -> list[SeedResult]:
    """Upserts every seeder's rows and commits, or on `dry_run` only reports what it
    would do and writes nothing."""
    results: list[SeedResult] = []
    for adapter_name, seed_function in seeders.items():
        for row in seed_function():
            results.append(_upsert(session, adapter_name, row, dry_run))
    if dry_run:
        session.rollback()
    else:
        session.commit()
    return results


def _upsert(session: Session, adapter_name: str, row: Any, dry_run: bool) -> SeedResult:
    row_state = inspect(row)
    identity = row_state.mapper.primary_key_from_instance(row)
    if any(key_value is None for key_value in identity):
        raise ValueError(
            f"{adapter_name!r} seeder returned a {type(row).__name__} without its "
            "Mailbox address"
        )
    mailbox = "/".join(str(key_value) for key_value in identity)
    # Only what the seeder set, not the columns it left to their defaults.
    seeded_values = {
        column_attribute.key: row_state.dict[column_attribute.key]
        for column_attribute in row_state.mapper.column_attrs
        if column_attribute.key in row_state.dict
    }

    existing = session.get(type(row), identity)
    if existing is None:
        if not dry_run:
            session.add(row)
        return SeedResult(adapter_name, mailbox, "inserted")

    changed_values = {
        attribute_name: value
        for attribute_name, value in seeded_values.items()
        if getattr(existing, attribute_name) != value
    }
    if not changed_values:
        return SeedResult(adapter_name, mailbox, "unchanged")
    if not dry_run:
        for attribute_name, value in changed_values.items():
            setattr(existing, attribute_name, value)
    return SeedResult(adapter_name, mailbox, "updated")
