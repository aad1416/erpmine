from typing import Optional

from sqlalchemy.orm import Session

from app.db.models.Conversation import Conversation
from app.support.adapter.mailbox_key import MailboxKey


class ConversationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create(self, mailbox_key: MailboxKey, conversation_id: str) -> Conversation:
        conversation = self.find(mailbox_key, conversation_id)
        if conversation is None:
            conversation = Conversation(
                adapter=mailbox_key.adapter,
                mailbox=mailbox_key.mailbox,
                conversation_id=conversation_id,
            )
            self.db.add(conversation)
            self.db.commit()
            self.db.refresh(conversation)
        return conversation

    def get_by_id(self, conversation_id: str) -> Optional[Conversation]:
        return self.db.get(Conversation, conversation_id)

    def find(self, mailbox_key: MailboxKey, conversation_id: str) -> Optional[Conversation]:
        """Non-creating lookup by the natural key, for read-only callers (the
        monitoring API) that must not create a row as a side effect of a GET."""
        return (
            self.db.query(Conversation)
            .filter(
                Conversation.adapter == mailbox_key.adapter,
                Conversation.mailbox == mailbox_key.mailbox,
                Conversation.conversation_id == conversation_id,
            )
            .first()
        )

    def save(self, conversation: Conversation, commit: bool = True) -> Conversation:
        """`commit=False` defers to a caller-owned transaction — see
        ConversationMessageRepository.add_outbound for why."""
        if commit:
            self.db.commit()
        return conversation
