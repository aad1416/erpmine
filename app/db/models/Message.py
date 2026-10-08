from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from app.db.database import Base
from sqlalchemy.orm import relationship


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    chat_id = Column(Integer, ForeignKey("chats.id"), nullable=False)
    role = Column(String, nullable=False)
    content = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    attachments = Column(JSON, nullable=True)

    chat = relationship("Chat", back_populates="messages")
