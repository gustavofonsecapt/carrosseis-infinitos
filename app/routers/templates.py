from __future__ import annotations

from fastapi import APIRouter

from app.services.template_service import template_registry

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.get("", response_model=dict)
def list_templates() -> dict:
    return template_registry.list_templates()
