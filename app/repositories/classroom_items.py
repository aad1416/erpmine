from sqlalchemy.orm import Session
from typing import Optional, List
from app.db.models.ClassroomItem import ClassroomItem


class ClassroomItemRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, item_id: str) -> Optional[ClassroomItem]:
        return self.db.get(ClassroomItem, item_id)

    def get_by_inventory_item_id(
        self, inventory_item_id: str
    ) -> Optional[ClassroomItem]:
        return (
            self.db.query(ClassroomItem)
            .filter(ClassroomItem.inventory_item_id == inventory_item_id)
            .first()
        )

    def get_all(self) -> List[ClassroomItem]:
        return self.db.query(ClassroomItem).all()

    def create(self, item: ClassroomItem) -> ClassroomItem:
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def delete(self, item_id: str) -> None:
        item = self.get_by_id(item_id)
        if item:
            self.db.delete(item)
        self.db.commit()
