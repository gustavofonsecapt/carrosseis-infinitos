from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any
from uuid import uuid4

from fastapi import status

from app.core.config import settings
from app.core.errors import AppError

from app.models import Project, ProjectType, Slide, SlideRole
from app.services.openai_service import OpenAIService
from app.services.template_service import template_registry
from app.utils.slots import (
    build_composition_hints,
    build_role_schema,
    derive_slot_capabilities,
    detect_overflow_slots,
    enforce_slot_limits,
    strip_forbidden_slots,
    summarize_slot_constraints,
)

logger = logging.getLogger(__name__)


@dataclass
class OutlineRequestContext:
    topic: str
    tone: str | None = None
    cta_action: str | None = None
    cta_trigger_word: str | None = None


class OutlineService:
    def __init__(self, openai_service: OpenAIService | None = None):
        if openai_service is not None:
            self.openai = openai_service
        else:
            try:
                self.openai = OpenAIService()
            except AppError as exc:
                if settings.environment in {"local", "test"}:
                    logger.warning("OpenAI unavailable at startup (%s). Using stub mode.", exc.code)
                    self.openai = None
                else:
                    raise

    def generate(self, project: Project, ctx: OutlineRequestContext) -> list[Slide]:
        if project.type == ProjectType.CAROUSEL:
            prompt = self._build_carousel_prompt(project, ctx)
        else:
            prompt = self._build_stories_prompt(project, ctx)

        if self.openai is None:
            response = self._fallback_payload(project, ctx)
        else:
            try:
                response = self.openai.complete_json(*prompt)
            except AppError as exc:
                if settings.environment in {"local", "test"}:
                    logger.warning("OpenAI unavailable (%s). Falling back to stub outline.", exc.code)
                    response = self._fallback_payload(project, ctx)
                else:
                    raise
        return self._parse_response(project, response)

    # ── Slot schema helpers (family-aware) ──────────────────────────

    def _get_slot_schema(self, project: Project, role_path: str) -> dict[str, Any]:
        """Load slot schema, preferring the project's selected family."""
        selection = project.template_selection or {}
        family = selection.get("family") if isinstance(selection, dict) else None

        if family and family != "classic":
            try:
                return template_registry.get_family_slots(family)
            except Exception:
                logger.warning("Failed to load family slots for '%s', falling back to layout slots", family)

        return template_registry.get_slots(role_path)

    def _get_slot_schema_for_role(self, project: Project, format_key: str, role: str, fallback_path: str) -> dict[str, Any]:
        """Load slot schema filtered by role, preferring family slots."""
        selection = project.template_selection or {}
        family = selection.get("family") if isinstance(selection, dict) else None

        if family and family != "classic":
            try:
                return template_registry.get_family_slots_for_role(family, format_key, role)
            except Exception:
                logger.warning("Failed to load family role slots for '%s/%s', falling back", family, role)

        return template_registry.get_slots(fallback_path)

    # ── Prompt builders ─────────────────────────────────────────────

    def _build_carousel_prompt(self, project: Project, ctx: OutlineRequestContext) -> tuple[str, str]:
        cover_slots = self._get_slot_schema_for_role(project, "carousel", "cover", "carousel/cover")
        body_slots = self._get_slot_schema_for_role(project, "carousel", "body", "carousel/body")
        cta_slots = self._get_slot_schema_for_role(project, "carousel", "cta", "carousel/cta")

        cover_caps = derive_slot_capabilities(cover_slots)
        body_caps = derive_slot_capabilities(body_slots)
        cta_caps = derive_slot_capabilities(cta_slots)

        cover_schema = build_role_schema("cover", cover_caps, cover_slots)
        body_schema = build_role_schema("body", body_caps, body_slots)
        cta_schema = build_role_schema("cta", cta_caps, cta_slots)

        body_hints = build_composition_hints(body_slots)

        # Build dynamic JSON example based on actual slot keys
        tk = cover_caps["title_key"]
        sk = cover_caps["subtitle_key"]
        btk = body_caps["title_key"]

        # CTA key detection
        cta_title_key = "cta_title" if cta_caps["supports_cta_title"] else cta_caps["title_key"]
        cta_button_key = "cta_button" if cta_caps["supports_cta_button"] else "cta"

        cover_example = f'{{"n":1,"role":"cover","{tk}":"...","{ sk}":"..."}}'
        body_example = f'{{"n":2,"role":"body","{btk}":"..."'
        if body_caps["bullets_strategy"]:
            body_example += ',"bullets":["...","...","..."]'
        elif body_caps["body_strategy"]:
            body_example += ',"body":"..."'
        body_example += "}"

        cta_example = f'{{"n":8,"role":"cta","{cta_title_key}":"...","{cta_button_key}":"..."}}'

        system_prompt = (
            "Você é um roteirista especializado em carrosséis do Instagram. "
            "Produza textos concisos, em português do Brasil, com uma ideia por slide.\n\n"
            "REGRAS OBRIGATÓRIAS:\n"
            "1. NUNCA exceda os limites de caracteres indicados para cada slot.\n"
            "2. Conte os caracteres ANTES de finalizar. Se estiver perto do limite, reescreva mais curto.\n"
            "3. Prefira frases de impacto a parágrafos longos.\n"
            "4. Retorne APENAS JSON válido, sem markdown, sem texto adicional.\n"
            "5. Cada role tem campos PROIBIDOS — NÃO os inclua no JSON."
        )

        total = project.slides_count or 8
        last = total
        body_end = total - 1

        user_prompt = f"""
Gere um roteiro completo para um carrossel de {total} páginas (n=1..{last}) sobre o tema "{ctx.topic}".
Papel de cada slide: 1 = cover, 2-{body_end} = body, {last} = cta.

⚠️ REGRAS POR ROLE — respeite os campos permitidos e NUNCA inclua campos proibidos:

{cover_schema}

{body_schema}
{f"Dicas de composição: {body_hints}" if body_hints else ""}

{cta_schema}

Tom desejado: {ctx.tone or "informativo e claro"}.
Chamada final deve direcionar para: {ctx.cta_action or "DM"}.

Saída obrigatória: JSON válido seguindo exatamente este formato:
{{
  "format": "carousel",
  "slides": [
    {cover_example},
    {body_example},
    ...,
    {cta_example}
  ]
}}
"""
        return system_prompt, user_prompt

    def _build_stories_prompt(self, project: Project, ctx: OutlineRequestContext) -> tuple[str, str]:
        frame_slots = self._get_slot_schema_for_role(project, "stories", "frame", "stories/frame")
        cta_slots = self._get_slot_schema_for_role(project, "stories", "frame", "stories/cta")

        frame_caps = derive_slot_capabilities(frame_slots)
        cta_caps = derive_slot_capabilities(cta_slots)

        frame_schema = build_role_schema("frame", frame_caps, frame_slots)
        cta_frame_schema = build_role_schema("frame_cta", cta_caps, cta_slots)

        frame_hints = build_composition_hints(frame_slots)

        tk = frame_caps["title_key"]

        system_prompt = (
            "Você escreve roteiros para sequências de stories (1080x1920). "
            "Cada quadro deve ser curto, com progressão narrativa.\n\n"
            "REGRAS OBRIGATÓRIAS:\n"
            "1. NUNCA exceda os limites de caracteres indicados para cada slot.\n"
            "2. Stories devem ter headlines MUITO curtos e support opcional curto.\n"
            "3. Retorne APENAS JSON válido, sem markdown."
        )

        user_prompt = f"""
Gere um roteiro para 10 stories (n=1..10) sobre "{ctx.topic}".
Quadros 1-9 = role "frame". Quadro 10 = role "frame_cta" com CTA final.

⚠️ REGRAS POR ROLE:

{frame_schema}
{f"Dicas: {frame_hints}" if frame_hints else ""}

{cta_frame_schema}

Tom: {ctx.tone or "envolvente e direto"}.
CTA final deve instruir: {ctx.cta_action or "DM"} com palavra-chave {ctx.cta_trigger_word or "CASA"}.

Saída obrigatória (JSON puro):
{{
  "format": "stories_10x",
  "frames": [
    {{"n":1,"role":"frame","{tk}":"...","support":"...","progress":"1/10"}},
    ...,
    {{"n":10,"role":"frame_cta","{tk}":"...","cta":"...","trigger_word":"{ctx.cta_trigger_word or 'CASA'}","progress":"10/10"}}
  ],
  "cta": {{"action":"{ctx.cta_action or 'DM'}","trigger_word":"{ctx.cta_trigger_word or 'CASA'}"}}
}}
"""
        return system_prompt, user_prompt

    # ── Response parsing with role sanitization + 2-pass compress ───

    def _parse_response(self, project: Project, payload: dict[str, Any]) -> list[Slide]:
        try:
            if project.type == ProjectType.CAROUSEL:
                slides_payload = payload["slides"]
            else:
                slides_payload = payload["frames"]
        except KeyError as exc:
            raise AppError("invalid_payload", "JSON missing slides", status.HTTP_502_BAD_GATEWAY) from exc

        slides: list[Slide] = []
        for entry in slides_payload:
            role = SlideRole(entry["role"])
            slot_schema = self._slot_schema_for_role(project, role)

            # Pass 0: strip forbidden slots for this role
            stripped = strip_forbidden_slots(entry, role.value)
            if stripped:
                logger.info("Stripped forbidden slots from %s: %s", role.value, stripped)

            # Pass 1: detect overflows that need auto-rewrite
            overflows = detect_overflow_slots(entry, slot_schema)
            if overflows and self.openai is not None:
                for slot_key, info in overflows.items():
                    if "[" in slot_key:
                        base_key, idx_str = slot_key.rstrip("]").split("[")
                        idx = int(idx_str)
                        original = entry[base_key][idx]
                        compressed = self.openai.compress_slot(
                            slot_key, original, info["max_chars"]
                        )
                        entry[base_key][idx] = compressed
                        logger.info(
                            "Auto-rewrite %s: %d -> %d chars (overflow was %.0f%%)",
                            slot_key, len(original), len(compressed), info["overflow_pct"] * 100,
                        )
                    else:
                        original = entry[slot_key]
                        compressed = self.openai.compress_slot(
                            slot_key, original, info["max_chars"]
                        )
                        entry[slot_key] = compressed
                        logger.info(
                            "Auto-rewrite %s: %d -> %d chars (overflow was %.0f%%)",
                            slot_key, len(original), len(compressed), info["overflow_pct"] * 100,
                        )

            # Pass 2: hard enforce (truncate anything still over)
            sanitized_payload, warnings = enforce_slot_limits(entry, slot_schema)
            if stripped:
                warnings.extend([f"stripped_{k}" for k in stripped])
            for warning in warnings:
                logger.info("Slide %s warning: %s", role.value, warning)

            # Resolve and store template_id for this slide
            template_id = self._resolve_template_id(project, role)
            if template_id:
                sanitized_payload["template_id"] = template_id
                logger.info("Slide n=%s role=%s -> template_id=%s", entry.get("n"), role.value, template_id)

            slides.append(
                Slide(
                    id=str(uuid4()),
                    project_id=str(project.id),
                    index=entry.get("n", len(slides) + 1),
                    role=role,
                    payload=sanitized_payload,
                    warnings=warnings if warnings else None,
                )
            )
        return slides

    def _resolve_template_id(self, project: Project, role: SlideRole) -> str | None:
        """Resolve the default template_id for a slide role based on project's template_selection."""
        from app.services.template_service import template_registry

        selection = project.template_selection or {}
        family = selection.get("family") if isinstance(selection, dict) else None

        format_map = {
            ProjectType.CAROUSEL: "carousel",
            ProjectType.STORIES_10X: "stories",
        }
        role_key_map = {
            SlideRole.COVER: "cover",
            SlideRole.BODY: "body",
            SlideRole.CTA: "cta",
            SlideRole.FRAME: "frame",
            SlideRole.FRAME_CTA: "cta",
        }
        format_key = format_map.get(project.type)
        role_key = role_key_map.get(role)
        if not format_key or not role_key:
            return None

        # Check per-role override in selection (e.g. template_selection.carousel.cover)
        if isinstance(selection, dict):
            fmt_block = selection.get(format_key)
            if isinstance(fmt_block, dict) and fmt_block.get(role_key):
                return fmt_block[role_key]

        if family and family != "classic":
            try:
                variants = template_registry.registry[family][format_key][role_key]
                if variants:
                    return variants[0]["id"]
            except KeyError:
                available = list(template_registry.registry.get(family, {}).get(format_key, {}).keys())
                raise AppError(
                    "template_not_found",
                    f"Family '{family}' has no {format_key}/{role_key} variants. Available roles: {available}",
                    status.HTTP_400_BAD_REQUEST,
                    {"family": family, "format": format_key, "role": role_key, "available_roles": available},
                )
        else:
            # Classic/legacy
            try:
                variants = template_registry.registry[format_key][role_key]
                if variants:
                    return variants[0]["id"]
            except KeyError:
                return None

        return None

    def _slot_schema_for_role(self, project: Project, role: SlideRole) -> dict[str, Any]:
        role_paths = {
            SlideRole.COVER: "carousel/cover",
            SlideRole.BODY: "carousel/body",
            SlideRole.CTA: "carousel/cta",
            SlideRole.FRAME: "stories/frame",
            SlideRole.FRAME_CTA: "stories/cta",
        }
        path = role_paths.get(role)
        if not path:
            raise AppError("invalid_payload", "Unsupported slide role", status.HTTP_400_BAD_REQUEST)
        return self._get_slot_schema(project, path)

    # ── Fallback (stub) — role-aware ────────────────────────────────

    def _fallback_payload(self, project: Project, ctx: OutlineRequestContext) -> dict[str, Any]:
        topic = ctx.topic or "Projeto"

        if project.type == ProjectType.CAROUSEL:
            # Detect capabilities for each role
            cover_slots = self._get_slot_schema_for_role(project, "carousel", "cover", "carousel/cover")
            body_slots = self._get_slot_schema_for_role(project, "carousel", "body", "carousel/body")
            cta_slots = self._get_slot_schema_for_role(project, "carousel", "cta", "carousel/cta")

            cover_caps = derive_slot_capabilities(cover_slots)
            body_caps = derive_slot_capabilities(body_slots)
            cta_caps = derive_slot_capabilities(cta_slots)

            tk = cover_caps["title_key"]
            sk = cover_caps["subtitle_key"]
            btk = body_caps["title_key"]

            slides: list[dict[str, Any]] = []

            total = project.slides_count or 8

            # Cover: only title + subtitle + brand + number
            cover: dict[str, Any] = {"n": 1, "role": "cover"}
            cover[tk] = f"{topic}: visão geral"
            if cover_caps["supports_subtitle"]:
                cover[sk] = "Resumo rápido"
            if cover_caps["supports_kicker"]:
                cover["kicker"] = "Introdução"
            if cover_caps["supports_brand"]:
                cover["brand"] = ""
            if cover_caps["supports_number"]:
                cover["number"] = f"01/{total:02d}"
            cover["image_brief"] = "Capa tipográfica"
            slides.append(cover)

            # Body slides: adapt bullets vs body
            total = project.slides_count or 8
            last = total
            for n in range(2, last):
                body: dict[str, Any] = {"n": n, "role": "body"}
                body[btk] = f"Ponto {n - 1}"
                if body_caps["bullets_strategy"]:
                    body["bullets"] = [f"Insight {i} sobre {topic}" for i in range(1, 4)]
                elif body_caps["body_strategy"] or body_caps["supports_body"]:
                    body["body"] = f"Detalhes do ponto {n - 1} sobre {topic}."
                if body_caps["supports_number"]:
                    body["number"] = f"{n:02d}/{total:02d}"
                body["image_brief"] = "Imagem ilustrativa"
                slides.append(body)

            # CTA: only cta fields + brand
            cta: dict[str, Any] = {"n": last, "role": "cta"}
            if cta_caps["supports_cta_title"]:
                cta["cta_title"] = "Continue a conversa"
            elif cta_caps["supports_title"]:
                cta[cta_caps["title_key"]] = "Continue a conversa"
            if cta_caps["supports_cta_button"]:
                cta["cta_button"] = ctx.cta_action or "DM"
            elif "cta" in cta_slots.get("slots", {}):
                cta["cta"] = ctx.cta_action or "DM"
            if cta_caps["supports_cta_body"]:
                cta["cta_body"] = "Fale com a equipe"
            if cta_caps["supports_brand"]:
                cta["brand"] = ""
            if cta_caps["supports_number"]:
                cta["number"] = f"{total:02d}/{total:02d}"
            cta["image_brief"] = "CTA minimalista"
            slides.append(cta)

            return {"format": "carousel", "slides": slides}

        # Stories fallback
        frames: list[dict[str, Any]] = []
        frame_slots = self._get_slot_schema_for_role(project, "stories", "frame", "stories/frame")
        frame_caps = derive_slot_capabilities(frame_slots)
        tk = frame_caps["title_key"]

        for n in range(1, 10):
            frames.append({
                "n": n,
                "role": "frame",
                tk: f"Take {n}" if n > 1 else f"{topic}",
                "support": f"Detalhe {n}" if n > 1 else "Hook inicial",
                "image_brief": "Visual minimalista",
                "progress": f"{n}/10",
            })
        frames.append({
            "n": 10,
            "role": "frame_cta",
            tk: "Chame no direct",
            "cta": ctx.cta_action or "DM",
            "trigger_word": ctx.cta_trigger_word or "CASA",
            "support": "Use a palavra-chave",
            "image_brief": "CTA final",
            "progress": "10/10",
        })
        return {
            "format": "stories_10x",
            "frames": frames,
            "cta": {"action": ctx.cta_action or "DM", "trigger_word": ctx.cta_trigger_word or "CASA"},
        }
