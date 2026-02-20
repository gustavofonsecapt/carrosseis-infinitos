from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response, JSONResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.services.template_service import template_registry
from app.services.render_service import RenderService

router = APIRouter(prefix="/api/templates", tags=["templates"])


def get_render_service(db: Session = Depends(get_db)) -> RenderService:
    return RenderService(db)


@router.get("", response_model=dict)
def list_templates() -> dict:
    return template_registry.list_templates()


@router.get("/families", response_model=dict)
def list_families() -> dict:
    return template_registry.list_families()


@router.post("/{template_id}/preview")
async def preview_template(
    template_id: str,
    payload: dict[str, Any] | None = None,
    format_key: str = Query("carousel", description="Format: carousel or stories"),
    render_service: RenderService = Depends(get_render_service),
):
    """Render a single template with mock/provided data. Returns PNG + metadata."""
    png_bytes, warnings, slot_info = await render_service.render_template_preview(
        template_id=template_id,
        payload=payload,
        format_key=format_key,
    )

    # Return PNG with metadata in headers
    headers = {
        "X-Template-Id": slot_info["template_id"],
        "X-Template-Label": slot_info["template_label"],
        "X-Template-Theme": slot_info["theme"],
        "X-Warnings": ",".join(warnings) if warnings else "none",
        "X-Missing-Required": ",".join(slot_info["missing_required"]) if slot_info["missing_required"] else "none",
    }
    return Response(content=png_bytes, media_type="image/png", headers=headers)


@router.post("/{template_id}/preview/json")
async def preview_template_json(
    template_id: str,
    payload: dict[str, Any] | None = None,
    format_key: str = Query("carousel", description="Format: carousel or stories"),
    render_service: RenderService = Depends(get_render_service),
):
    """Render a single template and return metadata as JSON (PNG as base64)."""
    import base64

    png_bytes, warnings, slot_info = await render_service.render_template_preview(
        template_id=template_id,
        payload=payload,
        format_key=format_key,
    )

    return JSONResponse(content={
        "image_base64": base64.b64encode(png_bytes).decode(),
        "warnings": warnings,
        "slot_info": slot_info,
    })
