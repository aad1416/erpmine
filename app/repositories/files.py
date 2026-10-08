from sqlalchemy.orm import Session
from typing import Optional

from app.db.models import File


class FilesRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, file: File) -> File:
        self.db.add(file)
        self.db.commit()
        self.db.refresh(file)
        return file

    def get_by_id(self, id: str) -> Optional[File]:
        return self.db.get(File, id)

    def delete(self, id: str) -> None:
        file = self.get_by_id(id)
        if file:
            self.db.delete(file)
        self.db.commit()
