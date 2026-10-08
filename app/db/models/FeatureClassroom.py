from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db.database import Base
from datetime import datetime, UTC


class FeatureClassroom(Base):
    __tablename__ = "collections"

    __table_args__ = (
        UniqueConstraint("feature_id", "classroom_id", name="uq_feature_classroom"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    feature_id = Column(Integer, ForeignKey("features.id"), nullable=False)
    classroom_id = Column(String(36), ForeignKey("classrooms.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))

    feature = relationship("Feature", back_populates="classroom_assignments")
    classroom = relationship("Classroom", back_populates="feature_assignments")
