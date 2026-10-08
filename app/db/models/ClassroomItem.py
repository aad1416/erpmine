from sqlalchemy import Column, String, DateTime
from sqlalchemy.orm import relationship
from app.db.database import Base
from datetime import datetime, UTC
import uuid


class ClassroomItem(Base):
    __tablename__ = "classroom_items"

    id = Column(
        String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4())
    )
    inventory_item_id = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    classroom_assignments = relationship(
        "ClassroomItemAssignment",
        back_populates="item",
        cascade="all, delete-orphan",
    )
    documents = relationship(
        "ClassroomItemDocument", back_populates="item", cascade="all, delete-orphan"
    )
