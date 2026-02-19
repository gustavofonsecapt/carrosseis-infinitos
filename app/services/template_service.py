from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any

from fastapi import status

from app.core.errors import AppError

from app.core.config import settings


@dataclass
class TemplateVariant:
    id: str
    file: str
    label: str


class TemplateRegistry:
    def __init__(self, registry_path: Path, templates_root: Path):
        self._registry_path = registry_path
        self._templates_root = templates_root

    @cached_property
    def registry(self) -> dict[str, Any]:
        if not self._registry_path.exists():
            raise FileNotFoundError(f"Template registry not found: {self._registry_path}")
        with self._registry_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def list_templates(self) -> dict[str, Any]:
        return self.registry

    def get_variant(self, family: str, role: str, variant_id: str) -> TemplateVariant:
        try:
            family_group = self.registry[family][role]
        except KeyError as exc:
            raise AppError("template_not_found", "Template family/role not found", status.HTTP_404_NOT_FOUND) from exc

        for variant in family_group:
            if variant["id"] == variant_id:
                file_path = self._templates_root / variant["file"]
                if not file_path.exists():
                    raise AppError("template_not_found", "Template file missing", status.HTTP_500_INTERNAL_SERVER_ERROR)
                return TemplateVariant(id=variant_id, file=str(file_path), label=variant["label"])

        raise AppError("template_not_found", "Template variant not found", status.HTTP_404_NOT_FOUND)

    def get_slots(self, family: str) -> dict[str, Any]:
        slots_path = self._templates_root / "layouts" / family / "slots.json"
        if not slots_path.exists():
            raise AppError("template_not_found", "Template slots not found", status.HTTP_404_NOT_FOUND)
        with slots_path.open("r", encoding="utf-8") as f:
            return json.load(f)


template_registry = TemplateRegistry(
    registry_path=settings.templates_dir / "registry.json",
    templates_root=settings.templates_dir,
)
