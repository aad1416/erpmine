from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class ClassroomCreate(BaseModel):
    name: str = Field(..., min_length=1, description="Classroom name")


class ClassroomUpdate(BaseModel):
    name: str = Field(..., min_length=1, description="New classroom name")


class ClassroomResponse(BaseModel):
    id: str
    name: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ClassroomItemCreate(BaseModel):
    inventory_item_id: str = Field(
        ..., min_length=1, description="External inventory item ID"
    )


class ClassroomItemsCreateRequest(BaseModel):
    items: List[ClassroomItemCreate] = Field(
        ..., min_length=1, description="List of items to create"
    )


class ClassroomItemsDeleteRequest(BaseModel):
    items: List[ClassroomItemCreate] = Field(
        ..., min_length=1, description="List of items to delete"
    )


class ClassroomItemWithDocumentCreate(BaseModel):
    inventory_item_id: str = Field(
        ..., min_length=1, description="External inventory item ID"
    )
    file_id: str = Field(
        ..., min_length=1, description="File ID to process as document"
    )
    inventory_item_document_id: str = Field(
        ..., min_length=1, description="External inventory item document ID"
    )


class ClassroomItemsWithDocumentsCreateRequest(BaseModel):
    items: List[ClassroomItemWithDocumentCreate] = Field(
        ...,
        min_length=1,
        description="List of items to create with associated documents",
    )


class ClassroomItemDocumentUploadRequest(BaseModel):
    file_id: str = Field(..., min_length=1, description="File ID to process")
    inventory_item_document_id: str = Field(
        ..., min_length=1, description="External inventory item document ID"
    )


class DocumentActivationRequest(BaseModel):
    active: bool = Field(..., description="Whether the document should be active")


class ClassroomItemDocumentResponse(BaseModel):
    id: str
    item_id: str
    document_id: str
    inventory_item_document_id: str
    active: Optional[bool] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ClassroomItemResponse(BaseModel):
    id: str
    inventory_item_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
