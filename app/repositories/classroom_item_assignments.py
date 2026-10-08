from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.models.Classroom import Classroom
from app.db.models.ClassroomItem import ClassroomItem
from app.db.models.ClassroomItemAssignment import ClassroomItemAssignment


class ClassroomItemAssignmentRepository:
    def __init__(self, db: Session):
        self.db = db

    def assign(self, classroom_id: str, item_id: str) -> ClassroomItemAssignment:
        existing = self.get_assignment(classroom_id, item_id)
        if existing:
            return existing
        assignment = ClassroomItemAssignment(
            classroom_id=classroom_id,
            item_id=item_id,
        )
        self.db.add(assignment)
        self.db.commit()
        self.db.refresh(assignment)
        return assignment

    def unassign(self, classroom_id: str, item_id: str) -> bool:
        assignment = self.get_assignment(classroom_id, item_id)
        if not assignment:
            return False
        self.db.delete(assignment)
        self.db.commit()
        return True

    def get_assignment(
        self, classroom_id: str, item_id: str
    ) -> Optional[ClassroomItemAssignment]:
        return (
            self.db.query(ClassroomItemAssignment)
            .filter(
                ClassroomItemAssignment.classroom_id == classroom_id,
                ClassroomItemAssignment.item_id == item_id,
            )
            .first()
        )

    def get_items_for_classroom(self, classroom_id: str) -> List[ClassroomItem]:
        return (
            self.db.query(ClassroomItem)
            .join(
                ClassroomItemAssignment,
                ClassroomItemAssignment.item_id == ClassroomItem.id,
            )
            .filter(ClassroomItemAssignment.classroom_id == classroom_id)
            .all()
        )

    def get_classrooms_for_item(self, item_id: str) -> List[Classroom]:
        return (
            self.db.query(Classroom)
            .join(
                ClassroomItemAssignment,
                ClassroomItemAssignment.classroom_id == Classroom.id,
            )
            .filter(ClassroomItemAssignment.item_id == item_id)
            .all()
        )
