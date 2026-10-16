from typing import Any
from pydantic import BaseModel, Field


class DocumentSource(BaseModel):
    document_id: str | int | None = None
    file_id: str | None = None
    filename: str | None = None
    file_type: str | None = None
    chunk_type: str | None = None
    chunk_index: int | None = None
    section_path: str | None = None
    page: int | str | None = None
    page_label: str | None = None
    table_id: str | None = None
    row_start: int | None = None
    row_end: int | None = None


class SearchDocumentsResult(BaseModel):
    formatted: str = Field(description="Markdown context for the model")
    sources: list[DocumentSource] = Field(default_factory=list)
    count: int = Field(ge=0)


class FeatureInfo(BaseModel):
    id: int
    name: str | None = None


class ListFeaturesResult(BaseModel):
    features: list[FeatureInfo]