from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any

from fastapi import status

from app.core.errors import AppError
from app.core.config import settings


@dataclass
class ScrimConfig:
    enabled: bool = False
    mode: str = "soft"          # "soft" (light overlay) | "dark" (dark overlay)
    strength: float = 0.35      # opacity 0.0–1.0
    position: str = "bottom"    # "top" | "center" | "bottom"
    scrim_mode: str = "gradient" # "gradient" | "box"


@dataclass
class TemplateVariant:
    id: str
    file: str
    label: str
    theme: str = "light"          # "light" | "dark"
    scrim: ScrimConfig = field(default_factory=ScrimConfig)
    text_area: str = "center"     # "top" | "center" | "bottom"
    uses_image: bool = False       # se a variante possui slot de imagem dedicado


# Known format keys in registry.json (top-level keys that are formats, not families)
_FORMAT_KEYS = {"carousel", "stories"}


def _parse_scrim(raw: dict[str, Any] | None) -> ScrimConfig:
    if not raw:
        return ScrimConfig()
    return ScrimConfig(
        enabled=raw.get("enabled", False),
        mode=raw.get("mode", "soft"),
        strength=raw.get("strength", 0.35),
        position=raw.get("position", "bottom"),
        scrim_mode=raw.get("scrim_mode", raw.get("mode_type", "gradient")),
    )


def _parse_variant(v: dict[str, Any], file_path: Path) -> TemplateVariant:
    return TemplateVariant(
        id=v["id"],
        file=str(file_path),
        label=v["label"],
        theme=v.get("theme", "light"),
        scrim=_parse_scrim(v.get("scrim")),
        text_area=v.get("text_area", "center"),
        uses_image=v.get("uses_image", False),
    )


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
                continue
            families[key] = value

        classic: dict[str, Any] = {}
        for fmt in _FORMAT_KEYS:
            if fmt in self.registry:
                classic[fmt] = self.registry[fmt]
        if classic:
            families["classic"] = classic

        return families

    def get_variant(self, family_or_format: str, role_key: str, variant_id: str, *, format_key: str | None = None) -> TemplateVariant:
        """
        Resolve a template variant with full metadata (theme, scrim, text_area).

        For legacy layouts:  get_variant("carousel", "cover", "cover_v1")
        For families:        get_variant("premium_editorial_v1", "cover", "pe_cover_v1", format_key="carousel")
        """
        try:
            if format_key and family_or_format not in _FORMAT_KEYS:
                variants_list = self.registry[family_or_format][format_key][role_key]
            else:
                variants_list = self.registry[family_or_format][role_key]
        except KeyError as exc:
            raise AppError("template_not_found", "Template family/role not found", status.HTTP_404_NOT_FOUND) from exc

        for variant in variants_list:
            if variant["id"] == variant_id:
                file_path = self._templates_root / variant["file"]
                if not file_path.exists():
                    raise AppError("template_not_found", f"Template file missing: {file_path}", status.HTTP_500_INTERNAL_SERVER_ERROR)
                return _parse_variant(variant, file_path)

        raise AppError("template_not_found", f"Template variant '{variant_id}' not found", status.HTTP_404_NOT_FOUND)

    def get_slots(self, role_path: str) -> dict[str, Any]:
        """Load slots.json for a layout role path like 'carousel/cover'."""
        slots_path = self._templates_root / "layouts" / role_path / "slots.json"
        if not slots_path.exists():
            raise AppError("template_not_found", "Template slots not found", status.HTTP_404_NOT_FOUND)
        with slots_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def get_family_slots(self, family: str) -> dict[str, Any]:
        """Load slots.json for a template family (e.g. 'premium_editorial_v1')."""
        slots_path = self._templates_root / "families" / family / "slots.json"
        if not slots_path.exists():
            raise AppError("template_not_found", f"Family slots not found: {family}", status.HTTP_404_NOT_FOUND)
        with slots_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def get_family_slots_for_role(self, family: str, format_key: str, role: str) -> dict[str, Any]:
        """Load slots.json filtered to only the slots relevant for a specific role.

        Uses `primary_slots` from the variation definition + global slots (brand, number, image, footer_note).
        """
        full = self.get_family_slots(family)
        all_slots = full.get("slots", {})

        # Find the variation list for this format/role
        variations = full.get("variations", {}).get(format_key, {}).get(role, [])
        if not variations:
            # Fallback: return all slots
            return full

        # Gather primary_slots from the first variation (they share the same structure)
        primary = set()
        for v in variations:
            for s in v.get("primary_slots", []):
                primary.add(s)

        # Global slots always included
        global_slots = {"brand", "number", "image", "footer_note", "page_counter"}
        allowed = primary | global_slots

        filtered_slots = {k: v for k, v in all_slots.items() if k in allowed}
        result = dict(full)
        result["slots"] = filtered_slots
        return result


template_registry = TemplateRegistry(
    registry_path=settings.templates_dir / "registry.json",
    templates_root=settings.templates_dir,
)
