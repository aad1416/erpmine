from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class PersonaBase(BaseModel):
    """Base persona schema with common fields."""
    prompt_text: str
    model_name: str


class PersonaCreate(PersonaBase):
    """Schema for creating a new persona."""
    original_prompt_text: str
    updated_by_user_id: str


class PersonaUpdate(BaseModel):
    """Schema for updating an existing persona."""
    prompt_text: Optional[str] = None
    model_name: Optional[str] = None
    updated_by_user_id: Optional[str] = None


class PersonaResponse(PersonaBase):
    """Schema for persona response."""
    id: int
    original_prompt_text: str
    updated_by_user_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

