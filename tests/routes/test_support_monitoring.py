"""Route-level tests for the support monitoring API — auth wiring, query param
plumbing, and the 404 case. Status-derivation and query business logic are covered by
tests/services/test_support_monitoring_service.py; these just prove the HTTP layer is
wired up correctly, using a minimal standalone app rather than app.main (which pulls
in scheduler/adapter startup wiring irrelevant to these routes)."""

from datetime import datetime, UTC

import pytest
from fastapi import FastAPI, HTTPException, status as http_status
from fastapi.testclient import TestClient

from app.db.models.Users import User
from app.dependencies.auth import get_admin_user
from app.dependencies.database import get_db
from app.dependencies.lyndom_db import get_lyndom_db
from app.repositories.conversation_messages import ConversationMessageRepository
from app.repositories.conversations import ConversationRepository
from app.routes.support_monitoring import router
from app.support.adapter.imap.models import ImapMailbox
from app.support.adapter.mailbox_key import MailboxKey
from app.support.adapter.mailtrap.models import MailtrapMailbox
from app.support.adapter.schemas import NormalizedMessage

# `resolve_store_mailboxes` still has its per-store lookup commented out, so every store
# resolves to every Mailbox in the adapters' tables — seed under that Mailbox, not the
# store's.
MAILBOX = MailboxKey("mailtrap", "support@inbound-mailtrap.io")
DETAIL_PATH = f"/support/monitoring/threads/{MAILBOX.adapter}/{MAILBOX.mailbox}"
STORE_EMAIL = "support@acme.com"


def _configure_mailtrap_inboxes(db_session, *addresses: str) -> None:
    """Replaces the Mailtrap Mailbox Connection rows the scope is read from."""
    db_session.query(MailtrapMailbox).delete()
    for address in addresses:
        db_session.add(MailtrapMailbox(mailbox=address, inbox_id="816"))
    db_session.commit()


@pytest.fixture(autouse=True)
def _configured_mailtrap_inbox(db_session):
    _configure_mailtrap_inboxes(db_session, MAILBOX.mailbox)


class _FakeLyndomDB:
    def __init__(self, email: str | None):
        self._email = email

    def get_store_email(self, store_id: str) -> str | None:
        return self._email


def _make_client(
    db_session, admin: bool = True, store_email: str | None = STORE_EMAIL
) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_lyndom_db] = lambda: _FakeLyndomDB(store_email)
    if admin:
        app.dependency_overrides[get_admin_user] = lambda: User(
            id="admin-1", name="Admin", username="admin", user_type="admin", store_id="store-1"
        )
    else:

        def _deny():
            raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="nope")

        app.dependency_overrides[get_admin_user] = _deny
    return TestClient(app)


def _seed_thread(db_session, conversation_id: str = "t1", mailbox_key: MailboxKey = MAILBOX):
    conversation = ConversationRepository(db_session).get_or_create(mailbox_key, conversation_id)
    ConversationMessageRepository(db_session).add_inbound(
        conversation,
        [
            NormalizedMessage(
                adapter=mailbox_key.adapter,
                mailbox=mailbox_key.mailbox,
                conversation_id=conversation_id,
                external_message_id="m1",
                sender_address="cust@x.com",
                received_at=datetime.now(UTC),
                body_text="help",
            )
        ],
    )
    return conversation


def test_list_threads_returns_seeded_thread(db_session):
    _seed_thread(db_session)
    client = _make_client(db_session)

    response = client.get("/support/monitoring/threads")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["conversation_id"] == "t1"
    assert (item["adapter"], item["mailbox"]) == ("mailtrap", "support@inbound-mailtrap.io")
    # Deprecated, built from adapter + mailbox for the monitoring panel outside this repo.
    assert item["source_id"] == "mailtrap:support@inbound-mailtrap.io"


def test_list_threads_filters_by_adapter_and_mailbox(db_session):
    _configure_mailtrap_inboxes(db_session, MAILBOX.mailbox, "second@inbound-mailtrap.io")
    _seed_thread(db_session, "t1")
    _seed_thread(db_session, "t2", MailboxKey("mailtrap", "second@inbound-mailtrap.io"))
    client = _make_client(db_session)

    by_mailbox = client.get(
        "/support/monitoring/threads",
        params={"adapter": "mailtrap", "mailbox": "second@inbound-mailtrap.io"},
    )
    other_adapter = client.get("/support/monitoring/threads", params={"adapter": "imap"})

    assert [item["conversation_id"] for item in by_mailbox.json()["items"]] == ["t2"]
    assert other_adapter.json()["items"] == []


def test_list_threads_includes_mailboxes_of_every_adapter(db_session):
    db_session.add(ImapMailbox(mailbox="help@shop.com", store_id="store-a"))
    db_session.commit()
    _seed_thread(db_session, "t1")
    _seed_thread(db_session, "t2", MailboxKey("imap", "help@shop.com"))
    client = _make_client(db_session)

    response = client.get("/support/monitoring/threads")

    assert {
        (item["adapter"], item["mailbox"], item["source_id"])
        for item in response.json()["items"]
    } == {
        ("mailtrap", MAILBOX.mailbox, MAILBOX.source_id),
        ("imap", "help@shop.com", "imap:help@shop.com"),
    }


def test_list_threads_scoped_to_caller_store_excludes_other_inboxes(db_session):
    """Threads belonging to a Mailbox the caller isn't scoped to must not be listed.
    Scoping is varied by the *resolved inbox* rather than by store_email: the per-store
    lookup is still commented out, so every store_email resolves to the same inbox and
    varying it would assert nothing."""
    _seed_thread(db_session)
    _configure_mailtrap_inboxes(db_session, "other@inbound-mailtrap.io")
    client = _make_client(db_session)

    response = client.get("/support/monitoring/threads")

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_list_threads_503_when_no_support_inbox_is_configured(db_session):
    _seed_thread(db_session)
    _configure_mailtrap_inboxes(db_session)
    client = _make_client(db_session, store_email=None)

    response = client.get("/support/monitoring/threads")

    assert response.status_code == 503


def test_get_thread_detail_returns_timeline(db_session):
    _seed_thread(db_session)
    client = _make_client(db_session)

    response = client.get(f"{DETAIL_PATH}/t1")

    assert response.status_code == 200
    body = response.json()
    assert body["conversation_id"] == "t1"
    assert (body["adapter"], body["mailbox"]) == ("mailtrap", "support@inbound-mailtrap.io")
    assert len(body["timeline"]) == 1
    assert body["timeline"][0]["kind"] == "message"


def test_get_thread_detail_404_for_unknown_thread(db_session):
    client = _make_client(db_session)

    response = client.get(f"{DETAIL_PATH}/does-not-exist")

    assert response.status_code == 404


def test_get_thread_detail_404_for_thread_outside_the_resolved_inbox(db_session):
    """Requesting a Mailbox the caller isn't scoped to must 404, not leak the thread.
    Asserted against a *different* inbox id rather than a different store_email, since
    every store currently resolves to the same inbox (the per-store lookup is still
    commented out) — which would make a store_email-based check pass vacuously."""
    _seed_thread(db_session)
    client = _make_client(db_session)

    response = client.get("/support/monitoring/threads/mailtrap/other@inbound-mailtrap.io/t1")

    assert response.status_code == 404


def test_get_thread_detail_404_for_the_same_address_on_another_adapter(db_session):
    _seed_thread(db_session)
    client = _make_client(db_session)

    response = client.get(f"/support/monitoring/threads/imap/{MAILBOX.mailbox}/t1")

    assert response.status_code == 404


def test_deprecated_source_id_detail_path_still_resolves(db_session):
    _seed_thread(db_session)
    client = _make_client(db_session)

    found = client.get(f"/support/monitoring/threads/{MAILBOX.source_id}/t1")
    out_of_scope = client.get("/support/monitoring/threads/mailtrap:other@inbound-mailtrap.io/t1")

    assert found.status_code == 200
    assert found.json()["mailbox"] == MAILBOX.mailbox
    assert out_of_scope.status_code == 404


def test_get_thread_detail_503_when_no_support_inbox_is_configured(db_session):
    _seed_thread(db_session)
    _configure_mailtrap_inboxes(db_session)
    client = _make_client(db_session, store_email=None)

    response = client.get(f"{DETAIL_PATH}/t1")

    assert response.status_code == 503


def test_routes_reject_non_admin_user(db_session):
    client = _make_client(db_session, admin=False)

    response = client.get("/support/monitoring/threads")

    assert response.status_code == 403
