from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.database import Base
from datetime import datetime, UTC
import uuid


class ClassroomItemDocument(Base):
    __tablename__ = "classroom_item_documents"

    id = Column(
        String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4())
    )
    item_id = Column(String(36), ForeignKey("classroom_items.id"), nullable=False)
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=False)
    inventory_item_document_id = Column(
        String, unique=True, nullable=False, index=True
    )
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    item = relationship("ClassroomItem", back_populates="documents")
    document = relationship("Document")
