from typing import List, Callable, Optional
import uuid

from fastapi import HTTPException

from app.db.models.Classroom import Classroom
from app.db.models.ClassroomItem import ClassroomItem
from app.db.models.ClassroomItemAssignment import ClassroomItemAssignment
from app.db.models.ClassroomItemDocument import ClassroomItemDocument
from app.repositories.classrooms import ClassroomRepository
from app.repositories.classroom_items import ClassroomItemRepository
from app.repositories.classroom_item_assignments import (
    ClassroomItemAssignmentRepository,
)
from app.repositories.classroom_item_documents import ClassroomItemDocumentRepository
from app.repositories.feature_classrooms import FeatureClassroomRepository
from app.services.documents import DocumentService
from app.services.files import FilesService


class ClassroomService:
    def __init__(
        self,
        classroom_repository: ClassroomRepository,
        classroom_item_repository: ClassroomItemRepository,
        classroom_item_assignment_repository: ClassroomItemAssignmentRepository,
        classroom_item_document_repository: ClassroomItemDocumentRepository,
        feature_classroom_repository: FeatureClassroomRepository,
        document_service_factory: Callable[[str], DocumentService],
        files_service: FilesService,
    ):
        self.classroom_repo = classroom_repository
        self.item_repo = classroom_item_repository
        self.item_assignment_repo = classroom_item_assignment_repository
        self.item_doc_repo = classroom_item_document_repository
        self.feature_classroom_repo = feature_classroom_repository
        self.document_service_factory = document_service_factory
        self.files_service = files_service

    def _get_document_service(self, item_id: str) -> DocumentService:
        return self.document_service_factory(item_id)

    def _enrich_item_documents_active_status(
        self, item_docs: List[ClassroomItemDocument]
    ) -> List[ClassroomItemDocument]:
        # Each doc's active flag lives in its item's ChromaDB collection.
        for item_doc in item_docs:
            document_service = self._get_document_service(item_doc.item_id)
            document = document_service.get_document(item_doc.document_id)
            item_doc.active = getattr(document, "active", None)
        return item_docs

    def list_item_documents(
        self, inventory_item_id: str
    ) -> List[ClassroomItemDocument]:
        item = self.item_repo.get_by_inventory_item_id(inventory_item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Classroom item not found")

        item_docs = self.item_doc_repo.get_all_by_item_id(item.id)
        return self._enrich_item_documents_active_status(item_docs)

    def list_classroom_items(self, classroom_id: str) -> List[ClassroomItem]:
        classroom = self.classroom_repo.get_by_id(classroom_id)
        if not classroom:
            raise HTTPException(status_code=404, detail="Classroom not found")
        return self.item_assignment_repo.get_items_for_classroom(classroom_id)

    def list_items(self) -> List[ClassroomItem]:
        return self.item_repo.get_all()

    def list_classrooms(self, feature_id: Optional[int] = None) -> List[Classroom]:
        if feature_id is not None:
            return self.feature_classroom_repo.get_classrooms_for_feature(feature_id)
        return self.classroom_repo.get_all()

    def create_classroom(self, name: str) -> Classroom:
        classroom = Classroom(
            id=str(uuid.uuid4()),
            name=name,
        )
        return self.classroom_repo.create(classroom)

    def rename_classroom(self, classroom_id: str, name: str) -> Classroom:
        classroom = self.classroom_repo.get_by_id(classroom_id)
        if not classroom:
            raise HTTPException(status_code=404, detail="Classroom not found")
        classroom.name = name
        return self.classroom_repo.update(classroom)

    def delete_classroom(self, classroom_id: str) -> None:
        """Delete a classroom and its item/feature assignments.

        Items themselves are shared across classrooms and are not deleted;
        only the assignment rows are removed (via relationship cascade).
        """
        classroom = self.classroom_repo.get_by_id(classroom_id)
        if not classroom:
            raise HTTPException(status_code=404, detail="Classroom not found")
        self.classroom_repo.delete(classroom_id)

    def create_items(self, items: List[dict]) -> List[ClassroomItem]:
        """Batch-create standalone items (no classroom or document)."""
        created: List[ClassroomItem] = []
        for entry in items:
            inventory_item_id = entry["inventory_item_id"]
            existing = self.item_repo.get_by_inventory_item_id(inventory_item_id)
            if existing:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Classroom item with inventory_item_id "
                        f"'{inventory_item_id}' already exists"
                    ),
                )
            item = ClassroomItem(
                id=str(uuid.uuid4()),
                inventory_item_id=inventory_item_id,
            )
            item = self.item_repo.create(item)
            created.append(item)
        return created

    def delete_items(self, items: List[dict]) -> None:
        """Batch-delete standalone items and their documents."""
        for entry in items:
            inventory_item_id = entry["inventory_item_id"]
            item = self.item_repo.get_by_inventory_item_id(inventory_item_id)
            if not item:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        f"Classroom item with inventory_item_id "
                        f"'{inventory_item_id}' not found"
                    ),
                )
            item_docs = list(self.item_doc_repo.get_all_by_item_id(item.id))
            for item_doc in item_docs:
                self.delete_document(item_doc.inventory_item_document_id)
            self.item_repo.delete(item.id)

    async def create_items_with_documents(
        self,
        items: List[dict],
    ) -> List[ClassroomItemDocument]:
        """Batch-create items and upload an associated document for each.

        Each item's document is ingested into its own per-item ChromaDB
        collection (`item_{ClassroomItem.id}`). If an item with the given
        `inventory_item_id` already exists it is reused.
        """
        created_item_docs: List[ClassroomItemDocument] = []

        for entry in items:
            inventory_item_id = entry["inventory_item_id"]
            file_id = entry["file_id"]
            inventory_item_document_id = entry["inventory_item_document_id"]

            item = self.item_repo.get_by_inventory_item_id(inventory_item_id)
            if not item:
                item = ClassroomItem(
                    id=str(uuid.uuid4()),
                    inventory_item_id=inventory_item_id,
                )
                item = self.item_repo.create(item)

            document_service = self._get_document_service(item.id)
            documents = await document_service.add_documents(
                file_ids=[file_id],
            )
            document = documents[0]

            item_doc = ClassroomItemDocument(
                id=str(uuid.uuid4()),
                item_id=item.id,
                document_id=document.id,
                inventory_item_document_id=inventory_item_document_id,
            )
            item_doc = self.item_doc_repo.create(item_doc)
            created_item_docs.append(item_doc)

        return created_item_docs

    def assign_item_to_classroom(
        self, classroom_id: str, item_id: str
    ) -> ClassroomItemAssignment:
        classroom = self.classroom_repo.get_by_id(classroom_id)
        if not classroom:
            raise HTTPException(status_code=404, detail="Classroom not found")

        item = self.item_repo.get_by_id(item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Classroom item not found")

        if self.item_assignment_repo.get_assignment(classroom_id, item_id):
            raise HTTPException(
                status_code=409,
                detail="Item already assigned to classroom",
            )

        return self.item_assignment_repo.assign(classroom_id, item_id)

    def unassign_item_from_classroom(self, classroom_id: str, item_id: str) -> None:
        removed = self.item_assignment_repo.unassign(classroom_id, item_id)
        if not removed:
            raise HTTPException(
                status_code=404,
                detail="Item is not assigned to this classroom",
            )

    async def upload_document(
        self, inventory_item_id: str, file_id: str, inventory_item_document_id: str
    ) -> ClassroomItemDocument:
        item = self.item_repo.get_by_inventory_item_id(inventory_item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Classroom item not found")

        document_service = self._get_document_service(item.id)

        documents = await document_service.add_documents(
            file_ids=[file_id],
        )
        document = documents[0]

        item_doc = ClassroomItemDocument(
            id=str(uuid.uuid4()),
            item_id=item.id,
            document_id=document.id,
            inventory_item_document_id=inventory_item_document_id,
        )
        return self.item_doc_repo.create(item_doc)

    def toggle_document_activation(
        self, inventory_item_document_id: str, active: bool
    ) -> None:
        item_doc = self.item_doc_repo.get_by_inventory_item_document_id(
            inventory_item_document_id
        )
        if not item_doc:
            raise HTTPException(
                status_code=404, detail="Classroom item document not found"
            )

        document_service = self._get_document_service(item_doc.item_id)

        if active:
            document_service.activate_document(item_doc.document_id)
        else:
            document_service.deactivate_document(item_doc.document_id)

    def delete_document(self, inventory_item_document_id: str) -> None:
        item_doc = self.item_doc_repo.get_by_inventory_item_document_id(
            inventory_item_document_id
        )
        if not item_doc:
            raise HTTPException(
                status_code=404, detail="Classroom item document not found"
            )

        document_service = self._get_document_service(item_doc.item_id)

        document = document_service.get_document(item_doc.document_id)
        file_id = document.file_id

        document_service.delete_documents([item_doc.document_id])
        self.files_service.delete(file_id)
        self.item_doc_repo.delete(item_doc.id)

    def download_document(self, inventory_item_document_id: str) -> dict:
        item_doc = self.item_doc_repo.get_by_inventory_item_document_id(
            inventory_item_document_id
        )
        if not item_doc:
            raise HTTPException(
                status_code=404, detail="Classroom item document not found"
            )

        document_service = self._get_document_service(item_doc.item_id)

        document = document_service.get_document(item_doc.document_id)
        file = self.files_service.get(document.file_id)
        if not file:
            raise HTTPException(status_code=404, detail="File not found")

        return {
            "path": file.path,
            "filename": file.file_name,
            "mime_type": file.mime_type,
        }
