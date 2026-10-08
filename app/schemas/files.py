from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict

class FileResponse(BaseModel):
    id: str
    file_name: str
    path: str
    extension: Optional[str] = None
    size: int
    mime_type: Optional[str] = None
    user_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

