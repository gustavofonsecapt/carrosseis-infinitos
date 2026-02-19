from __future__ import annotations

from uuid import UUID
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.errors import AppError
from app.models import Slide
from app.schemas.slide import SlideResponse, SlideUpdate
from app.services.project_service import ProjectService
from app.services.slide_service import SlideService

router = APIRouter(prefix="/api/projects/{project_id}/slides", tags=["slides"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


def get_services(db: Session = Depends(get_db)) -> tuple[ProjectService, SlideService]:
    return ProjectService(db), SlideService(db)


@router.get("", response_model=list[SlideResponse])
def list_slides(
    project_id: UUID,
    services: tuple[ProjectService, SlideService] = Depends(get_services),
) -> list[SlideResponse]:
    project_service, slide_service = services
    try:
        project_service.get_project(project_id)
    except ValueError as exc:
        raise AppError("project_not_found", str(exc), status.HTTP_404_NOT_FOUND, {"project_id": str(project_id)}) from exc
    slides = slide_service.list_by_project(project_id)
    return [SlideResponse.model_validate(slide) for slide in slides]


@router.patch("/{index}", response_model=SlideResponse)
def update_slide(
    project_id: UUID,
    index: int,
    payload: SlideUpdate,
    services: tuple[ProjectService, SlideService] = Depends(get_services),
) -> SlideResponse:
    _, slide_service = services
    try:
        slide = slide_service.get_by_project_and_index(project_id, index)
    except ValueError as exc:
        raise AppError("slide_not_found", str(exc), status.HTTP_404_NOT_FOUND, {"project_id": str(project_id), "index": index}) from exc

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(slide, field, value)

    if any(key in update_data for key in ("payload", "image_path")):
        slide.render_path = None

    updated = slide_service.update(slide)
    return SlideResponse.model_validate(updated)


@router.post("/{index}/image", response_model=SlideResponse, status_code=status.HTTP_201_CREATED)
async def upload_slide_image(
    project_id: UUID,
    index: int,
    file: UploadFile = File(...),
    services: tuple[ProjectService, SlideService] = Depends(get_services),
) -> SlideResponse:
    project_service, slide_service = services
    try:
        project_service.get_project(project_id)
    except ValueError as exc:
        raise AppError("project_not_found", str(exc), status.HTTP_404_NOT_FOUND, {"project_id": str(project_id)}) from exc
    try:
        slide = slide_service.get_by_project_and_index(project_id, index)
    except ValueError as exc:
        raise AppError(
            "slide_not_found",
            str(exc),
            status.HTTP_404_NOT_FOUND,
            {"project_id": str(project_id), "index": index},
        ) from exc

    uploads_dir = settings.data_dir / "projects" / str(project_id) / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "uploaded").suffix or ".png"
    dest = uploads_dir / f"slide_{index:02d}{suffix}"
    contents = await file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise AppError("upload_too_large", "Image exceeds 10MB limit", status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, {"max_bytes": MAX_UPLOAD_BYTES})
    dest.write_bytes(contents)

    slide.image_path = str(dest.relative_to(settings.data_dir.parent))
    slide.render_path = None
    updated = slide_service.update(slide)
    return SlideResponse.model_validate(updated)
