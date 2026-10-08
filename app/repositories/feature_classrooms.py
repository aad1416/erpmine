from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.models.Classroom import Classroom
from app.db.models.FeatureClassroom import FeatureClassroom


class FeatureClassroomRepository:
    def __init__(self, db: Session):
        self.db = db

    def assign(self, feature_id: int, classroom_id: str) -> FeatureClassroom:
        existing = self.get_assignment(feature_id, classroom_id)
        if existing:
            return existing
        assignment = FeatureClassroom(
            feature_id=feature_id,
            classroom_id=classroom_id,
        )
        self.db.add(assignment)
        self.db.commit()
        self.db.refresh(assignment)
        return assignment

    def unassign(self, feature_id: int, classroom_id: str) -> bool:
        assignment = self.get_assignment(feature_id, classroom_id)
        if not assignment:
            return False
        self.db.delete(assignment)
        self.db.commit()
        return True

    def get_assignment(
        self, feature_id: int, classroom_id: str
    ) -> Optional[FeatureClassroom]:
        return (
            self.db.query(FeatureClassroom)
            .filter(
                FeatureClassroom.feature_id == feature_id,
                FeatureClassroom.classroom_id == classroom_id,
            )
            .first()
        )

    def get_classrooms_for_feature(self, feature_id: int) -> List[Classroom]:
        return (
            self.db.query(Classroom)
            .join(FeatureClassroom, FeatureClassroom.classroom_id == Classroom.id)
            .filter(FeatureClassroom.feature_id == feature_id)
            .all()
        )

    def get_assignments_for_feature(self, feature_id: int) -> List[FeatureClassroom]:
        return (
            self.db.query(FeatureClassroom)
            .filter(FeatureClassroom.feature_id == feature_id)
            .all()
        )
