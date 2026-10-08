from datetime import datetime
from typing import List, Optional
from app.db.models.Feature import Feature
from app.db.models.Persona import Persona
from app.repositories.features import FeatureRepository
from app.repositories.personas import PersonaRepository
from app.schemas.features import FeatureCreate, FeatureUpdate

DEFAULT_PERSONA_PROMPT = (
    "You are a helpful AI assistant. Answer questions clearly and concisely."
)
DEFAULT_MODEL_NAME = "gpt-4o"


class FeatureService:
    """
    Feature Service

    Responsibilities:
    - Business logic for features
    - Coordinate feature operations
    - Validate feature access
    """

    def __init__(
        self,
        feature_repository: FeatureRepository,
        persona_repository: PersonaRepository,
    ):
        self.feature_repository = feature_repository
        self.persona_repository = persona_repository

    def get_feature_by_id(self, feature_id: int) -> Optional[Feature]:
        """
        Get a feature by ID

        Args:
            feature_id: ID of the feature

        Returns:
            Feature object or None if not found
        """
        return self.feature_repository.get_by_id(feature_id)

    def get_feature_by_entity_id(
        self, entity_id: str, store_id: Optional[str] = None
    ) -> Optional[Feature]:
        """
        Get a feature by entity_id, scoped to store when store_id is provided.

        Args:
            entity_id: External entity identifier stored on the feature
            store_id: When set, require a match on store_id (recommended for tenancy)

        Returns:
            Feature object or None if not found
        """
        if store_id is not None:
            return self.feature_repository.get_by_entity_id_and_store(
                entity_id, store_id
            )
        return self.feature_repository.get_by_entity_id(entity_id)

    def get_store_feature_by_name(
        self, name: str, store_id: Optional[str] = None
    ) -> Optional[Feature]:
        """
        Get a feature by name

        Args:
            name: Name of the feature

        Returns:
            Feature object or None if not found
        """
        return self.feature_repository.get_store_feature_by_name(
            name, store_id=store_id
        )

    def list_all_features(
        self, store_id: Optional[str] = None, entity_type: Optional[list[str]] = None
    ) -> List[Feature]:
        """
        List all features, optionally filtered by store_id

        Returns:
            List of features
        """
        return self.feature_repository.get_all(
            store_id=store_id, entity_type=entity_type
        )

    def create_feature(self, feature: FeatureCreate, admin_user_id: str) -> Feature:
        """
        Create a new feature with a default persona linked to it.

        Args:
            feature: Feature creation data
            admin_user_id: ID of the admin creating the feature

        Returns:
            Created feature object
        """
        db_feature = self.feature_repository.create_feature(feature)

        now = datetime.now()
        default_persona = Persona(
            prompt_text=DEFAULT_PERSONA_PROMPT,
            original_prompt_text=DEFAULT_PERSONA_PROMPT,
            model_name=DEFAULT_MODEL_NAME,
            updated_by_user_id=admin_user_id,
            created_at=now,
            updated_at=now,
        )
        persona = self.persona_repository.create(default_persona)

        db_feature.persona_id = persona.id
        self.feature_repository.db.commit()
        self.feature_repository.db.refresh(db_feature)

        return db_feature

    def update_feature(
        self, feature_id: int, feature_update: FeatureUpdate
    ) -> Optional[Feature]:
        """
        Update a feature by ID

        Args:
            feature_id: ID of the feature to update
            feature_update: Updated feature data

        Returns:
            Updated feature object or None if not found
        """
        return self.feature_repository.update_feature(feature_id, feature_update)

    def delete_feature(self, feature_id: int) -> bool:
        """
        Delete a feature by ID

        Args:
            feature_id: ID of the feature to delete

        Returns:
            True if deleted, False if not found
        """
        return self.feature_repository.delete_feature(feature_id)

    def validate_feature_exists(self, feature_id: int) -> Feature:
        """
        Validate that a feature exists, raise exception if not

        Args:
            feature_id: ID of the feature to validate

        Returns:
            Feature object

        Raises:
            ValueError: If feature not found
        """
        feature = self.get_feature_by_id(feature_id)
        if not feature:
            raise ValueError(f"Feature with id {feature_id} not found")
        return feature
