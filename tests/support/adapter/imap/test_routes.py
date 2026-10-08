from __future__ import annotations

from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.config.setting import settings
from app.db.models.Users import User
from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.support.adapter.gmail.models import GmailMailbox
from app.support.adapter.imap.adapter import ImapAdapter
from app.support.adapter.imap.models import ImapMailbox
from app.support.adapter.mailtrap.models import MailtrapMailbox
from app.support.adapter.registry import MailboxRegistry


def _client(db_session, user: User) -> TestClient:
    app = FastAPI()
    app.include_router(MailboxRegistry({"imap": ImapAdapter.load(db_session)}).router())
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def _user(store_id="store-a", user_type="admin") -> User:
    return User(id="1", name="Admin", username="admin", store_id=store_id, user_type=user_type)


def test_create_read_isolation_encryption_and_startup_snapshot(db_session, monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "SUPPORT_CREDENTIALS_KEY", key)
    client = _client(db_session, _user())
    response = client.put(
        "/support/mailboxes/imap",
        json={"mailbox": "Help@Shop.com", "app_password": "secret"},
    )
    assert response.status_code == 201
    assert response.json() == {
        "mailbox": "help@shop.com",
        "imap_host": "imap.gmail.com", "imap_port": 993, "imap_tls_mode": "ssl",
        "smtp_host": "smtp.gmail.com", "smtp_port": 465, "smtp_tls_mode": "ssl",
        "restart_required": True,
    }
    assert client.get("/support/mailboxes/imap").json() == response.json()
    row = db_session.query(ImapMailbox).one()
    assert row.store_id == "store-a" and row.app_password == "secret" and row.cursor is None
    stored = db_session.connection().exec_driver_sql(
        "SELECT app_password FROM imap_mailboxes"
    ).scalar_one()
    assert stored != "secret" and "secret" not in stored
    monkeypatch.setattr(settings, "SUPPORT_CREDENTIALS_KEY", None)
    assert client.get("/support/mailboxes/imap").json() == response.json()
    monkeypatch.setattr(settings, "SUPPORT_CREDENTIALS_KEY", key)
    assert _client(db_session, _user("store-b")).get("/support/mailboxes/imap").status_code == 404
    assert client.put("/support/mailboxes/imap", json={
        "mailbox": "other@shop.com", "app_password": "new"
    }).status_code == 200
    assert db_session.query(ImapMailbox).count() == 1


def test_custom_settings_and_address_conflicts(db_session, monkeypatch):
    monkeypatch.setattr(settings, "SUPPORT_CREDENTIALS_KEY", Fernet.generate_key().decode())
    client = _client(db_session, _user())
    custom = {
        "mailbox": "other@shop.com", "app_password": "secret",
        "imap_host": "imap.example.com", "imap_port": 143, "imap_tls_mode": "starttls",
        "smtp_host": "smtp.example.com", "smtp_port": 587, "smtp_tls_mode": "starttls",
    }
    assert client.put("/support/mailboxes/imap", json=custom).status_code == 201
    assert client.get("/support/mailboxes/imap").json()["smtp_port"] == 587
    second = _client(db_session, _user("store-b"))
    assert second.put("/support/mailboxes/imap", json=custom).status_code == 409
    db_session.add_all([GmailMailbox(mailbox="gmail@shop.com"), MailtrapMailbox(mailbox="mailtrap@shop.com")])
    db_session.commit()
    for address in ("gmail@shop.com", "mailtrap@shop.com"):
        assert second.put("/support/mailboxes/imap", json={
            "mailbox": address, "app_password": "secret"
        }).status_code == 409


def test_admin_and_store_claim_required(db_session):
    payload = {"mailbox": "help@shop.com", "app_password": "secret"}
    for user in (_user(user_type="user"), _user(""), _user("   ")):
        client = _client(db_session, user)
        assert client.get("/support/mailboxes/imap").status_code == 403
        assert client.put("/support/mailboxes/imap", json=payload).status_code == 403
    assert db_session.query(ImapMailbox).count() == 0


def test_first_put_requires_address_and_password(db_session):
    client = _client(db_session, _user())
    for payload in ({"app_password": "secret"}, {"mailbox": "help@shop.com"}):
        assert client.put("/support/mailboxes/imap", json=payload).status_code == 422


def test_partial_update_preserves_omitted_values_credential_and_cursor(db_session, monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "SUPPORT_CREDENTIALS_KEY", key)
    client = _client(db_session, _user())
    assert client.put("/support/mailboxes/imap", json={
        "mailbox": "help@shop.com", "app_password": "original",
    }).status_code == 201
    row = db_session.query(ImapMailbox).one()
    row.cursor = "1:42"
    db_session.commit()
    ciphertext = db_session.connection().exec_driver_sql(
        "SELECT app_password FROM imap_mailboxes"
    ).scalar_one()

    response = client.put("/support/mailboxes/imap", json={
        "imap_host": " imap.example.com ", "imap_port": 143,
        "imap_tls_mode": "starttls", "smtp_host": "smtp.example.com",
        "smtp_port": 587, "smtp_tls_mode": "starttls",
    })
    assert response.status_code == 200
    assert response.json()["imap_host"] == "imap.example.com"
    assert response.json()["mailbox"] == "help@shop.com"
    assert db_session.query(ImapMailbox).one().cursor == "1:42"
    assert db_session.connection().exec_driver_sql(
        "SELECT app_password FROM imap_mailboxes"
    ).scalar_one() == ciphertext
    monkeypatch.setattr(settings, "SUPPORT_CREDENTIALS_KEY", None)
    assert client.put("/support/mailboxes/imap", json={"mailbox": "HELP@SHOP.COM"}).status_code == 200
    assert db_session.query(ImapMailbox.cursor).scalar() == "1:42"

    monkeypatch.setattr(settings, "SUPPORT_CREDENTIALS_KEY", key)
    assert client.put("/support/mailboxes/imap", json={"app_password": "replacement"}).status_code == 200
    assert db_session.query(ImapMailbox).one().app_password == "replacement"
    assert db_session.query(ImapMailbox).one().cursor == "1:42"
    assert "app_password" not in client.get("/support/mailboxes/imap").json()


def test_address_change_resets_cursor_and_conflicts_are_isolated(db_session, monkeypatch):
    monkeypatch.setattr(settings, "SUPPORT_CREDENTIALS_KEY", Fernet.generate_key().decode())
    first = _client(db_session, _user())
    second = _client(db_session, _user("store-b"))
    assert first.put("/support/mailboxes/imap", json={
        "mailbox": "first@shop.com", "app_password": "first-secret"
    }).status_code == 201
    assert second.put("/support/mailboxes/imap", json={
        "mailbox": "second@shop.com", "app_password": "second-secret"
    }).status_code == 201
    db_session.query(ImapMailbox).filter_by(store_id="store-a").one().cursor = "1:42"
    db_session.commit()

    assert first.put("/support/mailboxes/imap", json={"mailbox": "second@shop.com"}).status_code == 409
    db_session.add_all([GmailMailbox(mailbox="gmail@shop.com"), MailtrapMailbox(mailbox="mailtrap@shop.com")])
    db_session.commit()
    for address in ("gmail@shop.com", "mailtrap@shop.com"):
        assert first.put("/support/mailboxes/imap", json={"mailbox": address}).status_code == 409
    response = first.put("/support/mailboxes/imap", json={"mailbox": "new@shop.com"})
    assert response.status_code == 200
    assert response.json()["mailbox"] == "new@shop.com"
    assert db_session.query(ImapMailbox).count() == 2
    assert db_session.query(ImapMailbox).filter_by(store_id="store-a").one().cursor is None
    assert second.get("/support/mailboxes/imap").json()["mailbox"] == "second@shop.com"
    assert second.put("/support/mailboxes/imap", json={"mailbox": "new@shop.com"}).status_code == 409


def test_null_and_invalid_update_values_are_rejected(db_session, monkeypatch):
    monkeypatch.setattr(settings, "SUPPORT_CREDENTIALS_KEY", Fernet.generate_key().decode())
    client = _client(db_session, _user())
    assert client.put("/support/mailboxes/imap", json={
        "mailbox": "help@shop.com", "app_password": "secret"
    }).status_code == 201
    for field in ("mailbox", "app_password", "imap_host", "imap_port", "imap_tls_mode",
                  "smtp_host", "smtp_port", "smtp_tls_mode"):
        assert client.put("/support/mailboxes/imap", json={field: None}).status_code == 422
    for payload in ({"mailbox": "invalid"}, {"app_password": " "},
                    {"imap_port": 0}, {"smtp_port": 65536},
                    {"imap_tls_mode": "none"}, {"smtp_host": " "},
                    {"store_id": "store-b"}):
        assert client.put("/support/mailboxes/imap", json=payload).status_code == 422
    assert db_session.query(ImapMailbox).one().mailbox == "help@shop.com"


def test_bearer_token_required(db_session):
    app = FastAPI()
    app.include_router(MailboxRegistry({"imap": ImapAdapter.load(db_session)}).router())
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    assert client.get("/support/mailboxes/imap").status_code in (401, 403)
    assert client.put("/support/mailboxes/imap", json={}).status_code in (401, 403)


def test_unique_race_returns_conflict_without_secret(db_session, monkeypatch):
    monkeypatch.setattr(settings, "SUPPORT_CREDENTIALS_KEY", Fernet.generate_key().decode())
    client = _client(db_session, _user())
    original_commit = db_session.commit

    def raced_commit():
        raise IntegrityError("INSERT", {"app_password": "sensitive"}, Exception("unique"))

    monkeypatch.setattr(db_session, "commit", raced_commit)
    response = client.put("/support/mailboxes/imap", json={
        "mailbox": "help@shop.com", "app_password": "sensitive"
    })
    assert response.status_code == 409
    assert "sensitive" not in response.text
    monkeypatch.setattr(db_session, "commit", original_commit)


def test_running_adapter_keeps_startup_snapshot(db_session, monkeypatch):
    monkeypatch.setattr(settings, "SUPPORT_CREDENTIALS_KEY", Fernet.generate_key().decode())
    adapter = ImapAdapter.load(db_session)
    app = FastAPI()
    app.include_router(MailboxRegistry({"imap": adapter}).router())
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: _user()
    client = TestClient(app)
    assert client.put("/support/mailboxes/imap", json={
        "mailbox": "help@shop.com", "app_password": "secret"
    }).status_code == 201
    assert adapter._mailboxes == {}
    assert "help@shop.com" in ImapAdapter.load(db_session)._mailboxes
    assert client.put("/support/mailboxes/imap", json={"mailbox": "new@shop.com"}).status_code == 200
    assert adapter._mailboxes == {}
    assert "new@shop.com" in ImapAdapter.load(db_session)._mailboxes
