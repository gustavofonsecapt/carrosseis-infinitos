from __future__ import annotations

import base64
import logging
from datetime import datetime
from pathlib import Path
from time import perf_counter
from uuid import UUID

from bs4 import BeautifulSoup
from fastapi import status

from app.core.errors import AppError
from playwright.async_api import Page, async_playwright
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Project, ProjectType, Slide, SlideRole
from app.services.template_service import TemplateVariant, template_registry

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
                            f"template={variant.id} duration={duration:.3f}s "
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
        html_content, warnings = self._build_html(slide, variant.file)
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

        family = FAMILY_MAP[project.type]
        selected_id = None
        if isinstance(selection, dict):
            family_block = selection.get(family)
            if isinstance(family_block, dict):
                selected_id = family_block.get(role_key)
            else:
                selected_id = selection.get(role_key)
        if not selected_id:
            family_variants = template_registry.registry[family][role_key]
            selected_id = family_variants[0]["id"]
        return template_registry.get_variant(family, role_key, selected_id)

    def _build_html(self, slide: Slide, template_file: str) -> tuple[str, list[str]]:
        template_path = Path(template_file)
        if not template_path.exists():
            raise AppError("template_not_found", "Template file missing", status.HTTP_500_INTERNAL_SERVER_ERROR)

        html = template_path.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")
        warnings: list[str] = []

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
