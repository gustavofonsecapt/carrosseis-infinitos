from __future__ import annotations

import base64
import logging
from datetime import datetime
from pathlib import Path
from time import perf_counter
from uuid import UUID

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


# ── Appearance resolution helpers ──────────────────────────────────

def _resolve_effective_theme(variant: TemplateVariant, appearance: dict) -> tuple[str, list[str]]:
    """Return (effective_theme, warnings)."""
    warnings = []
    theme_override = appearance.get("theme", "auto")
    if theme_override in ("light", "dark"):
        effective = theme_override
        warnings.append(f"applied_theme_{effective}")
    else:
        effective = variant.theme
    return effective, warnings


def _resolve_effective_scrim(variant: TemplateVariant, appearance: dict) -> tuple[ScrimConfig, list[str]]:
    """Merge slide appearance.scrim over variant defaults. Return (config, warnings)."""
    warnings = []
    scrim_override = appearance.get("scrim", {})

    enabled = scrim_override.get("enabled", variant.scrim.enabled)
    strength = scrim_override.get("strength", variant.scrim.strength)
    position = scrim_override.get("position", variant.scrim.position)
    mode = scrim_override.get("mode", variant.scrim.scrim_mode)
    # Determine color mode from effective theme (dark theme = dark scrim color)
    color_mode = variant.scrim.mode  # "soft" or "dark"

    if "enabled" in scrim_override and scrim_override["enabled"] != variant.scrim.enabled:
        warnings.append("scrim_disabled" if not enabled else "scrim_enabled")
    if "strength" in scrim_override and scrim_override["strength"] != variant.scrim.strength:
        warnings.append("scrim_strength_changed")

    return ScrimConfig(
        enabled=enabled,
        mode=color_mode,
        strength=strength,
        position=position,
        scrim_mode=mode,
    ), warnings


# ── Scrim CSS generators ───────────────────────────────────────────

def _scrim_gradient_value(scrim: ScrimConfig, effective_theme: str) -> str:
    """Generate a CSS gradient string for scrim overlay."""
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
    else:  # center
        return f"linear-gradient(to bottom, {fade_color} 0%, {base_color} 25%, {base_color} 75%, {fade_color} 100%)"


def _scrim_box_value(scrim: ScrimConfig, effective_theme: str) -> str:
    """Generate a solid translucent color for box scrim mode."""
    if effective_theme == "dark" or scrim.mode == "dark":
        return f"rgba(0, 0, 0, {scrim.strength})"
    else:
        return f"rgba(255, 255, 255, {scrim.strength})"


class RenderService:
    def __init__(self, db: Session):
        self.db = db
        self.data_dir = settings.data_dir

    async def render_project(self, project: Project) -> None:
        if not project.slides:
            raise AppError("invalid_state", "Project has no slides", status.HTTP_400_BAD_REQUEST)

        viewport = VIEWPORTS[project.type]
        log_path = self._render_log_path(project.id)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page(viewport={"width": viewport[0], "height": viewport[1]})
                with log_path.open("a", encoding="utf-8") as log_file:
                    for slide in sorted(project.slides, key=lambda s: s.index):
                        started = perf_counter()
                        png_path, variant, warnings = await self._render_slide(page, project, slide)
                        duration = perf_counter() - started
                        slide.render_path = str(png_path.relative_to(settings.data_dir.parent))
                        self.db.add(slide)

                        log_entry = (
                            f"{datetime.utcnow().isoformat()} slide={slide.index} role={slide.role.value} "
                            f"template={variant.id} theme={variant.theme} "
                            f"scrim={'yes' if variant.scrim.enabled else 'no'} "
                            f"duration={duration:.3f}s "
                            f"warnings={','.join(warnings) if warnings else 'none'}\n"
                        )
                        log_file.write(log_entry)
                await browser.close()
        except Exception as exc:
            logger.exception("Render failed for project %s", project.id)
            raise AppError("render_failed", "Render failed", status.HTTP_500_INTERNAL_SERVER_ERROR, {"project_id": str(project.id)}) from exc
        self.db.commit()

    async def _render_slide(self, page: Page, project: Project, slide: Slide) -> tuple[Path, TemplateVariant, list[str]]:
        variant = self._resolve_variant(project, slide)
        html_content, warnings = self._build_html(slide, variant)
        html_path, png_path = self._target_paths(project.id, slide.index)
        html_path.write_text(html_content, encoding="utf-8")

        await page.set_content(html_content, wait_until="networkidle")
        await page.wait_for_function(
            """
            () => Array.from(document.images)
                .filter(img => img.getAttribute('src'))
                .every(img => img.complete && img.naturalWidth > 0)
            """
        )
        await page.wait_for_timeout(150)
        await page.screenshot(path=str(png_path))
        return png_path, variant, warnings

    def _resolve_variant(self, project: Project, slide: Slide):
        selection = project.template_selection or {}
        role_key = ROLE_KEY_MAP[project.type].get(slide.role)
        if not role_key:
            raise AppError("template_not_found", f"Unsupported role {slide.role}", status.HTTP_400_BAD_REQUEST)

        format_key = FAMILY_MAP[project.type]
        family_name = selection.get("family") if isinstance(selection, dict) else None

        # Per-slide variant override (from payload.template_variant)
        per_slide_variant = slide.payload.get("template_variant") if slide.payload else None

        selected_id = per_slide_variant  # prioritize per-slide choice

        if not selected_id:
            if isinstance(selection, dict):
                format_block = selection.get(format_key)
                if isinstance(format_block, dict):
                    selected_id = format_block.get(role_key)
                else:
                    selected_id = selection.get(role_key)

        if family_name and family_name != "classic":
            if not selected_id:
                try:
                    family_variants = template_registry.registry[family_name][format_key][role_key]
                    selected_id = family_variants[0]["id"]
                except KeyError:
                    raise AppError("template_not_found", f"Family {family_name} has no {format_key}/{role_key}", status.HTTP_404_NOT_FOUND)
            return template_registry.get_variant(family_name, role_key, selected_id, format_key=format_key)
        else:
            if not selected_id:
                family_variants = template_registry.registry[format_key][role_key]
                selected_id = family_variants[0]["id"]
            return template_registry.get_variant(format_key, role_key, selected_id)

    def _build_html(self, slide: Slide, variant: TemplateVariant) -> tuple[str, list[str]]:
        template_path = Path(variant.file)
        if not template_path.exists():
            raise AppError("template_not_found", "Template file missing", status.HTTP_500_INTERNAL_SERVER_ERROR)

        html = template_path.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")
        warnings: list[str] = []

        # ── Resolve appearance overrides ──
        appearance = slide.payload.get("appearance", {})
        effective_theme, theme_warnings = _resolve_effective_theme(variant, appearance)
        warnings.extend(theme_warnings)

        effective_scrim, scrim_warnings = _resolve_effective_scrim(variant, appearance)
        warnings.extend(scrim_warnings)

        # Inline CSS from <link> tags
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

        # ── Apply theme class + scrim vars on .slide element ──
        slide_el = soup.select_one(".slide")
        if slide_el:
            # Remove any legacy dark class
            classes = slide_el.get("class", [])
            if "dark" in classes:
                classes.remove("dark")

            # Add theme class
            theme_class = f"theme-{effective_theme}"
            if theme_class not in classes:
                classes.append(theme_class)
            slide_el["class"] = classes

            # Build inline style with scrim vars
            existing_style = slide_el.get("style", "")
            has_image = bool(slide.payload.get("image") or slide.image_path)

            if effective_scrim.enabled and has_image:
                if effective_scrim.scrim_mode == "box":
                    scrim_val = _scrim_box_value(effective_scrim, effective_theme)
                    existing_style += f" --scrim-bg: transparent; --scrim-box-bg: {scrim_val};"
                    # Inject scrim-box div before .content
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
                if "scrim_disabled" not in warnings:
                    warnings.append("scrim_disabled")

            if existing_style.strip():
                slide_el["style"] = existing_style.strip()

        # Fill data-slot values
        for node in soup.select("[data-slot]"):
            slot_name = node.get("data-slot")
            value = slide.payload.get(slot_name)
            if value is None:
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
                bullets_text = "\n".join(f"• {item}" for item in value)
                node.clear()
                node.append(bullets_text)
            else:
                node.clear()
                node.append(str(value))

        return str(soup), warnings

    def _asset_uri(self, template_path: Path, value: str | None) -> tuple[str, str | None]:
        placeholder = "data:image/png;base64," + base64.b64encode(b" ").decode()
        if not value:
            return placeholder, "image_missing"
        if value.startswith(("http://", "https://")):
            return placeholder, "image_blocked_external"
        potential = Path(value)
        if potential.exists():
            return potential.resolve().as_uri(), None
        relative = (template_path.parent / value).resolve()
        if relative.exists():
            return relative.as_uri(), None
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
