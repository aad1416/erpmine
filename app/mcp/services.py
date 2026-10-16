import logging
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.dependencies.embeddings import get_embedding_service
from app.dependencies.vector_store import get_chroma_client
from app.repositories.classroom_item_assignments import ClassroomItemAssignmentRepository
from app.repositories.feature_classrooms import FeatureClassroomRepository
from app.repositories.features import FeatureRepository
from app.services.document_retrieval_tool_service import DocumentRetrievalToolService
from app.services.rag_service import RAGService

logger = logging.getLogger(__name__)

_chroma = None
_embedding = None


def _ensure_infra():
    global _chroma, _embedding
    if _chroma is None:
        _chroma = get_chroma_client()
    if _embedding is None:
        _embedding = get_embedding_service()
    return _chroma, _embedding


@contextmanager
def session_scope() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def build_rag_service(db: Session) -> RAGService:
    chroma, embedding = _ensure_infra()
    return RAGService(
        chroma_client=chroma,
        embedding_service=embedding,
        feature_classroom_repository=FeatureClassroomRepository(db),
        item_assignment_repository=ClassroomItemAssignmentRepository(db),
    )


def build_document_retrieval(db: Session) -> DocumentRetrievalToolService:
    return DocumentRetrievalToolService(rag_service=build_rag_service(db))


def list_features_for_ids(feature_ids: frozenset[int]) -> list[dict]:
    if not feature_ids:
        return []
    with session_scope() as db:
        repo = FeatureRepository(db)
        out = []
        for fid in sorted(feature_ids):
            feat = repo.get_by_id(fid)
            if feat is not None:
                out.append({"id": feat.id, "name": getattr(feat, "name", None)})
        return out