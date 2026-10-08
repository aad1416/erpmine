from sqlalchemy.orm import Session
from typing import Optional, List
from app.db.models.Chat import Chat


class ChatRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, chat_id: int) -> Optional[Chat]:
        return self.db.get(Chat, chat_id)

    def get_all(self, user_id: str) -> List[Chat]:
        return self.db.query(Chat).filter(Chat.user_id == user_id).all()

    def get_user_chats(self, user_id: str) -> List[Chat]:
        return self.db.query(Chat).filter(Chat.user_id == user_id).all()

    def get_user_chats_by_feature(self, user_id: str, feature_id: int) -> List[Chat]:
        return self.db.query(Chat).filter(
            Chat.user_id == user_id,
            Chat.feature_id == feature_id
        ).all()

    def create(self, chat: Chat) -> Chat:
        self.db.add(chat)
        self.db.commit()
        self.db.refresh(chat)
        return chat

    def update(self, chat: Chat) -> Chat:
        self.db.commit()
        return chat

    def delete(self, chat_id: int) -> None:
        chat = self.get_by_id(chat_id)
        if chat:
            self.db.delete(chat)
        self.db.commit()
