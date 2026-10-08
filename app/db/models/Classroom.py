from sqlalchemy import Column, String, DateTime
from sqlalchemy.orm import relationship
from app.db.database import Base
from datetime import datetime, UTC
import uuid


class Classroom(Base):
    __tablename__ = "classrooms"

    id = Column(
        String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4())
    )
    name = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    item_assignments = relationship(
        "ClassroomItemAssignment",
        back_populates="classroom",
        cascade="all, delete-orphan",
    )
    feature_assignments = relationship(
        "FeatureClassroom", back_populates="classroom", cascade="all, delete-orphan"
    )
