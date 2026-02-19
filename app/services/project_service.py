from __future__ import annotations

from datetime import datetime
from typing import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Project, Slide
from app.models.enums import ProjectStatus, SlideRole


class ProjectService:
    def __init__(self, db: Session):
        self.db = db

    def list_projects(self) -> list[Project]:
        stmt = select(Project).order_by(Project.created_at.desc())
        return list(self.db.scalars(stmt).all())

    def get_project(self, project_id: UUID) -> Project:
        project = self.db.get(Project, str(project_id))
        if not project:
            raise ValueError("Project not found")
        return project

    def create_project(self, project: Project) -> Project:
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def update_project(self, project: Project) -> Project:
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def delete_project(self, project: Project) -> None:
        self.db.delete(project)
        self.db.commit()

    def replace_slides(self, project: Project, slides: Iterable[Slide]) -> Project:
        for existing in list(project.slides):
            self.db.delete(existing)
        project.slides = list(slides)
        project.slides_count = len(project.slides)
        project.status = ProjectStatus.OUTLINED
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def set_status(self, project: Project, status: ProjectStatus) -> Project:
        project.status = status
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def mark_rendering(self, project: Project) -> Project:
        return self.set_status(project, ProjectStatus.RENDERING)

    def mark_rendered(self, project: Project) -> Project:
        project.status = ProjectStatus.RENDERED
        now = datetime.utcnow()
        project.rendered_at = now
        current_version = int(project.render_version or 0) + 1
        project.render_version = str(current_version)
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def ensure_slide_roles(self, project: Project) -> None:
        type_to_roles = {
            "carousel": [SlideRole.COVER] + [SlideRole.BODY] * 6 + [SlideRole.CTA],
            "stories_10x": [SlideRole.FRAME] * 9 + [SlideRole.FRAME_CTA],
        }
        expected_roles = type_to_roles.get(project.type.value)
        if expected_roles and len(project.slides) == len(expected_roles):
            for slide, role in zip(project.slides, expected_roles, strict=False):
                slide.role = role
        self.db.commit()
