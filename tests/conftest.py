"""Shared in-memory SQLite fixture for app/support/ and app/services/ tests
(08-unit-test-strategy-checklist.md §1: "DB layer in tests: in-memory / SQLite")."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.database as db_module
import app.db.models  # noqa: F401 -- registers AI-core models on Base.metadata
import app.support.adapter.gmail.models  # noqa: F401
import app.support.adapter.imap.models  # noqa: F401
import app.support.adapter.mailtrap.models  # noqa: F401
import app.support.ingestion.models  # noqa: F401
from app.db.database import Base


@pytest.fixture()
def db_session(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_session_local = sessionmaker(bind=engine)
    monkeypatch.setattr(db_module, "SessionLocal", test_session_local)

    # Several modules do `from app.db.database import SessionLocal` (matching the
    # existing app/services/seed_scheduler.py convention), which early-binds the name
    # at import time — patching app.db.database.SessionLocal alone doesn't reach them.
    for dotted_path in [
        "app.support.ingestion.worker.ingestion_worker.SessionLocal",
        "app.support.ingestion.sink.SessionLocal",
        "app.support.init.SessionLocal",
        "app.support.adapter.gmail.adapter.SessionLocal",
        "app.support.adapter.mailtrap.adapter.SessionLocal",
        "app.support.adapter.imap.adapter.SessionLocal",
        "app.services.conversation_service.SessionLocal",
        "app.services.log_sync_retry_job.SessionLocal",
    ]:
        monkeypatch.setattr(dotted_path, test_session_local)

    session = test_session_local()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
