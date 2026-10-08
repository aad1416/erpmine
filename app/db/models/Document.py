from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from app.db.database import Base
from sqlalchemy.orm import relationship
from datetime import datetime, UTC


class Document(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, index=True)
    feature_id = Column(Integer, ForeignKey("features.id"), nullable=True)
    file_id = Column(String(36), ForeignKey("files.id"), unique=True, nullable=False)
    document_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    feature = relationship("Feature", back_populates="documents")
    file = relationship("File", back_populates="document", uselist=False)
