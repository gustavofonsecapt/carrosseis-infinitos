from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.models import SlideRole

Payload = Dict[str, Any]


class SlideBase(BaseModel):
    index: int = Field(..., ge=1)
    role: SlideRole
    payload: Payload = Field(default_factory=dict)


class SlideCreate(SlideBase):
    id: UUID = Field(default_factory=uuid4)
    project_id: UUID


class SlideUpdate(BaseModel):
    payload: Optional[Payload] = None
    image_path: Optional[str] = None
    render_path: Optional[str] = None


class SlideResponse(SlideBase):
    id: UUID
    project_id: UUID
    image_path: Optional[str] = None
    render_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SlideListResponse(BaseModel):
    items: list[SlideResponse]
