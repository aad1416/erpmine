from typing import List, Optional, Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.dependencies.auth import get_admin_user, get_current_user
from app.dependencies.database import get_db
from app.dependencies.features import get_feature_service
from app.db.models.Users import User
from app.services.feature_service import FeatureService
from app.repositories.feature_classrooms import FeatureClassroomRepository
from app.repositories.features import FeatureRepository
from app.repositories.classrooms import ClassroomRepository
from app.schemas.features import (
    FeatureBase,
    FeatureCreate,
    FeatureUpdate,
    FeatureResponse,
    ClassroomAssignRequest,
    FeatureClassroomResponse,
)

router = APIRouter()


def get_feature_classroom_repo(
    db: Annotated[Session, Depends(get_db)],
) -> FeatureClassroomRepository:
    return FeatureClassroomRepository(db)


def get_feature_repo(
    db: Annotated[Session, Depends(get_db)],
) -> FeatureRepository:
    return FeatureRepository(db)


def get_classroom_repo(
    db: Annotated[Session, Depends(get_db)],
) -> ClassroomRepository:
    return ClassroomRepository(db)


@router.get(
    "/admin/features",
    response_model=List[FeatureResponse],
    tags=["admin-features"],
    summary="List features for the admin's store",
)
def list_features(
    entity_type: Optional[list[str]] = Query(
        default=None,
        description=(
            "Filter by feature entity_type. Repeat for multiple values "
            "(e.g. `?entity_type=widget&entity_type=page`). "
            "Use `custom` to include features with no entity_type (null)."
        ),
    ),
    service: FeatureService = Depends(get_feature_service),
    user: User = Depends(get_current_user),
):
    """
    List features for the authenticated admin's store.

    Results are limited to the admin's **store_id** from their session. Each item is a
    feature record (id, name, persona_id, store_id, entity_type, entity_id, document_count).

    **Query parameters**

    - **entity_type**: Optional. When omitted, all features in the store are returned.
      When set, only features matching at least one value are included. The literal
      `custom` matches rows where `entity_type` is null (store-defined features without
      a typed link to an external entity).

    **Authorization:** Admin only.

    **Returns:** A JSON array of features, possibly empty if none match the filters.
    """
    return service.list_all_features(store_id=user.store_id, entity_type=entity_type)


@router.get(
    "/admin/features/by-entity/{entity_id}",
    response_model=FeatureResponse,
    tags=["admin-features"],
)
def get_feature_by_entity_id(
    entity_id: str,
    service: FeatureService = Depends(get_feature_service),
    user: User = Depends(get_current_user),
):
    """Get a feature by entity_id within the admin's store (admin only)."""
    feature = service.get_feature_by_entity_id(entity_id, store_id=user.store_id)
    if not feature:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feature with entity_id {entity_id!r} not found",
        )
    return feature


@router.get(
    "/admin/features/{feature_id}",
    response_model=FeatureResponse,
    tags=["admin-features"],
)
def get_feature(
    feature_id: int,
    service: FeatureService = Depends(get_feature_service),
    admin_user: User = Depends(get_admin_user),
):
    """Get a feature by ID (admin only)."""
    feature = service.get_feature_by_id(feature_id)
    if not feature:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feature with id {feature_id} not found",
        )
    return feature


@router.post(
    "/admin/features",
    response_model=FeatureResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["admin-features"],
)
def create_feature(
    feature_data: FeatureBase,
    service: FeatureService = Depends(get_feature_service),
    admin_user: User = Depends(get_admin_user),
):
    """Create a new feature with a default persona (admin only)."""
    existing = service.get_store_feature_by_name(
        feature_data.name, store_id=admin_user.store_id
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Feature with name '{feature_data.name}' already exists",
        )
    return service.create_feature(
        FeatureCreate(name=feature_data.name, store_id=admin_user.store_id),
        admin_user_id=admin_user.id,
    )


@router.put(
    "/admin/features/{feature_id}",
    response_model=FeatureResponse,
    tags=["admin-features"],
)
def update_feature(
    feature_id: int,
    feature_data: FeatureUpdate,
    service: FeatureService = Depends(get_feature_service),
    admin_user: User = Depends(get_admin_user),
):
    """Update a feature by ID (admin only)."""
    existing_store_feature_by_name = service.get_store_feature_by_name(
        feature_data.name, feature_data.store_id
    )
    if (
        existing_store_feature_by_name
        and existing_store_feature_by_name.id != feature_id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Feature with name '{feature_data.name}' already exists",
        )
    updated = service.update_feature(feature_id, feature_data)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feature with id {feature_id} not found",
        )
    return updated


@router.delete(
    "/admin/features/{feature_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["admin-features"],
)
def delete_feature(
    feature_id: int,
    service: FeatureService = Depends(get_feature_service),
    admin_user: User = Depends(get_admin_user),
):
    """Delete a feature by ID (admin only)."""
    deleted = service.delete_feature(feature_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feature with id {feature_id} not found",
        )


@router.get(
    "/admin/features/{feature_id}/classrooms",
    response_model=List[FeatureClassroomResponse],
    tags=["admin-features"],
)
def list_feature_classrooms(
    feature_id: int,
    feature_repo: FeatureRepository = Depends(get_feature_repo),
    fc_repo: FeatureClassroomRepository = Depends(get_feature_classroom_repo),
    admin_user: User = Depends(get_admin_user),
):
    """List all classrooms assigned to a feature (admin only)."""
    feature = feature_repo.get_by_id(feature_id)
    if not feature:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feature with id {feature_id} not found",
        )
    return fc_repo.get_assignments_for_feature(feature_id)


@router.post(
    "/admin/features/{feature_id}/classrooms",
    response_model=FeatureClassroomResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["admin-features"],
)
def assign_classroom_to_feature(
    feature_id: int,
    request: ClassroomAssignRequest,
    feature_repo: FeatureRepository = Depends(get_feature_repo),
    classroom_repo: ClassroomRepository = Depends(get_classroom_repo),
    fc_repo: FeatureClassroomRepository = Depends(get_feature_classroom_repo),
    admin_user: User = Depends(get_admin_user),
):
    """Assign a classroom to a feature (admin only)."""
    feature = feature_repo.get_by_id(feature_id)
    if not feature:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feature with id {feature_id} not found",
        )
    classroom = classroom_repo.get_by_id(request.classroom_id)
    if not classroom:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Classroom with id {request.classroom_id} not found",
        )
    existing = fc_repo.get_assignment(feature_id, request.classroom_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Classroom is already assigned to this feature",
        )
    return fc_repo.assign(feature_id, request.classroom_id)


@router.delete(
    "/admin/features/{feature_id}/classrooms/{classroom_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["admin-features"],
)
def unassign_classroom_from_feature(
    feature_id: int,
    classroom_id: str,
    fc_repo: FeatureClassroomRepository = Depends(get_feature_classroom_repo),
    admin_user: User = Depends(get_admin_user),
):
    """Remove a classroom assignment from a feature (admin only)."""
    removed = fc_repo.unassign(feature_id, classroom_id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found",
        )
