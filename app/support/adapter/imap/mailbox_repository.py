"""Persistence queries used while activating an IMAP mailbox."""

from sqlalchemy.orm import Session

from app.support.adapter.imap.models import ImapMailbox


class ImapMailboxRepository:
    def __init__(self, db: Session):
        self.db = db

    def cursor_for_store(self, store_id: str) -> str | None:
        return self.db.query(ImapMailbox.cursor).filter_by(store_id=store_id).scalar()
