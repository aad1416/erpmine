from fastapi import Depends
from sqlalchemy.orm import Session
from app.services.feature_service import FeatureService
from app.repositories.features import FeatureRepository
from app.repositories.personas import PersonaRepository
from app.dependencies.database import get_db


def get_feature_repository(db: Session = Depends(get_db)) -> FeatureRepository:
    return FeatureRepository(db)


def get_persona_repository(db: Session = Depends(get_db)) -> PersonaRepository:
    return PersonaRepository(db)


def get_feature_service(
    feature_repository: FeatureRepository = Depends(get_feature_repository),
    persona_repository: PersonaRepository = Depends(get_persona_repository),
) -> FeatureService:
    return FeatureService(feature_repository, persona_repository)

