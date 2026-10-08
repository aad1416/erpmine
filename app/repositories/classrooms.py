from sqlalchemy.orm import Session
from typing import Optional, List
from app.db.models.Classroom import Classroom


class ClassroomRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, classroom_id: str) -> Optional[Classroom]:
        return self.db.get(Classroom, classroom_id)

    def get_all(self) -> List[Classroom]:
        return self.db.query(Classroom).all()

    def create(self, classroom: Classroom) -> Classroom:
        self.db.add(classroom)
        self.db.commit()
        self.db.refresh(classroom)
        return classroom

    def update(self, classroom: Classroom) -> Classroom:
        self.db.commit()
        self.db.refresh(classroom)
        return classroom

    def delete(self, classroom_id: str) -> None:
        classroom = self.get_by_id(classroom_id)
        if classroom:
            self.db.delete(classroom)
        self.db.commit()
