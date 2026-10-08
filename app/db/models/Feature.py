from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db.database import Base


class Feature(Base):
    __tablename__ = "features"

    __table_args__ = (
        UniqueConstraint("entity_id", "store_id", name="uq_feature_entity_id_store_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    store_id = Column(String, nullable=True)
    persona_id = Column(Integer, ForeignKey("personas.id"), nullable=True)
    entity_type = Column(String, nullable=True)
    entity_id = Column(String, nullable=True)

    persona = relationship("Persona", back_populates="features")
    documents = relationship("Document", back_populates="feature")
    chats = relationship(
        "Chat", back_populates="feature", cascade="all, delete-orphan"
    )
    classroom_assignments = relationship(
        "FeatureClassroom", back_populates="feature", cascade="all, delete-orphan"
    )
