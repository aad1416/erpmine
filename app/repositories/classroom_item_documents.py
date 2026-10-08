from sqlalchemy.orm import Session, joinedload
from typing import Optional, List
from app.db.models.ClassroomItemDocument import ClassroomItemDocument


class ClassroomItemDocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, doc_id: str) -> Optional[ClassroomItemDocument]:
        return self.db.get(ClassroomItemDocument, doc_id)

    def get_by_inventory_item_document_id(
        self, inventory_item_document_id: str
    ) -> Optional[ClassroomItemDocument]:
        return (
            self.db.query(ClassroomItemDocument)
            .options(
                joinedload(ClassroomItemDocument.item),
                joinedload(ClassroomItemDocument.document),
            )
            .filter(
                ClassroomItemDocument.inventory_item_document_id
                == inventory_item_document_id
            )
            .first()
        )

    def get_all_by_item_id(self, item_id: str) -> List[ClassroomItemDocument]:
        return (
            self.db.query(ClassroomItemDocument)
            .filter(ClassroomItemDocument.item_id == item_id)
            .all()
        )

    def create(self, doc: ClassroomItemDocument) -> ClassroomItemDocument:
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def delete(self, doc_id: str) -> None:
        doc = self.get_by_id(doc_id)
        if doc:
            self.db.delete(doc)
        self.db.commit()
