from sqlalchemy.orm import Session
from typing import Optional, List
from app.db.models.Message import Message


class MessageRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, message_id: int) -> Optional[Message]:
        return self.db.get(Message, message_id)

    def get_all(self, chat_id: int) -> List[Message]:
        return self.db.query(Message).filter(Message.chat_id == chat_id).all()

    def create(self, message: Message) -> Message:
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def update(self, message: Message) -> Message:
        self.db.commit()
        return message

    def delete(self, message_id: int) -> None:
        message = self.get_by_id(message_id)
        if message:
            self.db.delete(message)
        self.db.commit()
