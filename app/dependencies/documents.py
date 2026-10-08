from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Union

from fastapi import Depends, HTTPException, Path as FastAPIPath, status
from sqlalchemy.orm import Session
from chromadb import Collection

from app.config.setting import settings
from app.dependencies.database import get_db
from app.dependencies.embeddings import get_embedding_service
from app.dependencies.files import get_files_service
from app.dependencies.vector_store import get_collection
from app.repositories.documents import DocumentRepository
from app.repositories.features import FeatureRepository
from app.services.documents import DocumentService
from app.services.embedding_service import EmbeddingService
from app.services.files import FilesService
from app.utils.document_parser import DocumentParser
from app.utils.markdown_chunker import MarkdownChunker
from app.utils.fast_document_parser import FastDocumentParser



def get_document_repository(
    db: Annotated[Session, Depends(get_db)],
) -> DocumentRepository:
    return DocumentRepository(db)


def get_feature_repository(
    db: Annotated[Session, Depends(get_db)],
) -> FeatureRepository:
    return FeatureRepository(db)


def get_feature_id_from_path(
    feature_id: Annotated[int, FastAPIPath(..., description="The ID of the feature")],
) -> int:
    return feature_id


def get_llama_document_parser() -> DocumentParser:
    """Return a LlamaParse-backed parser with full format support."""
    return DocumentParser(
        llama_parse_api_key=settings.LLAMA_PARSE_API_KEY,
        language=settings.LLAMA_PARSE_LANGUAGE,
        config_profile=settings.LLAMA_PARSE_CONFIG_PROFILE,
        version=settings.LLAMA_PARSE_VERSION,
    )


def get_document_parser() -> Union[DocumentParser, FastDocumentParser]:
    """Return the appropriate document parser based on DOCUMENT_PARSER_BACKEND.

    - ``fast`` (default): local API-free parsing (pymupdf4llm, MarkItDown, calamine)
      with optional LlamaParse fallback for images.
    - ``llama``: cloud-based LlamaParse — full format support.
    """
    if settings.DOCUMENT_PARSER_BACKEND == "fast":
        llama_fallback = None
        if settings.LLAMA_PARSE_API_KEY:
            llama_fallback = get_llama_document_parser()
        return FastDocumentParser(llama_fallback_parser=llama_fallback)

    return get_llama_document_parser()



def get_markdown_chunker() -> MarkdownChunker:
    if settings.MARKDOWN_CHUNKER_BACKEND == "llamaindex":
        from app.utils.llamaindex_chunker import LlamaIndexMarkdownChunker

        return LlamaIndexMarkdownChunker(
            text_chunk_size=settings.TEXT_CHUNK_SIZE,
            text_chunk_overlap=settings.TEXT_CHUNK_OVERLAP,
            table_max_rows=settings.TABLE_MAX_ROWS,
            table_row_overlap=settings.TABLE_ROW_OVERLAP,
            min_section_tokens=settings.MIN_SECTION_TOKENS,
        )
    return MarkdownChunker(
        text_chunk_size=settings.TEXT_CHUNK_SIZE,
        text_chunk_overlap=settings.TEXT_CHUNK_OVERLAP,
        table_max_rows=settings.TABLE_MAX_ROWS,
        table_row_overlap=settings.TABLE_ROW_OVERLAP,
        min_section_tokens=settings.MIN_SECTION_TOKENS,
    )


async def get_document_service(
    feature_id: Annotated[int, Depends(get_feature_id_from_path)],
    files_service: Annotated[FilesService, Depends(get_files_service)],
    document_repository: Annotated[
        DocumentRepository, Depends(get_document_repository)
    ],
    feature_repository: Annotated[FeatureRepository, Depends(get_feature_repository)],
    parser_service: Annotated[DocumentParser, Depends(get_document_parser)],
    chunker: Annotated[MarkdownChunker, Depends(get_markdown_chunker)],
    embedding_service: Annotated[EmbeddingService, Depends(get_embedding_service)],
) -> DocumentService:
    feature = feature_repository.get_by_id(feature_id)
    if not feature:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Feature not found"
        )

    collection: Collection = get_collection(feature_id)
    return DocumentService(
        files_service=files_service,
        collection=collection,
        document_repository=document_repository,
        parser_service=parser_service,
        chunker=chunker,
        embedding_service=embedding_service,
    )
