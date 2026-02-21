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


# Fields that are "frozen" after outline generation — edits must never remove them
_PROTECTED_PAYLOAD_KEYS = {"template_id", "template_variant"}


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

    # Merge payload instead of replacing — protect template_id / template_variant
    if "payload" in update_data and update_data["payload"] is not None:
        existing_payload = dict(slide.payload) if slide.payload else {}
        new_payload = update_data["payload"]

        # Preserve protected keys from existing payload
        for key in _PROTECTED_PAYLOAD_KEYS:
            if key in existing_payload and key not in new_payload:
                new_payload[key] = existing_payload[key]

        existing_payload.update(new_payload)
        slide.payload = existing_payload
        del update_data["payload"]

    for field, value in update_data.items():
        setattr(slide, field, value)

    if any(key in update_data for key in ("payload",)) or "payload" not in update_data and "image_path" in update_data:
        slide.render_path = None
    # Payload was already merged above, always invalidate render
    else:
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

    # Snapshot protected payload keys BEFORE upload
    frozen_template_id = slide.payload.get("template_id") if slide.payload else None
    frozen_template_variant = slide.payload.get("template_variant") if slide.payload else None

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

    # GUARD: upload must NEVER alter template_id or template_variant
    if slide.payload:
        payload_copy = dict(slide.payload)
        if frozen_template_id is not None:
            payload_copy["template_id"] = frozen_template_id
        if frozen_template_variant is not None:
            payload_copy["template_variant"] = frozen_template_variant
        slide.payload = payload_copy

    updated = slide_service.update(slide)
    return SlideResponse.model_validate(updated)
