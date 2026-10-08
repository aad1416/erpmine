from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.dependencies.auth import get_admin_user
from app.db.models.Users import User
from app.repositories.personas import PersonaRepository
from app.services.persona_service import PersonaService
from app.schemas.personas import PersonaResponse, PersonaUpdate

router = APIRouter()


def get_persona_service(db: Session = Depends(get_db)) -> PersonaService:
    repo = PersonaRepository(db)
    return PersonaService(repo)


@router.get(
    "/admin/features/{feature_id}/personas",
    response_model=PersonaResponse,
    tags=["admin-personas"],
)
def get_persona_for_feature(
    feature_id: int,
    service: PersonaService = Depends(get_persona_service),
    admin_user: User = Depends(get_admin_user),
):
    """Get persona for feature (admin only)."""
    persona = service.get_persona_for_feature(feature_id)
    if not persona:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Persona for feature {feature_id} not found",
        )
    return persona


@router.put(
    "/admin/features/{feature_id}/personas",
    response_model=PersonaResponse,
    tags=["admin-personas"],
)
def update_persona_for_feature(
    feature_id: int,
    persona_update: PersonaUpdate,
    service: PersonaService = Depends(get_persona_service),
    admin_user: User = Depends(get_admin_user),
):
    """Update persona for feature (admin only)."""
    persona = service.get_persona_for_feature(feature_id)
    if not persona:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Persona for feature {feature_id} not found",
        )

    persona_update.updated_by_user_id = admin_user.id
    updated_persona = service.update_persona(persona.id, persona_update)
    return updated_persona


@router.post(
    "/admin/features/{feature_id}/personas/reset",
    response_model=PersonaResponse,
    tags=["admin-personas"],
)
def reset_persona_for_feature(
    feature_id: int,
    service: PersonaService = Depends(get_persona_service),
    admin_user: User = Depends(get_admin_user),
):
    """Reset persona prompt to original (admin only)."""
    persona = service.get_persona_for_feature(feature_id)
    if not persona:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Persona for feature {feature_id} not found",
        )

    reset_persona = service.reset_persona_to_original(persona.id, admin_user.id)
    return reset_persona
