from __future__ import annotations

from typing import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Slide


class SlideService:
    def __init__(self, db: Session):
        self.db = db

    def list_by_project(self, project_id: UUID) -> list[Slide]:
        stmt = select(Slide).where(Slide.project_id == str(project_id)).order_by(Slide.index)
        return list(self.db.scalars(stmt).all())

    def get_by_project_and_index(self, project_id: UUID, index: int) -> Slide:
        stmt = select(Slide).where(
            (Slide.project_id == str(project_id)) & (Slide.index == index)
        )
        slide = self.db.scalars(stmt).first()
        if not slide:
            raise ValueError("Slide not found")
        return slide

    def bulk_create(self, slides: Iterable[Slide]) -> None:
        self.db.add_all(list(slides))
        self.db.commit()

    def update(self, slide: Slide) -> Slide:
        self.db.add(slide)
        self.db.commit()
        self.db.refresh(slide)
        return slide
