from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session
from chromadb import Collection

from app.dependencies.database import get_db
from app.dependencies.embeddings import get_embedding_service
from app.dependencies.files import get_files_service
from app.dependencies.vector_store import get_item_collection
from app.dependencies.documents import get_document_parser, get_markdown_chunker
from app.repositories.classrooms import ClassroomRepository
from app.repositories.classroom_items import ClassroomItemRepository
from app.repositories.classroom_item_assignments import (
    ClassroomItemAssignmentRepository,
)
from app.repositories.classroom_item_documents import ClassroomItemDocumentRepository
from app.repositories.documents import DocumentRepository
from app.repositories.feature_classrooms import FeatureClassroomRepository
from app.services.classroom_service import ClassroomService
from app.services.documents import DocumentService
from app.services.embedding_service import EmbeddingService
from app.services.files import FilesService
from app.utils.document_parser import DocumentParser
from app.utils.markdown_chunker import MarkdownChunker


def get_classroom_service(
    db: Annotated[Session, Depends(get_db)],
    files_service: Annotated[FilesService, Depends(get_files_service)],
    parser_service: Annotated[DocumentParser, Depends(get_document_parser)],
    chunker: Annotated[MarkdownChunker, Depends(get_markdown_chunker)],
    embedding_service: Annotated[EmbeddingService, Depends(get_embedding_service)],
) -> ClassroomService:
    classroom_repo = ClassroomRepository(db)
    item_repo = ClassroomItemRepository(db)
    item_assignment_repo = ClassroomItemAssignmentRepository(db)
    item_doc_repo = ClassroomItemDocumentRepository(db)
    document_repo = DocumentRepository(db)
    feature_classroom_repo = FeatureClassroomRepository(db)

    def document_service_factory(item_id: str) -> DocumentService:
        collection: Collection = get_item_collection(item_id)
        return DocumentService(
            files_service=files_service,
            collection=collection,
            document_repository=document_repo,
            parser_service=parser_service,
            chunker=chunker,
            embedding_service=embedding_service,
        )

    return ClassroomService(
        classroom_repository=classroom_repo,
        classroom_item_repository=item_repo,
        classroom_item_assignment_repository=item_assignment_repo,
        classroom_item_document_repository=item_doc_repo,
        feature_classroom_repository=feature_classroom_repo,
        document_service_factory=document_service_factory,
        files_service=files_service,
    )
