"""Shared document-search behavior behind the retrieve_documents agent tool."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List

from app.config.setting import settings

if TYPE_CHECKING:
    from app.services.rag_service import RAGService

logger = logging.getLogger(__name__)


@dataclass
class DocumentRetrievalResult:
    content: str
    sources: List[dict] = field(default_factory=list)


class DocumentRetrievalToolService:
    """Owns RAG retrieval for agent tools; context-agnostic and reusable across runners."""

    def __init__(self, rag_service: "RAGService"):
        self.rag_service = rag_service

    async def retrieve(
        self, *, query: str, feature_id: int, top_k: int
    ) -> DocumentRetrievalResult:
        trimmed = query.strip()
        if not trimmed:
            return DocumentRetrievalResult(content="Error: empty search query.")

        try:
            result = await self.rag_service.retrieve_async(
                query=trimmed,
                feature_id=feature_id,
                top_k=top_k,
                similarity_threshold=settings.RAG_SIMILARITY_THRESHOLD,
            )
            formatted = result.get("formatted") or ""
            chunk_sources = result.get("sources") or []
            content = (
                formatted if formatted.strip() else "(No matching documentation chunks.)"
            )
            return DocumentRetrievalResult(content=content, sources=chunk_sources)
        except Exception as exc:  # noqa: BLE001
            logger.exception("retrieve_documents failed")
            return DocumentRetrievalResult(content=f"Document search failed: {exc}")
