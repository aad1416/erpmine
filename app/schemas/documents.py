from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime
from app.schemas.files import FileResponse


class DocumentCreateRequest(BaseModel):
    file_ids: List[str]
    metadata: Optional[Dict[str, str]] = None


class DocumentResponse(BaseModel):
    id: str
    feature_id: int
    file_id: str
    document_metadata: Optional[Dict[str, str]] = None
    active: Optional[bool] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentWithFileResponse(BaseModel):
    id: str
    feature_id: int
    file_id: str
    document_metadata: Optional[Dict[str, str]] = None
    active: Optional[bool] = None
    created_at: datetime
    updated_at: datetime
    file: Optional[FileResponse] = None

    class Config:
        from_attributes = True


class DocumentMetadataUpdateRequest(BaseModel):
    metadata: Dict[str, str]
