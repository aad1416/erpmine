from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.db.models.Feature import Feature
from app.schemas.features import FeatureCreate, FeatureUpdate


class FeatureRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_feature(self, feature: FeatureCreate) -> Feature:
        db_feature = Feature(
            name=feature.name,
            store_id=feature.store_id,
            entity_type=feature.entity_type,
            entity_id=feature.entity_id,
        )
        self.db.add(db_feature)
        self.db.commit()
        self.db.refresh(db_feature)
        return db_feature

    def get_by_id(self, feature_id: int) -> Feature | None:
        return self.db.query(Feature).filter(Feature.id == feature_id).first()

    def get_by_entity_id(self, entity_id: str) -> Feature | None:
        return self.db.query(Feature).filter(Feature.entity_id == entity_id).first()

    def get_by_entity_id_and_store(
        self, entity_id: str, store_id: str
    ) -> Feature | None:
        return (
            self.db.query(Feature)
            .filter(Feature.entity_id == entity_id, Feature.store_id == store_id)
            .first()
        )

    def get_store_feature_by_name(
        self, name: str, store_id: str | None = None
    ) -> Feature | None:
        query = self.db.query(Feature)
        if store_id is not None:
            query = query.filter(Feature.store_id == store_id)
        return query.filter(Feature.name == name).first()

    def get_all(
        self, store_id: str | None = None, entity_type: list[str] | None = None
    ) -> list[Feature]:
        query = self.db.query(Feature)
        if store_id is not None:
            query = query.filter(Feature.store_id == store_id)
        if entity_type is not None:
            filters = []
            if "custom" in entity_type:
                filters.append(Feature.entity_type.is_(None))
            types = [t for t in entity_type if t != "custom"]
            if types:
                filters.append(Feature.entity_type.in_(types))
            query = query.filter(or_(*filters))
        return query.all()

    def update_feature(
        self, feature_id: int, feature_update: FeatureUpdate
    ) -> Feature | None:
        db_feature = self.get_by_id(feature_id)
        if not db_feature:
            return None
        db_feature.name = feature_update.name
        self.db.commit()
        self.db.refresh(db_feature)
        return db_feature

    def delete_feature(self, feature_id: int) -> bool:
        db_feature = self.get_by_id(feature_id)
        if not db_feature:
            return False
        self.db.delete(db_feature)
        self.db.commit()
        return True
