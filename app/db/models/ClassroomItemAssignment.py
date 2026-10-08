from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db.database import Base
from datetime import datetime, UTC


class ClassroomItemAssignment(Base):
    __tablename__ = "classroom_item_assignments"

    __table_args__ = (
        UniqueConstraint("classroom_id", "item_id", name="uq_classroom_item"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    classroom_id = Column(String(36), ForeignKey("classrooms.id"), nullable=False)
    item_id = Column(String(36), ForeignKey("classroom_items.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))

    classroom = relationship("Classroom", back_populates="item_assignments")
    item = relationship("ClassroomItem", back_populates="classroom_assignments")
