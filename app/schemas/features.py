from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime


class FeatureBase(BaseModel):
    name: str


class FeatureCreate(FeatureBase):
    store_id: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None


class FeatureUpdate(BaseModel):
    name: str


class Feature(FeatureBase):
    id: int
    persona_id: Optional[int] = None
    store_id: Optional[str] = None

    class Config:
        from_attributes = True


class FeatureResponse(Feature):
    document_count: int = 0


class ClassroomAssignRequest(BaseModel):
    classroom_id: str


class FeatureClassroomResponse(BaseModel):
    id: int
    feature_id: int
    classroom_id: str
    created_at: datetime

    class Config:
        from_attributes = True
