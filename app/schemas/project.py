from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.models import ProjectStatus, ProjectType

TemplateSelection = Dict[str, Any]


class ProjectBase(BaseModel):
    type: ProjectType = Field(..., description="Formato desejado: carousel ou stories_10x")
    title: str = Field(..., max_length=255)
    template_selection: Optional[TemplateSelection] = None
    slides_count: int | None = Field(None, ge=0)


class ProjectCreate(ProjectBase):
    id: UUID = Field(default_factory=uuid4)


class ProjectUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    status: Optional[ProjectStatus] = None
    template_selection: Optional[TemplateSelection] = None
    slides_count: Optional[int] = Field(None, ge=0)


class ProjectResponse(ProjectBase):
    id: UUID
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime
    rendered_at: datetime | None = None
    render_version: str | None = None

    class Config:
        from_attributes = True


class ProjectListResponse(BaseModel):
    items: list[ProjectResponse]


class GenerateOutlineRequest(BaseModel):
    topic: str = Field(..., description="Tema central do roteiro")
    tone: str | None = Field(None, description="Tom desejado (ex.: educativo, provocativo)")
    cta_action: str | None = Field(None, description="Ação do CTA final (ex.: DM, link)")
    cta_trigger_word: str | None = Field(None, description="Palavra-chave para o CTA final")
