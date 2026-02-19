from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError
from app.models import Project, ProjectStatus
from app.schemas.project import (
    GenerateOutlineRequest,
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)
from app.services.outline_service import OutlineRequestContext, OutlineService
from app.services.project_service import ProjectService
from app.services.render_service import RenderService
from app.services.export_service import ExportService

router = APIRouter(prefix="/api/projects", tags=["projects"])


def get_service(db: Session = Depends(get_db)) -> ProjectService:
    return ProjectService(db)


def get_outline_service() -> OutlineService:
    return OutlineService()


def get_render_service(db: Session = Depends(get_db)) -> RenderService:
    return RenderService(db)


def get_export_service() -> ExportService:
    return ExportService()


def _slugify(value: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    slug = slug.strip("-") or "project"
    return slug[:80]


@router.get("", response_model=ProjectListResponse)
def list_projects(service: ProjectService = Depends(get_service)) -> ProjectListResponse:
    projects = service.list_projects()
    return ProjectListResponse(items=projects)


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    service: ProjectService = Depends(get_service),
) -> ProjectResponse:
    project = Project(
        id=str(payload.id),
        type=payload.type,
        title=payload.title,
        template_selection=payload.template_selection,
        slides_count=payload.slides_count or 0,
    )
    created = service.create_project(project)
    return ProjectResponse.model_validate(created)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: UUID,
    service: ProjectService = Depends(get_service),
) -> ProjectResponse:
    try:
        project = service.get_project(project_id)
    except ValueError as exc:
        raise AppError("project_not_found", str(exc), status.HTTP_404_NOT_FOUND, {"project_id": str(project_id)}) from exc
    return ProjectResponse.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: UUID,
    payload: ProjectUpdate,
    service: ProjectService = Depends(get_service),
) -> ProjectResponse:
    try:
        project = service.get_project(project_id)
    except ValueError as exc:
        raise AppError("project_not_found", str(exc), status.HTTP_404_NOT_FOUND, {"project_id": str(project_id)}) from exc

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    updated = service.update_project(project)
    return ProjectResponse.model_validate(updated)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: UUID,
    service: ProjectService = Depends(get_service),
) -> None:
    try:
        project = service.get_project(project_id)
    except ValueError as exc:
        raise AppError("project_not_found", str(exc), status.HTTP_404_NOT_FOUND, {"project_id": str(project_id)}) from exc
    service.delete_project(project)


@router.post("/{project_id}/generate-outline", response_model=ProjectResponse, status_code=status.HTTP_202_ACCEPTED)
def generate_outline(
    project_id: UUID,
    payload: GenerateOutlineRequest,
    service: ProjectService = Depends(get_service),
    outline_service: OutlineService = Depends(get_outline_service),
) -> ProjectResponse:
    try:
        project = service.get_project(project_id)
    except ValueError as exc:
        raise AppError("project_not_found", str(exc), status.HTTP_404_NOT_FOUND, {"project_id": str(project_id)}) from exc

    ctx = OutlineRequestContext(
        topic=payload.topic,
        tone=payload.tone,
        cta_action=payload.cta_action,
        cta_trigger_word=payload.cta_trigger_word,
    )

    slides = outline_service.generate(project, ctx)
    service.replace_slides(project, slides)

    return ProjectResponse.model_validate(project)


@router.post("/{project_id}/render", response_model=ProjectResponse, status_code=status.HTTP_202_ACCEPTED)
async def render_project_route(
    project_id: UUID,
    service: ProjectService = Depends(get_service),
    render_service: RenderService = Depends(get_render_service),
) -> ProjectResponse:
    try:
        project = service.get_project(project_id)
    except ValueError as exc:
        raise AppError("project_not_found", str(exc), status.HTTP_404_NOT_FOUND, {"project_id": str(project_id)}) from exc

    if project.status == ProjectStatus.RENDERING:
        raise AppError("render_in_progress", "Project is already rendering", status.HTTP_409_CONFLICT, {"project_id": str(project_id)})

    service.mark_rendering(project)
    try:
        await render_service.render_project(project)
    except Exception as exc:
        service.set_status(project, ProjectStatus.OUTLINED)
        raise AppError(
            "render_failed",
            "Render failed",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            {"project_id": str(project_id)},
        ) from exc
    updated = service.mark_rendered(project)
    return ProjectResponse.model_validate(updated)


@router.get("/{project_id}/export")
def export_project(
    project_id: UUID,
    service: ProjectService = Depends(get_service),
    export_service: ExportService = Depends(get_export_service),
) -> StreamingResponse:
    try:
        project = service.get_project(project_id)
    except ValueError as exc:
        raise AppError("project_not_found", str(exc), status.HTTP_404_NOT_FOUND, {"project_id": str(project_id)}) from exc

    buffer = export_service.build_zip(project)
    filename = f"{_slugify(project.title)}.zip"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(buffer, media_type="application/zip", headers=headers)
