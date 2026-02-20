from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse, StreamingResponse
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
from app.services.render_service import RenderService, ROLE_KEY_MAP, FAMILY_MAP
from app.services.template_service import template_registry
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


@router.post("/{project_id}/render", status_code=status.HTTP_202_ACCEPTED)
async def render_project_route(
    project_id: UUID,
    debug: int = Query(0, description="Set to 1 to save debug HTML and failed screenshots"),
    service: ProjectService = Depends(get_service),
    render_service: RenderService = Depends(get_render_service),
):
    try:
        project = service.get_project(project_id)
    except ValueError as exc:
        raise AppError("project_not_found", str(exc), status.HTTP_404_NOT_FOUND, {"project_id": str(project_id)}) from exc

    if project.status == ProjectStatus.RENDERING:
        raise AppError("render_in_progress", "Project is already rendering", status.HTTP_409_CONFLICT, {"project_id": str(project_id)})

    service.mark_rendering(project)
    try:
        results = await render_service.render_project(project, debug=bool(debug))
    except AppError as exc:
        service.set_status(project, ProjectStatus.OUTLINED)
        # Re-raise with full details (including partial results)
        raise
    except Exception as exc:
        service.set_status(project, ProjectStatus.OUTLINED)
        raise AppError(
            "render_failed",
            f"Render failed: {exc}",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            {"project_id": str(project_id)},
        ) from exc

    # Check if any slides failed
    failed = [r for r in results if not r.ok]
    if failed:
        service.set_status(project, ProjectStatus.OUTLINED)
        return JSONResponse(
            status_code=status.HTTP_207_MULTI_STATUS,
            content={
                "status": "partial_failure",
                "project_id": str(project_id),
                "total": len(results),
                "failed": len(failed),
                "slides": [r.to_dict() for r in results],
                "failed_slides": [r.to_dict() for r in failed],
            },
        )

    updated = service.mark_rendered(project)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "ok",
            "project_id": str(project_id),
            "total": len(results),
            "failed": 0,
            "slides": [r.to_dict() for r in results],
            "template_selection": updated.template_selection,
        },
    )


@router.get("/{project_id}/template-trace")
def template_trace(
    project_id: UUID,
    service: ProjectService = Depends(get_service),
):
    """Diagnostic endpoint: shows the full template resolution chain per slide."""
    try:
        project = service.get_project(project_id)
    except ValueError as exc:
        raise AppError("project_not_found", str(exc), status.HTTP_404_NOT_FOUND, {"project_id": str(project_id)}) from exc

    selection = project.template_selection or {}
    family = selection.get("family") if isinstance(selection, dict) else None
    format_key = FAMILY_MAP.get(project.type, "carousel")

    slides_trace = []
    for slide in sorted(project.slides, key=lambda s: s.index):
        role_key = ROLE_KEY_MAP.get(project.type, {}).get(slide.role)
        payload_tid = slide.payload.get("template_id") if slide.payload else None
        payload_tv = slide.payload.get("template_variant") if slide.payload else None

        # Resolve what render would actually use
        resolved_id = payload_tv or payload_tid
        resolved_path = None
        if not resolved_id and family and family != "classic":
            try:
                variants = template_registry.registry[family][format_key][role_key]
                resolved_id = variants[0]["id"] if variants else None
            except KeyError:
                resolved_id = None
        elif not resolved_id:
            try:
                variants = template_registry.registry[format_key][role_key]
                resolved_id = variants[0]["id"] if variants else None
            except KeyError:
                resolved_id = None

        # Get file path
        if resolved_id:
            try:
                if family and family != "classic":
                    variant = template_registry.get_variant(family, role_key, resolved_id, format_key=format_key)
                else:
                    variant = template_registry.get_variant(format_key, role_key, resolved_id)
                resolved_path = variant.file
            except Exception:
                resolved_path = "NOT_FOUND"

        slides_trace.append({
            "index": slide.index,
            "role": slide.role.value,
            "project_family": family,
            "project_format": format_key,
            "payload_template_id": payload_tid,
            "payload_template_variant": payload_tv,
            "resolved_template_id": resolved_id,
            "template_path": resolved_path,
        })

    return {
        "project_id": str(project_id),
        "family": family,
        "format": format_key,
        "slides_count": project.slides_count,
        "slides": slides_trace,
    }


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
