from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response, JSONResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.services.template_service import template_registry
from app.services.render_service import RenderService

router = APIRouter(prefix="/api/templates", tags=["templates"])
logger = logging.getLogger(__name__)

CACHE_DIR = settings.data_dir / "preview_cache"


def get_render_service(db: Session = Depends(get_db)) -> RenderService:
    return RenderService(db)


def _template_content_hash(template_id: str, format_key: str) -> str:
    """Hash template HTML + CSS files to detect changes."""
    render_svc = RenderService.__new__(RenderService)
    try:
        variant, family_key, role_key = render_svc._find_variant_by_id(template_id, format_key)
    except Exception:
        return "unknown"

    hasher = hashlib.md5()
    template_path = Path(variant.file)
    if template_path.exists():
        hasher.update(template_path.read_bytes())

    # Hash linked CSS files
    for css_candidate in template_path.parent.glob("*.css"):
        hasher.update(css_candidate.read_bytes())

    # Hash family-level CSS if applicable
    if family_key not in {"carousel", "stories"}:
        family_css_dir = settings.templates_dir / "families" / family_key
        for css_file in family_css_dir.glob("*.css"):
            hasher.update(css_file.read_bytes())

    return hasher.hexdigest()


def _get_cached_preview(template_id: str, content_hash: str) -> bytes | None:
    cache_file = CACHE_DIR / f"{template_id}_{content_hash}.png"
    meta_file = CACHE_DIR / f"{template_id}_{content_hash}.json"
    if cache_file.exists() and meta_file.exists():
        return cache_file.read_bytes(), json.loads(meta_file.read_text())
    return None


def _save_cached_preview(template_id: str, content_hash: str, png_bytes: bytes, meta: dict):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    # Clean old caches for this template
    for old in CACHE_DIR.glob(f"{template_id}_*.png"):
        old.unlink(missing_ok=True)
    for old in CACHE_DIR.glob(f"{template_id}_*.json"):
        old.unlink(missing_ok=True)
    cache_file = CACHE_DIR / f"{template_id}_{content_hash}.png"
    meta_file = CACHE_DIR / f"{template_id}_{content_hash}.json"
    cache_file.write_bytes(png_bytes)
    meta_file.write_text(json.dumps(meta), encoding="utf-8")


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
    no_cache: bool = Query(False, description="Bypass cache"),
    render_service: RenderService = Depends(get_render_service),
):
    """Render a single template and return metadata as JSON (PNG as base64)."""
    import base64

    content_hash = _template_content_hash(template_id, format_key)

    # Try cache (only for default/no custom payload)
    if not payload and not no_cache:
        cached = _get_cached_preview(template_id, content_hash)
        if cached:
            png_bytes, meta = cached
            logger.info("Cache HIT for %s (hash=%s)", template_id, content_hash[:8])
            return JSONResponse(content={
                "image_base64": base64.b64encode(png_bytes).decode(),
                "warnings": meta.get("warnings", []),
                "slot_info": meta.get("slot_info", {}),
                "cached": True,
            })

    logger.info("Cache MISS for %s (hash=%s), rendering via Playwright", template_id, content_hash[:8])

    png_bytes, warnings, slot_info = await render_service.render_template_preview(
        template_id=template_id,
        payload=payload,
        format_key=format_key,
    )

    # Save to cache (only default payloads)
    if not payload:
        _save_cached_preview(template_id, content_hash, png_bytes, {
            "warnings": warnings,
            "slot_info": slot_info,
        })

    return JSONResponse(content={
        "image_base64": base64.b64encode(png_bytes).decode(),
        "warnings": warnings,
        "slot_info": slot_info,
        "cached": False,
    })


@router.delete("/preview-cache")
def clear_preview_cache():
    """Clear all cached preview PNGs."""
    count = 0
    if CACHE_DIR.exists():
        for f in CACHE_DIR.iterdir():
            f.unlink(missing_ok=True)
            count += 1
    return {"cleared": count}
