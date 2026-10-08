from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from app.db.database import Base
from sqlalchemy.orm import relationship
import uuid


class File(Base):
    __tablename__ = "files"

    id = Column(
        String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4())
    )
    file_name = Column(String, nullable=False)
    path = Column(String, nullable=False)
    extension = Column(String, nullable=True)
    size = Column(Integer, nullable=False)
    mime_type = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    user_id = Column(String(36), nullable=True)

    document = relationship("Document", back_populates="file", uselist=False)
