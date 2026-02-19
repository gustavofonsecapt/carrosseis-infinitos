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


# Known family keys in registry.json (top-level keys that are families, not formats)
_FORMAT_KEYS = {"carousel", "stories"}


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

    def list_families(self) -> dict[str, Any]:
        """Return available template families with their variations."""
        families: dict[str, Any] = {}
        for key, value in self.registry.items():
            if key in _FORMAT_KEYS:
                # Legacy flat layouts — group as "classic"
                continue
            # Family key (e.g. premium_editorial_v1)
            families[key] = value

        # Also expose classic layouts as a virtual family
        classic: dict[str, Any] = {}
        for fmt in _FORMAT_KEYS:
            if fmt in self.registry:
                classic[fmt] = self.registry[fmt]
        if classic:
            families["classic"] = classic

        return families

    def get_variant(self, family_or_format: str, role_key: str, variant_id: str, *, format_key: str | None = None) -> TemplateVariant:
        """
        Resolve a template variant.

        For legacy layouts:  get_variant("carousel", "cover", "cover_v1")
        For families:        get_variant("premium_editorial_v1", "cover", "pe_cover_v1", format_key="carousel")
        """
        try:
            if format_key and family_or_format not in _FORMAT_KEYS:
                # Family-based lookup: registry[family][format][role]
                variants_list = self.registry[family_or_format][format_key][role_key]
            else:
                # Legacy flat lookup: registry[format][role]
                variants_list = self.registry[family_or_format][role_key]
        except KeyError as exc:
            raise AppError("template_not_found", "Template family/role not found", status.HTTP_404_NOT_FOUND) from exc

        for variant in variants_list:
            if variant["id"] == variant_id:
                file_path = self._templates_root / variant["file"]
                if not file_path.exists():
                    raise AppError("template_not_found", f"Template file missing: {file_path}", status.HTTP_500_INTERNAL_SERVER_ERROR)
                return TemplateVariant(id=variant_id, file=str(file_path), label=variant["label"])

        raise AppError("template_not_found", f"Template variant '{variant_id}' not found", status.HTTP_404_NOT_FOUND)

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
