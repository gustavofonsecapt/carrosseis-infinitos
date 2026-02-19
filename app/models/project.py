from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import ProjectStatus, ProjectType


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    type: Mapped[ProjectType] = mapped_column(Enum(ProjectType), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus), default=ProjectStatus.DRAFT, nullable=False
    )
    template_selection: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=True)
    slides_count: Mapped[int] = mapped_column(default=0)
    metadata_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    rendered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    render_version: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    slides: Mapped[list["Slide"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="Slide.index"
    )


from app.models.slide import Slide  # noqa: E402  circular import guard
