from __future__ import annotations

import base64
import mimetypes
import logging
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import UUID
import os

from bs4 import BeautifulSoup, Tag
from fastapi import status

from app.core.errors import AppError
from playwright.async_api import Page, async_playwright
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Project, ProjectType, Slide, SlideRole
from app.services.template_service import ScrimConfig, TemplateVariant, template_registry

Viewport = tuple[int, int]

ROLE_KEY_MAP = {
    ProjectType.CAROUSEL: {
        SlideRole.COVER: "cover",
        SlideRole.BODY: "body",
        SlideRole.CTA: "cta",
    },
    ProjectType.STORIES_10X: {
        SlideRole.FRAME: "frame",
        SlideRole.FRAME_CTA: "cta",
    },
}

FAMILY_MAP = {
    ProjectType.CAROUSEL: "carousel",
    ProjectType.STORIES_10X: "stories",
}

VIEWPORTS: dict[ProjectType, Viewport] = {
    ProjectType.CAROUSEL: (1080, 1350),
    ProjectType.STORIES_10X: (1080, 1920),
}


logger = logging.getLogger(__name__)


# ── Per-slide render result ────────────────────────────────────────

@dataclass
class SlideRenderResult:
    index: int
    ok: bool
    render_path: str | None = None
    template_id: str | None = None
    template_path: str | None = None
    warnings: list[str] = field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"index": self.index, "ok": self.ok}
        if self.render_path:
            d["render_path"] = self.render_path
        if self.template_id:
            d["template_id"] = self.template_id
        if self.template_path:
            d["template_path"] = self.template_path
        if self.warnings:
            d["warnings"] = self.warnings
        if self.error_code:
            d["error_code"] = self.error_code
        if self.error_message:
            d["error_message"] = self.error_message
        return d


# ── Appearance resolution helpers ──────────────────────────────────

def _resolve_effective_theme(variant: TemplateVariant, appearance: dict) -> tuple[str, list[str]]:
    warnings = []
    theme_override = appearance.get("theme", "auto")
    if theme_override in ("light", "dark"):
        effective = theme_override
        warnings.append(f"applied_theme_{effective}")
    else:
        effective = variant.theme
    return effective, warnings


def _resolve_effective_scrim(
    variant: TemplateVariant,
    appearance: dict,
    has_image: bool = False,
) -> tuple[ScrimConfig, list[str]]:
    warnings = []
    scrim_override = appearance.get("scrim", {})

    default_enabled = variant.scrim.enabled
    if has_image and "enabled" not in scrim_override:
        default_enabled = True
        if not variant.scrim.enabled:
            warnings.append("scrim_auto_enabled_image_text")

    enabled = scrim_override.get("enabled", default_enabled)
    strength = scrim_override.get("strength", variant.scrim.strength)
    position = scrim_override.get("position", variant.scrim.position)
    mode = scrim_override.get("mode", variant.scrim.scrim_mode)
    color_mode = variant.scrim.mode

    if "enabled" in scrim_override and scrim_override["enabled"] != variant.scrim.enabled:
        warnings.append("scrim_disabled" if not enabled else "scrim_enabled")
    if "strength" in scrim_override and scrim_override["strength"] != variant.scrim.strength:
        warnings.append("scrim_strength_changed")

    if not enabled:
        if not has_image:
            warnings.append("scrim_disabled_reason:no_image")
        elif "enabled" in scrim_override and not scrim_override["enabled"]:
            warnings.append("scrim_disabled_reason:user_disabled")
        else:
            warnings.append("scrim_disabled_reason:template_scrim_disabled")

    return ScrimConfig(
        enabled=enabled,
        mode=color_mode,
        strength=strength,
        position=position,
        scrim_mode=mode,
    ), warnings


# ── Scrim CSS generators ───────────────────────────────────────────

def _scrim_gradient_value(scrim: ScrimConfig, effective_theme: str) -> str:
    if effective_theme == "dark" or scrim.mode == "dark":
        base_color = f"rgba(0, 0, 0, {scrim.strength})"
        fade_color = "rgba(0, 0, 0, 0)"
    else:
        base_color = f"rgba(255, 255, 255, {scrim.strength})"
        fade_color = "rgba(255, 255, 255, 0)"

    pos = scrim.position
    if pos == "bottom":
        return f"linear-gradient(to top, {base_color} 0%, {base_color} 30%, {fade_color} 70%)"
    elif pos == "top":
        return f"linear-gradient(to bottom, {base_color} 0%, {base_color} 30%, {fade_color} 70%)"
    else:
        return f"linear-gradient(to bottom, {fade_color} 0%, {base_color} 25%, {base_color} 75%, {fade_color} 100%)"


def _scrim_box_value(scrim: ScrimConfig, effective_theme: str) -> str:
    if effective_theme == "dark" or scrim.mode == "dark":
        return f"rgba(0, 0, 0, {scrim.strength})"
    else:
        return f"rgba(255, 255, 255, {scrim.strength})"


class RenderService:
    def __init__(self, db: Session):
        self.db = db
        self.data_dir = settings.data_dir

    async def render_project(self, project: Project, *, debug: bool = False) -> list[SlideRenderResult]:
        if not project.slides:
            raise AppError("invalid_state", "Project has no slides", status.HTTP_400_BAD_REQUEST)

        viewport = VIEWPORTS[project.type]
        log_path = self._render_log_path(project.id)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        results: list[SlideRenderResult] = []
        failed_count = 0

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page(viewport={"width": viewport[0], "height": viewport[1]})
                with log_path.open("a", encoding="utf-8") as log_file:
                    log_file.write(f"\\n--- RENDER START: {datetime.utcnow().isoformat()} ---\\n")
                    for slide in sorted(project.slides, key=lambda s: s.index):
                        result = await self._render_slide_safe(page, project, slide, log_file, debug=debug)
                        results.append(result)
                        if not result.ok:
                            failed_count += 1
                await browser.close()
        except Exception as exc:
            logger.exception("Browser-level render failure for project %s", project.id)
            raise AppError(
                "render_browser_crash",
                f"Playwright crashed: {exc}",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                {
                    "project_id": str(project.id),
                    "completed_slides": [r.to_dict() for r in results],
                    "traceback": traceback.format_exc(),
                },
            ) from exc

        self.db.commit()

        if failed_count > 0:
            logger.warning("Render completed with %d/%d failures for project %s", failed_count, len(results), project.id)

        return results

    async def _render_slide_safe(
        self, page: Page, project: Project, slide: Slide, log_file, *, debug: bool = False
    ) -> SlideRenderResult:
        started = perf_counter()
        try:
            variant, source = self._resolve_variant(project, slide)

            # ─── DIAGNOSTIC LOGGING (START) ────────
            image_path_str = str(slide.image_path) if slide.image_path else "N/A"
            image_exists = "N/A"
            if slide.image_path:
                full_image_path = settings.data_dir.parent / slide.image_path.lstrip("/")
                image_exists = "OK" if os.path.exists(full_image_path) else "MISSING"

            log_file.write(f"""
--- SLIDE {slide.index} DIAGNOSTICS ---
  - Role:           {slide.role.value}
  - Image Path:     {image_path_str}
  - Image Exists:   {image_exists}
  - Variant Source: {source}
  - Variant ID:     {variant.id}
  - Variant uses_image: {variant.uses_image}
  - Payload:        {slide.payload}
--------------------------------
""")
            # ─── DIAGNOSTIC LOGGING (END) ──────────

            html_content, warnings = self._build_html(slide, variant)
            html_path, png_path = self._target_paths(project.id, slide.index)
            html_path.write_text(html_content, encoding="utf-8")

            if debug:
                debug_dir = self.data_dir / "projects" / str(project.id) / "renders" / "html_debug"
                debug_dir.mkdir(parents=True, exist_ok=True)
                debug_path = debug_dir / f"slide_{slide.index:02d}.html"
                debug_path.write_text(html_content, encoding="utf-8")

            await page.set_content(html_content, wait_until="domcontentloaded")

            try:
                await page.wait_for_function("() => document.fonts.ready.then(() => true)", timeout=3000)
            except Exception:
                warnings.append("font_wait_timeout")

            try:
                await page.wait_for_function(
                    """
                    () => Array.from(document.images)
                        .filter(img => {
                            const src = img.getAttribute('src') || '';
                            if (!src || src.startsWith('data:')) return false;
                            return true;
                        })
                        .every(img => img.complete && img.naturalWidth > 0)
                    """,
                    timeout=6000,
                )
            except Exception:
                warnings.append("image_wait_timeout")

            await page.wait_for_timeout(150)
            await page.screenshot(path=str(png_path))

            duration = perf_counter() - started
            slide.render_path = str(png_path.relative_to(settings.data_dir.parent))
            slide.warnings = warnings if warnings else None
            self.db.add(slide)

            log_entry = (
                f"{datetime.utcnow().isoformat()} slide={slide.index} role={slide.role.value} "
                f"template_id={variant.id} template_path={variant.file} "
                f"theme={variant.theme} "
                f"scrim={'yes' if variant.scrim.enabled else 'no'} "
                f"duration={duration:.3f}s "
                f"warnings={','.join(warnings) if warnings else 'none'}\\n"
            )
            log_file.write(log_entry)

            return SlideRenderResult(
                index=slide.index,
                ok=True,
                render_path=slide.render_path,
                template_id=variant.id,
                template_path=variant.file,
                warnings=warnings,
            )

        except AppError as exc:
            duration = perf_counter() - started
            logger.error("Slide %d render failed: %s - %s", slide.index, exc.code, exc.message)
            log_file.write(
                f"{datetime.utcnow().isoformat()} slide={slide.index} ERROR code={exc.code} msg={exc.message} duration={duration:.3f}s\\n"
            )

            if debug:
                try:
                    debug_dir = self.data_dir / "projects" / str(project.id) / "renders" / "html_debug"
                    debug_dir.mkdir(parents=True, exist_ok=True)
                    await page.screenshot(path=str(debug_dir / f"slide_{slide.index:02d}_failed.png"))
                except Exception:
                    pass

            return SlideRenderResult(
                index=slide.index,
                ok=False,
                error_code=exc.code,
                error_message=exc.message,
                warnings=[],
            )

        except Exception as exc:
            duration = perf_counter() - started
            tb = traceback.format_exc()
            logger.exception("Unexpected error rendering slide %d", slide.index)
            log_file.write(
                f"{datetime.utcnow().isoformat()} slide={slide.index} EXCEPTION {exc} duration={duration:.3f}s\\n"
            )

            if debug:
                try:
                    debug_dir = self.data_dir / "projects" / str(project.id) / "renders" / "html_debug"
                    debug_dir.mkdir(parents=True, exist_ok=True)
                    await page.screenshot(path=str(debug_dir / f"slide_{slide.index:02d}_failed.png"))
                except Exception:
                    pass

            return SlideRenderResult(
                index=slide.index,
                ok=False,
                error_code="unexpected_error",
                error_message=str(exc),
                warnings=[],
            )

    async def render_template_preview(
        self, template_id: str, payload: dict[str, Any] | None = None, format_key: str = "carousel"
    ) -> tuple[bytes, list[str], dict[str, Any]]:
        variant, family_key, role_key = self._find_variant_by_id(template_id, format_key)

        try:
            if family_key not in {"carousel", "stories"}:
                slot_schema = template_registry.get_family_slots_for_role(family_key, format_key, role_key)
            else:
                slot_schema = template_registry.get_slots(f"{format_key}/{role_key}")
        except Exception:
            slot_schema = {"slots": {}}

        if not payload:
            payload = self._build_mock_payload(slot_schema, role_key)

        all_slots = slot_schema.get("slots", {})
        missing_slots = [k for k in all_slots if k not in payload and all_slots[k].get("required")]
        warnings: list[str] = [f"slot_missing:{s}" for s in missing_slots]

        mock_slide = type("MockSlide", (), {
            "index": 1,
            "role": SlideRole.COVER,
            "payload": payload,
            "image_path": None,
        })()

        html_content, build_warnings = self._build_html(mock_slide, variant)
        warnings.extend(build_warnings)

        viewport = VIEWPORTS.get(
            ProjectType.CAROUSEL if format_key == "carousel" else ProjectType.STORIES_10X,
            (1080, 1350),
        )

        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(viewport={"width": viewport[0], "height": viewport[1]})
            await page.set_content(html_content, wait_until="domcontentloaded")
            try:
                await page.wait_for_function("() => document.fonts.ready.then(() => true)", timeout=3000)
            except Exception:
                warnings.append("font_wait_timeout")
            await page.wait_for_timeout(200)
            png_bytes = await page.screenshot()
            await browser.close()

        slot_info = {
            "template_id": variant.id,
            "template_path": variant.file,
            "template_label": variant.label,
            "theme": variant.theme,
            "available_slots": list(all_slots.keys()),
            "filled_slots": [k for k in all_slots if k in payload],
            "missing_required": missing_slots,
        }

        return png_bytes, warnings, slot_info

    def _find_variant_by_id(self, template_id: str, format_key: str) -> tuple[TemplateVariant, str, str]:
        registry = template_registry.registry

        for family_key, family_data in registry.items():
            if family_key in {"carousel", "stories"}:
                for role_key, variants in family_data.items():
                    if isinstance(variants, list):
                        for v in variants:
                            if v["id"] == template_id:
                                variant = template_registry.get_variant(family_key, role_key, template_id)
                                return variant, family_key, role_key
            else:
                fmt_data = family_data.get(format_key, {})
                for role_key, variants in fmt_data.items():
                    if isinstance(variants, list):
                        for v in variants:
                            if v["id"] == template_id:
                                variant = template_registry.get_variant(family_key, role_key, template_id, format_key=format_key)
                                return variant, family_key, role_key

        raise AppError("template_not_found", f"Template '{template_id}' not found in registry", status.HTTP_404_NOT_FOUND)

    _MOCK_DATA = {
        "cover": {
            "brand": "ContentForge",
            "category": "MARKETING DIGITAL",
            "kicker": "GUIA COMPLETO",
            "title": "7 estratégias que triplicaram meu engajamento",
            "subtitle": "O passo a passo que ninguém te conta sobre crescimento orgânico",
            "number": "01/08",
            "footer_note": "@contentforge",
        },
        "body": {
            "brand": "ContentForge",
            "category": "DICA #3",
            "kicker": "ESTRATÉGIA",
            "title": "Consistência vence perfeição",
            "subtitle": "Por que postar 4x por semana supera 1 post perfeito",
            "body": "A maioria dos criadores trava buscando o post perfeito. Dados mostram que contas que publicam com regularidade crescem 3x mais rápido, mesmo com qualidade mediana.",
            "bullets": [
                "Defina um calendário editorial realista",
                "Use templates para agilizar a produção",
                "Reaproveite conteúdo em formatos diferentes",
                "Analise métricas semanalmente",
            ],
            "number": "03/08",
            "footer_note": "@contentforge",
        },
        "cta": {
            "brand": "ContentForge",
            "cta_title": "Quer o checklist completo?",
            "cta_body": "Responda 'CHECKLIST' no DM e receba o guia gratuito com as 7 estratégias detalhadas.",
            "cta_button": "Responder no DM",
            "number": "08/08",
            "footer_note": "@contentforge",
        },
        "frame": {
            "brand": "ContentForge",
            "title": "Você está perdendo alcance sem saber",
            "subtitle": "Descubra o que mudou no algoritmo",
            "body": "O Instagram prioriza conteúdo que gera salvamentos e compartilhamentos, não apenas curtidas.",
            "number": "03/10",
        },
        "frame_cta": {
            "brand": "ContentForge",
            "title": "Quer dominar o algoritmo?",
            "cta": "Responda ALCANCE no DM",
            "trigger_word": "ALCANCE",
            "number": "10/10",
        },
    }

    def _build_mock_payload(self, slot_schema: dict[str, Any], role_key: str) -> dict[str, Any]:
        slots = slot_schema.get("slots", {})
        mock_defaults = self._MOCK_DATA.get(role_key, {})
        payload: dict[str, Any] = {}

        for key, spec in slots.items():
            if key == "image":
                continue
            max_chars = spec.get("max_chars", 40)

            if key == "bullets":
                max_items = spec.get("max_items", 3)
                max_per_item = spec.get("max_chars_per_item", 48)
                source_bullets = mock_defaults.get("bullets", [f"Ponto importante {i+1}" for i in range(max_items)])
                payload["bullets"] = [b[:max_per_item] for b in source_bullets[:max_items]]
            elif key in mock_defaults:
                payload[key] = str(mock_defaults[key])[:max_chars]
            else:
                desc = spec.get("description", key)
                payload[key] = desc[:max_chars]

        return payload

    def _resolve_variant(self, project: Project, slide: Slide) -> tuple[TemplateVariant, str]:
        selection = project.template_selection or {}
        role_key = ROLE_KEY_MAP[project.type].get(slide.role)
        if not role_key:
            raise AppError("template_not_found", f"Unsupported role {slide.role}", status.HTTP_400_BAD_REQUEST)

        format_key = FAMILY_MAP[project.type]
        family_name = selection.get("family") if isinstance(selection, dict) else None

        source = "unknown"
        per_slide_variant = slide.payload.get("template_variant") if slide.payload else None
        selected_id = per_slide_variant
        if selected_id:
            source = "slide_payload_variant"

        if not selected_id:
            selected_id = slide.payload.get("template_id") if slide.payload else None
            if selected_id:
                source = "slide_payload_id"

        if not selected_id:
            if isinstance(selection, dict):
                format_block = selection.get(format_key)
                if isinstance(format_block, dict):
                    selected_id = format_block.get(role_key)
                else:
                    selected_id = selection.get(role_key)
                if selected_id:
                    source = "project_selection"

        if slide.image_path and source != "slide_payload_variant":
            current_variant_supports_image = False
            if selected_id:
                try:
                    temp_variant = (
                        template_registry.get_variant(family_name, role_key, selected_id, format_key=format_key)
                        if family_name and family_name != "classic"
                        else template_registry.get_variant(format_key, role_key, selected_id)
                    )
                    current_variant_supports_image = temp_variant.uses_image
                except AppError:
                    current_variant_supports_image = False

            if not current_variant_supports_image:
                variants = []
                try:
                    if family_name and family_name != "classic":
                        variants = template_registry.registry[family_name][format_key][role_key]
                    else:
                        variants = template_registry.registry[format_key][role_key]
                except KeyError:
                    pass

                image_capable_variant = next((v for v in variants if v.get("uses_image")), None)
                if image_capable_variant:
                    selected_id = image_capable_variant["id"]
                    source = f"auto_promoted_from_{source}"

        if family_name and family_name != "classic":
            if not selected_id:
                try:
                    family_variants = template_registry.registry[family_name][format_key][role_key]
                    selected_id = family_variants[0]["id"]
                    source = "family_default"
                except (KeyError, IndexError):
                    available_roles = list(template_registry.registry.get(family_name, {}).get(format_key, {}).keys())
                    raise AppError(
                        "template_not_found",
                        f"Family '{family_name}' has no {format_key}/{role_key} variants. Available: {available_roles}",
                        status.HTTP_400_BAD_REQUEST,
                    )
            return template_registry.get_variant(family_name, role_key, selected_id, format_key=format_key), source
        else:
            if not selected_id:
                family_variants = template_registry.registry[format_key][role_key]
                selected_id = family_variants[0]["id"]
                source = "classic_default"
            return template_registry.get_variant(format_key, role_key, selected_id), source

    def _build_html(self, slide: Slide, variant: TemplateVariant) -> tuple[str, list[str]]:
        template_path = Path(variant.file)
        if not template_path.exists():
            raise AppError(
                "template_file_missing",
                f"Template file not found: {variant.file}",
                status.HTTP_400_BAD_REQUEST,
                {"template_id": variant.id, "path": str(variant.file)},
            )

        html = template_path.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")
        warnings: list[str] = []

        appearance = slide.payload.get("appearance", {})
        has_image = bool(slide.payload.get("image") or slide.image_path)
        effective_theme, theme_warnings = _resolve_effective_theme(variant, appearance)
        warnings.extend(theme_warnings)

        effective_scrim, scrim_warnings = _resolve_effective_scrim(variant, appearance, has_image=has_image)
        warnings.extend(scrim_warnings)

        for link in soup.find_all("link", rel="stylesheet"):
            href = link.get("href")
            if not href:
                link.decompose()
                continue
            css_path = (template_path.parent / href).resolve()
            if css_path.exists():
                style_tag = soup.new_tag("style")
                style_tag.string = css_path.read_text(encoding="utf-8")
                link.replace_with(style_tag)
            else:
                link.decompose()

        slide_el = soup.select_one(".slide")
        if slide_el:
            classes = slide_el.get("class", [])
            if "dark" in classes:
                classes.remove("dark")

            theme_class = f"theme-{effective_theme}"
            if theme_class not in classes:
                classes.append(theme_class)
            slide_el["class"] = classes

            existing_style = slide_el.get("style", "")

            if effective_scrim.enabled and has_image:
                if effective_scrim.scrim_mode == "box":
                    scrim_val = _scrim_box_value(effective_scrim, effective_theme)
                    existing_style += f" --scrim-bg: transparent; --scrim-box-bg: {scrim_val};"
                    content_el = slide_el.select_one(".content")
                    if content_el:
                        box_div = soup.new_tag("div", **{"class": "scrim-box"})
                        content_el.insert_before(box_div)
                    warnings.append("applied_scrim_box")
                else:
                    scrim_val = _scrim_gradient_value(effective_scrim, effective_theme)
                    existing_style += f" --scrim-bg: {scrim_val};"
                    warnings.append(f"applied_scrim_gradient_{effective_scrim.position}")
                logger.info("Injected scrim (mode=%s, strength=%.2f, pos=%s) for slide %s",
                             effective_scrim.scrim_mode, effective_scrim.strength,
                             effective_scrim.position, slide.index)
            elif not effective_scrim.enabled:
                existing_style += " --scrim-bg: transparent;"

            if existing_style.strip():
                slide_el["style"] = existing_style.strip()

        # Tradução de chaves da IA para o Premium
        SLOT_ALIASES = {
            "title": ["headline"],
            "subtitle": ["subhead", "support"],
            "cta_button": ["cta"],
            "cta_title": ["headline", "title"],
            "cta_body": ["subhead", "body"]
        }

        for node in soup.select("[data-slot]"):
            slot_name = node.get("data-slot")
            value = slide.payload.get(slot_name)

            if value is None and slot_name in SLOT_ALIASES:
                for alias in SLOT_ALIASES[slot_name]:
                    if slide.payload.get(alias):
                        value = slide.payload.get(alias)
                        break

            # Validação rigorosa: strings vazias ou nulas viram ghost text se não forem apagadas
            is_empty = False
            if value is None:
                is_empty = True
            elif isinstance(value, str) and not value.strip():
                is_empty = True
            elif isinstance(value, list) and len(value) == 0:
                is_empty = True

            if is_empty:
                if node.name == "img":
                    image_path = slide.image_path
                    if image_path:
                        src, warning = self._asset_uri(template_path, image_path)
                        node["src"] = src
                        if warning:
                            warnings.append(f"{slot_name}:{warning}")
                else:
                    node.clear()
                continue

            if node.name == "img":
                image_path = slide.image_path or value
                if image_path:
                    src, warning = self._asset_uri(template_path, image_path)
                    node["src"] = src
                    if warning:
                        warnings.append(f"{slot_name}:{warning}")
                continue

            if isinstance(value, list):
                bullets_text = "\\n".join(f"• {item}" for item in value)
                node.clear()
                node.append(bullets_text)
            else:
                node.clear()
                node.append(str(value))

        return str(soup), warnings

    def _asset_uri(self, template_path: Path, value: str | None) -> tuple[str, str | None]:
        placeholder = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        if not value:
            return placeholder, "image_missing"
        if value.startswith(("http://", "https://")):
            return placeholder, "image_blocked_external"

        normalized = value.lstrip("/")

        candidates = [Path(value), self.data_dir / normalized, self.data_dir.parent / normalized, template_path.parent / normalized]
        for candidate in candidates:
            resolved = candidate.resolve()
            if not resolved.exists() or not resolved.is_file():
                continue
            mime, _ = mimetypes.guess_type(resolved.name)
            mime = mime or "image/png"
            encoded = base64.b64encode(resolved.read_bytes()).decode("ascii")
            return f"data:{mime};base64,{encoded}", None

        return placeholder, "image_missing_disk"

    def _target_paths(self, project_id: UUID | str, index: int) -> tuple[Path, Path]:
        base = self.data_dir / "projects" / str(project_id) / "renders"
        html_dir = base / "html"
        png_dir = base / "png"
        html_dir.mkdir(parents=True, exist_ok=True)
        png_dir.mkdir(parents=True, exist_ok=True)
        html_path = html_dir / f"slide_{index:02d}.html"
        png_path = png_dir / f"slide_{index:02d}.png"
        return html_path, png_path

    def _render_log_path(self, project_id: UUID | str) -> Path:
        base = self.data_dir / "projects" / str(project_id) / "renders"
        base.mkdir(parents=True, exist_ok=True)
        return base / "render.log"
