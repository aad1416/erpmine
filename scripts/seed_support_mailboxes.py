"""Copies the env-configured Support Email Mailboxes into the adapters' Mailbox
Connection tables (see app/support/adapter/seeding.py). Safe to run again: rows are
upserted by Mailbox address. Prints the adapter and Mailbox address of each row, never
credentials.

    poetry run python scripts/seed_support_mailboxes.py [--dry-run]
"""

import argparse
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.database import SessionLocal
from app.support.adapter.seeding import (
    Seeder,
    discover_seeders,
    seed_mailbox_connections,
)


def main(
    argv=None, session_factory=SessionLocal, seeders: dict[str, Seeder] | None = None
):
    parser = argparse.ArgumentParser(
        description="Copy the env-configured Support Email Mailboxes into the adapters' "
        "Mailbox Connection tables."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show what would be inserted or updated without writing anything",
    )
    args = parser.parse_args(argv)

    if seeders is None:
        seeders = discover_seeders()
    if not seeders:
        print("No Mailbox seeders registered: nothing to seed.")
        return

    db = session_factory()
    try:
        results = seed_mailbox_connections(db, seeders, dry_run=args.dry_run)
    finally:
        db.close()

    if not results:
        print("No Mailboxes configured in the environment: nothing to seed.")
        return

    prefix = "[dry run] " if args.dry_run else ""
    for result in results:
        print(f"{prefix}{result.action}: {result.adapter} {result.mailbox}")

    counts = {
        action: sum(1 for result in results if result.action == action)
        for action in ("inserted", "updated", "unchanged")
    }
    print(
        f"\nDone{' (dry run, nothing written)' if args.dry_run else ''}. "
        f"Inserted: {counts['inserted']}, Updated: {counts['updated']}, "
        f"Unchanged: {counts['unchanged']}."
    )


if __name__ == "__main__":
    main()
