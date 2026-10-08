"""Seam 2: the support system run through `start_support`, with a test Mailbox Adapter
registered by the decorator, against a test DB. Covers the sink → task → worker → reply
path and the startup guards."""

from __future__ import annotations

import asyncio
import base64
import json
import textwrap
from datetime import datetime, UTC
from email.message import EmailMessage
from unittest.mock import patch

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi import APIRouter, FastAPI
from sqlalchemy import Column, String
from sqlalchemy.orm import DeclarativeBase

import app.db.database as db_module
from app.config.setting import settings
from app.db.models.Conversation import Conversation
from app.support.adapter.gmail import adapter as gmail_adapter_module
from app.support.adapter.gmail.adapter import GmailAdapter
from app.support.adapter.gmail.models import GmailMailbox
from app.support.adapter.gmail.settings import gmail_settings
from app.support.adapter.imap import adapter as imap_adapter_module
from app.support.adapter.imap.adapter import ImapAdapter
from app.support.adapter.imap.models import ImapMailbox
from app.support.adapter.imap.settings import imap_settings
from app.support.adapter import base as adapter_base_module
from app.support.adapter.base import (
    MailboxAdapter,
    adapter,
    discover,
    registered_adapter_classes,
)
from app.support.adapter.mailbox_key import MailboxKey
from app.support.adapter.registry import MailboxRegistry
from app.support.adapter.mailtrap import adapter as mailtrap_adapter_module
from app.support.adapter.mailtrap.adapter import MailtrapAdapter
from app.support.adapter.mailtrap.models import MailtrapMailbox
from app.support.adapter.mailtrap.settings import mailtrap_settings
from app.support.adapter.schemas import NormalizedMessage
from app.support.ingestion.models import IngestionTask, TaskStatus, TaskType
from app.support.ingestion.sink import message_sink
from app.support.ingestion.task_repository import TaskRepository
from app.support.ingestion.port import notify_ai_core
from app.support.init import check_single_worker, start_support, stop_support
from tests.support.adapter.gmail.fake_gmail import FakeGmail
from tests.support.adapter.imap.fake_imap import FakeImapHosts, FakeImapServer
from tests.support.adapter.imap.fake_smtp import FakeSmtp
from tests.support.adapter.mailtrap.fake_mailtrap import FakeMailtrap


class FakeTablesBase(DeclarativeBase):
    """Kept off the app's Base, so these tables exist only in these tests."""


class FakeMailbox(FakeTablesBase):
    __tablename__ = "test_mailboxes"

    mailbox = Column(String, primary_key=True)


class OtherFakeMailbox(FakeTablesBase):
    __tablename__ = "other_test_mailboxes"

    mailbox = Column(String, primary_key=True)


class RecordingAdapter(MailboxAdapter):
    """Undecorated: each test registers it (or not) itself."""

    def __init__(self, credential_rows):
        self.mailboxes = [row.mailbox for row in credential_rows]
        self.sink = None
        self.stopped = False
        self.sent = []

    async def start(self, sink):
        self.sink = sink

    async def stop(self):
        self.stopped = True

    async def send_message(self, mailbox, conversation_id, text, idempotency_key):
        self.sent.append(
            {
                "mailbox": mailbox,
                "conversation_id": conversation_id,
                "text": text,
                "idempotency_key": idempotency_key,
            }
        )

    def router(self):
        router = APIRouter()

        @router.get(f"/support/{self.name}/ping")
        async def ping():
            return {"ok": True}

        return router


class OtherRecordingAdapter(RecordingAdapter):
    pass


@pytest.fixture()
def support_system(db_session, monkeypatch, tmp_path):
    """An adapter class registry holding only the ported real adapters, the test tables
    and a private lock file. The AI core is stubbed to queue a reply per batch.

    The ported adapters stay registered because `start_support` discovers the real
    adapter package, and their modules are already imported, so they wouldn't register
    again. With empty tables they start and serve nothing."""
    monkeypatch.setattr(
        adapter_base_module,
        "_adapter_classes",
        {"mailtrap": MailtrapAdapter, "imap": ImapAdapter, "gmail": GmailAdapter},
    )
    FakeTablesBase.metadata.create_all(db_session.get_bind())
    monkeypatch.setattr(settings, "SUPPORT_LOCK_FILE", str(tmp_path / "support.lock"))
    monkeypatch.delenv("WEB_CONCURRENCY", raising=False)

    notified = []

    async def fake_notify_ai_core(conversation_id, messages):
        notified.append((conversation_id, messages))
        db = db_module.SessionLocal()
        try:
            TaskRepository(db).enqueue(
                task_type=TaskType.send_message.value,
                mailbox_key=messages[0].mailbox_key,
                conversation_id=conversation_id,
                payload={"text": f"reply to {messages[0].body_text}"},
            )
        finally:
            db.close()

    monkeypatch.setattr(
        "app.support.ingestion.worker.ingestion_worker.port.notify_ai_core",
        fake_notify_ai_core,
    )
    yield notified


@pytest.fixture()
async def stopped_after(support_system):
    """`support_system`, with `stop_support` on teardown."""
    yield support_system
    await stop_support()


def _message(external_message_id="m1", conversation_id="t1", mailbox="help@shop.com"):
    return NormalizedMessage(
        adapter="test",
        mailbox=mailbox,
        conversation_id=conversation_id,
        external_message_id=external_message_id,
        sender_address="customer@example.com",
        received_at=datetime.now(UTC),
        body_text="where is my order",
    )


async def _eventually(predicate, timeout=2.0):
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("condition not met in time")
        await asyncio.sleep(0.01)


def _register_test_adapter():
    adapter("test", credentials=FakeMailbox)(RecordingAdapter)


@pytest.mark.asyncio
async def test_a_message_through_the_sink_becomes_one_message_task(stopped_after, db_session):
    _register_test_adapter()
    db_session.add(FakeMailbox(mailbox="help@shop.com"))
    db_session.commit()
    await start_support(FastAPI())

    await message_sink(_message())
    await message_sink(_message())  # an adapter re-sinking after a crash

    tasks = db_session.query(IngestionTask).filter_by(task_type="message").all()
    assert len(tasks) == 1
    assert (tasks[0].adapter, tasks[0].mailbox, tasks[0].external_message_id) == (
        "test",
        "help@shop.com",
        "m1",
    )


@pytest.mark.asyncio
async def test_the_worker_processes_the_message_and_the_reply_reaches_the_adapter(
    stopped_after, db_session
):
    _register_test_adapter()
    db_session.add(FakeMailbox(mailbox="help@shop.com"))
    db_session.commit()
    mailbox_registry = await start_support(FastAPI())
    test_adapter = mailbox_registry.get("test")

    await test_adapter.sink(_message(conversation_id="thread-9"))
    await _eventually(lambda: len(test_adapter.sent) == 1)

    db_session.expire_all()
    send_task = db_session.query(IngestionTask).filter_by(task_type="send_message").one()
    assert test_adapter.sent == [
        {
            "mailbox": "help@shop.com",
            "conversation_id": "thread-9",
            "text": "reply to where is my order",
            "idempotency_key": send_task.id,
        }
    ]
    await _eventually(lambda: _statuses(db_session) == {TaskStatus.done.value})


def _statuses(db_session):
    db_session.expire_all()
    return {task.status for task in db_session.query(IngestionTask).all()}


@pytest.mark.asyncio
async def test_the_worker_wakes_when_the_sink_writes_without_waiting_for_its_interval(
    stopped_after, db_session, monkeypatch
):
    monkeypatch.setattr(settings, "SUPPORT_WORKER_FALLBACK_INTERVAL_SECONDS", 3600)
    notified = stopped_after
    _register_test_adapter()
    await start_support(FastAPI())
    await asyncio.sleep(0.1)  # let the first, empty pass finish and the loop go idle

    await message_sink(_message())

    await _eventually(lambda: len(notified) == 1, timeout=1.0)


@pytest.mark.asyncio
async def test_an_adapter_with_no_mailboxes_is_still_built_and_started(stopped_after):
    _register_test_adapter()

    mailbox_registry = await start_support(FastAPI())

    test_adapter = mailbox_registry.get("test")
    assert test_adapter is not None
    assert test_adapter.mailboxes == []
    assert test_adapter.sink is message_sink


@pytest.mark.asyncio
async def test_adapter_routes_are_mounted_and_adapters_stop_on_shutdown(stopped_after):
    _register_test_adapter()
    app = FastAPI()

    mailbox_registry = await start_support(app)
    await stop_support()

    assert "/support/test/ping" in {route.path for route in app.routes}
    assert mailbox_registry.get("test").stopped


def test_an_undecorated_subclass_is_not_registered(support_system, db_session):
    class UndecoratedFake(RecordingAdapter):
        pass

    assert "test" not in registered_adapter_classes()
    assert MailboxRegistry.load(db_session).get("test") is None


def test_a_duplicate_adapter_name_raises(support_system):
    _register_test_adapter()

    with pytest.raises(ValueError, match="'test' is registered twice"):
        adapter("test", credentials=OtherFakeMailbox)(OtherRecordingAdapter)


@pytest.mark.asyncio
async def test_the_same_mailbox_in_two_adapters_refuses_to_start(stopped_after, db_session):
    _register_test_adapter()
    adapter("other", credentials=OtherFakeMailbox)(OtherRecordingAdapter)
    db_session.add(FakeMailbox(mailbox="help@shop.com"))
    db_session.add(OtherFakeMailbox(mailbox="Help@Shop.com"))
    db_session.commit()

    with pytest.raises(RuntimeError, match="help@shop.com in other, test"):
        await start_support(FastAPI())


@pytest.mark.asyncio
async def test_the_same_mailbox_in_gmail_and_imap_refuses_to_start(
    stopped_after, db_session, monkeypatch
):
    """A Mailbox uses exactly one Connection Method (ADR 0002): the Mailbox Registry
    refuses an address in both the Gmail API's and IMAP's tables."""
    monkeypatch.setattr(settings, "SUPPORT_CREDENTIALS_KEY", Fernet.generate_key().decode())
    db_session.add(GmailMailbox(mailbox="support@acme-store.com", refresh_token="token"))
    db_session.add(ImapMailbox(mailbox="Support@Acme-Store.com", store_id="store-a", app_password="app password"))
    db_session.commit()

    with pytest.raises(RuntimeError, match="support@acme-store.com in gmail, imap"):
        await start_support(FastAPI())


def _write_adapter_package(tmp_path, package_name, folders):
    package_dir = tmp_path / package_name
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("")
    for folder_name, adapter_source in folders.items():
        folder = package_dir / folder_name
        folder.mkdir()
        (folder / "__init__.py").write_text("")
        if adapter_source is not None:
            (folder / "adapter.py").write_text(textwrap.dedent(adapter_source))


def test_discovery_raises_on_an_adapter_module_that_registered_nothing(
    support_system, tmp_path, monkeypatch
):
    import importlib

    _write_adapter_package(
        tmp_path,
        "empty_module_adapters",
        {"forgotten": "class ForgottenAdapter:\n    pass\n", "placeholder": None},
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    with pytest.raises(RuntimeError, match="empty_module_adapters.forgotten.adapter registered no"):
        discover(importlib.import_module("empty_module_adapters"))


def test_discovery_imports_decorated_adapters_and_skips_placeholder_folders(
    support_system, tmp_path, monkeypatch
):
    import importlib

    _write_adapter_package(
        tmp_path,
        "discovered_adapters",
        {
            "sample": """
                from tests.support.test_support_system import RecordingAdapter, FakeMailbox
                from app.support.adapter.base import adapter

                @adapter("sample", credentials=FakeMailbox)
                class SampleAdapter(RecordingAdapter):
                    pass
            """,
            "placeholder": None,
        },
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    package = importlib.import_module("discovered_adapters")

    assert set(discover(package)) == {"sample", "mailtrap", "imap", "gmail"}
    # a second discovery doesn't raise
    assert set(discover(package)) == {"sample", "mailtrap", "imap", "gmail"}


def test_discovery_of_the_real_adapter_package_skips_placeholders(support_system):
    """telegram/ and whatsapp/ have no adapter module."""
    assert discover() == {"mailtrap": MailtrapAdapter, "imap": ImapAdapter, "gmail": GmailAdapter}


@pytest.mark.parametrize(
    "argv, environ",
    [
        (["uvicorn", "app.main:app", "--workers", "2"], {}),
        (["uvicorn", "app.main:app", "--workers=4"], {}),
        (["uvicorn", "app.main:app"], {"WEB_CONCURRENCY": "3"}),
    ],
)
def test_more_than_one_worker_refuses_to_start(argv, environ):
    with pytest.raises(RuntimeError, match="single uvicorn worker"):
        check_single_worker(argv, environ)


@pytest.mark.parametrize(
    "argv, environ",
    [
        (["uvicorn", "app.main:app"], {}),
        (["uvicorn", "app.main:app", "--workers", "1"], {"WEB_CONCURRENCY": "4"}),
        (["uvicorn", "app.main:app", "--reload"], {"WEB_CONCURRENCY": "4"}),
    ],
)
def test_a_single_worker_is_allowed(argv, environ):
    check_single_worker(argv, environ)


@pytest.mark.asyncio
async def test_start_support_checks_the_worker_count(stopped_after, monkeypatch):
    monkeypatch.setattr("sys.argv", ["uvicorn", "app.main:app", "--workers", "2"])

    with pytest.raises(RuntimeError, match="single uvicorn worker"):
        await start_support(FastAPI())


@pytest.mark.asyncio
async def test_a_reply_for_an_adapter_not_in_the_registry_is_retried_not_sent(
    stopped_after, db_session
):
    """The Mailbox Registry is the only reply route: a task naming an adapter it doesn't
    have fails into retry and dead-letter instead of being marked sent."""
    _register_test_adapter()
    mailbox_registry = await start_support(FastAPI())

    task = TaskRepository(db_session).enqueue(
        task_type=TaskType.send_message.value,
        mailbox_key=MailboxKey("retired", "s@x.com"),
        conversation_id="t1",
        payload={"text": "hello"},
    )
    await message_sink(_message())  # wakes the worker

    def failed_once() -> bool:
        db_session.expire_all()
        return "last_error" in db_session.get(IngestionTask, task.id).payload

    await _eventually(failed_once)
    assert db_session.get(IngestionTask, task.id).status != TaskStatus.done.value
    assert "'retired'" in db_session.get(IngestionTask, task.id).payload["last_error"]
    assert all(sent["mailbox"] == "help@shop.com" for sent in mailbox_registry.get("test").sent)


@pytest.mark.asyncio
async def test_mailtrap_is_started_and_its_replies_route_to_it(
    stopped_after, db_session, monkeypatch
):
    monkeypatch.setattr(settings, "SUPPORT_CREDENTIALS_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(mailtrap_settings, "POLL_INTERVAL_SECONDS", 0.01)
    monkeypatch.setattr(mailtrap_settings, "DETECTION_MODE", "poll")
    mailtrap_api = FakeMailtrap()
    monkeypatch.setattr(mailtrap_adapter_module, "MailtrapClient", mailtrap_api.client)
    inbox = mailtrap_api.add_inbox("816", "token")
    inbox.receive("m1", "2024-01-02T00:00:00+00:00", thread_id="thread-7")
    db_session.add(
        MailtrapMailbox(
            mailbox="dev@inbound-mailtrap.io",
            inbox_id="816",
            api_token="token",
            cursor="2024-01-01T00:00:00+00:00",
        )
    )
    db_session.commit()

    mailbox_registry = await start_support(FastAPI())

    assert isinstance(mailbox_registry.get("mailtrap"), MailtrapAdapter)
    await _eventually(lambda: inbox.replies == [("m1", "reply to body m1")])
    await _eventually(lambda: _statuses(db_session) == {TaskStatus.done.value})
    send_task = db_session.query(IngestionTask).filter_by(task_type="send_message").one()
    assert (send_task.adapter, send_task.mailbox) == ("mailtrap", "dev@inbound-mailtrap.io")


def _reply_agent():
    async def run(self, *, run_input, ctx, allow_gathering_tools):
        ctx.tool_called = "reply"
        ctx.reply_text = "Thanks, looking into it."
        return ctx

    return run


@pytest.mark.asyncio
async def test_imap_is_started_and_its_replies_route_to_it(
    stopped_after, db_session, monkeypatch
):
    """The real AI core, with only its decision agent stubbed: an email to an IMAP
    Mailbox becomes a Conversation, and the reply goes out over SMTP in its thread."""
    monkeypatch.setattr(settings, "SUPPORT_CREDENTIALS_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(imap_settings, "POLL_INTERVAL_SECONDS", 0.01)
    monkeypatch.setattr(
        "app.support.ingestion.worker.ingestion_worker.port.notify_ai_core", notify_ai_core
    )
    hosts = FakeImapHosts()
    server = hosts.add("imap.gmail.com", FakeImapServer(uidvalidity=7))
    smtp = FakeSmtp()
    monkeypatch.setattr(imap_adapter_module, "IMAPClient", hosts.factory)
    monkeypatch.setattr(imap_adapter_module, "aiosmtplib_send", smtp.send)
    email = EmailMessage()
    email["From"] = "Jane Doe <jane@example.com>"
    email["To"] = "help@shop.com"
    email["Subject"] = "Help"
    email["Message-ID"] = "<m1@example.com>"
    email.set_content("My unit is broken.")
    server.deliver(email.as_bytes(), 0x11, 0x22, datetime(2026, 9, 25, 9, 0, tzinfo=UTC))
    db_session.add(ImapMailbox(mailbox="help@shop.com", store_id="store-a", app_password="app password", cursor="7:0"))
    db_session.commit()

    with patch("app.services.decision_agent.DecisionAgent.run", new=_reply_agent()):
        mailbox_registry = await start_support(FastAPI())
        assert isinstance(mailbox_registry.get("imap"), ImapAdapter)
        await _eventually(lambda: len(smtp.sent) == 1)
        await _eventually(lambda: _statuses(db_session) == {TaskStatus.done.value})

    conversation = db_session.query(Conversation).one()
    assert (conversation.adapter, conversation.mailbox, conversation.conversation_id) == (
        "imap",
        "help@shop.com",
        "22",
    )
    send_task = db_session.query(IngestionTask).filter_by(task_type="send_message").one()
    assert (send_task.adapter, send_task.mailbox) == ("imap", "help@shop.com")
    [mail] = smtp.sent
    assert (mail.sender, mail.recipients) == ("help@shop.com", ["jane@example.com"])
    assert mail.message["In-Reply-To"] == "<m1@example.com>"
    assert mail.message.get_content().strip() == "Thanks, looking into it."


@pytest.mark.asyncio
async def test_gmail_is_started_its_webhook_is_mounted_and_replies_route_to_it(
    stopped_after, db_session, monkeypatch
):
    """The real AI core, with only its decision agent stubbed, and Gmail in push mode: a
    Pub/Sub notification to the mounted webhook reads the Mailbox, the email becomes a
    Conversation, and the reply goes out through the Gmail API in its thread."""
    monkeypatch.setattr(settings, "SUPPORT_CREDENTIALS_KEY", Fernet.generate_key().decode())
    for name, value in {
        "CLIENT_ID": "client-id",
        "CLIENT_SECRET": "client-secret",
        "DETECTION_MODE": "push",
        "BACKUP_POLL_INTERVAL_SECONDS": 3600,
        "PUBSUB_TOPIC": "projects/p/topics/gmail",
        "PUBSUB_AUDIENCE": None,
    }.items():
        monkeypatch.setattr(gmail_settings, name, value)
    monkeypatch.setattr(
        "app.support.ingestion.worker.ingestion_worker.port.notify_ai_core", notify_ai_core
    )
    gmail = FakeGmail()
    account = gmail.add("help@shop.com")
    monkeypatch.setattr(gmail_adapter_module, "GmailClient", gmail.factory)
    db_session.add(GmailMailbox(mailbox="help@shop.com", refresh_token="token", history_id="100"))
    db_session.commit()
    app = FastAPI()

    with patch("app.services.decision_agent.DecisionAgent.run", new=_reply_agent()):
        mailbox_registry = await start_support(app)
        assert isinstance(mailbox_registry.get("gmail"), GmailAdapter)
        assert "/support/webhooks/gmail" in {route.path for route in app.routes}
        await _eventually(lambda: account.history_reads == 1)  # the read on start
        account.receive("m1", thread_id="thread-1", sender="Jane Doe <jane@example.com>")

        notification = json.dumps({"emailAddress": "help@shop.com", "historyId": "101"})
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/support/webhooks/gmail",
                json={"message": {"data": base64.b64encode(notification.encode()).decode()}},
            )
        assert response.status_code == 204
        await _eventually(lambda: len(account.sent) == 1)
        await _eventually(lambda: _statuses(db_session) == {TaskStatus.done.value})

    conversation = db_session.query(Conversation).one()
    assert (conversation.adapter, conversation.mailbox, conversation.conversation_id) == (
        "gmail",
        "help@shop.com",
        "thread-1",
    )
    send_task = db_session.query(IngestionTask).filter_by(task_type="send_message").one()
    assert (send_task.adapter, send_task.mailbox) == ("gmail", "help@shop.com")
    [(reply, thread_id)] = account.sent
    assert thread_id == "thread-1"
    assert (reply["From"], reply["To"]) == ("help@shop.com", "jane@example.com")
    assert reply["X-Support-Reply-Key"] == send_task.id
    assert reply.get_content().strip() == "Thanks, looking into it."
    assert account.watches == ["projects/p/topics/gmail"]
