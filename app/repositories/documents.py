from sqlalchemy.orm import Session, joinedload
from typing import Optional, List
from app.db.models.Document import Document


class DocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, id: str) -> Optional[Document]:
        return self.db.get(Document, id)

    def get_all_by_feature_id(self, feature_id: int) -> List[Document]:
        return (
            self.db.query(Document)
            .options(joinedload(Document.file))
            .filter(Document.feature_id == feature_id)
            .all()
        )

    def create(self, document: Document) -> Document:
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def update(self, document: Document) -> Document:
        self.db.commit()
        return document

    def delete(self, id: str) -> None:
        document = self.get_by_id(id)
        if document:
            self.db.delete(document)
        self.db.commit()
