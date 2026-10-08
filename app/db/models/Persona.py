from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from app.db.database import Base
from sqlalchemy.orm import relationship


class Persona(Base):
    __tablename__ = "personas"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    prompt_text = Column(String, nullable=False)
    original_prompt_text = Column(String, nullable=False)
    model_name = Column(String, nullable=False)
    updated_by_user_id = Column(String(36), nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    features = relationship("Feature", back_populates="persona")