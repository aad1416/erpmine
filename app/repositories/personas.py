from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from app.db.models.Persona import Persona
from app.db.models.Feature import Feature


class PersonaRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, persona_id: int) -> Optional[Persona]:
        """Get a persona by ID."""
        return self.db.query(Persona).filter(Persona.id == persona_id).first()

    def get_by_feature_id(self, feature_id: int) -> Optional[Persona]:
        """Get persona for a specific feature."""
        feature = self.db.query(Feature).filter(Feature.id == feature_id).first()
        if feature and feature.persona_id:
            return self.db.query(Persona).filter(Persona.id == feature.persona_id).first()
        return None

    def get_all(self, skip: int = 0, limit: int = 100) -> List[Persona]:
        """List all personas."""
        return self.db.query(Persona).offset(skip).limit(limit).all()

    def create(self, persona: Persona) -> Persona:
        """Create a new persona."""
        self.db.add(persona)
        self.db.commit()
        self.db.refresh(persona)
        return persona

    def update(self, persona: Persona) -> Persona:
        """Update an existing persona."""
        persona.updated_at = datetime.now()
        self.db.commit()
        self.db.refresh(persona)
        return persona
