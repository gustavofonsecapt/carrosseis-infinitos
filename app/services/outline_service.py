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
    detect_overflow_slots,
    enforce_slot_limits,
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

    # ── Prompt builders ─────────────────────────────────────────────

    def _build_carousel_prompt(self, project: Project, ctx: OutlineRequestContext) -> tuple[str, str]:
        cover_slots = self._get_slot_schema(project, "carousel/cover")
        body_slots = self._get_slot_schema(project, "carousel/body")
        cta_slots = self._get_slot_schema(project, "carousel/cta")

        cover_hints = build_composition_hints(cover_slots)
        body_hints = build_composition_hints(body_slots)

        system_prompt = (
            "Você é um roteirista especializado em carrosséis do Instagram. "
            "Produza textos concisos, em português do Brasil, com uma ideia por slide.\n\n"
            "REGRAS OBRIGATÓRIAS:\n"
            "1. NUNCA exceda os limites de caracteres indicados para cada slot.\n"
            "2. Conte os caracteres ANTES de finalizar. Se estiver perto do limite, reescreva mais curto.\n"
            "3. Prefira frases de impacto a parágrafos longos.\n"
            "4. Retorne APENAS JSON válido, sem markdown, sem texto adicional."
        )

        user_prompt = f"""
Gere um roteiro completo para um carrossel de 8 páginas (n=1..8) sobre o tema "{ctx.topic}".
Papel de cada slide:
1 = cover, 2-7 = body, 8 = cta.

⚠️ LIMITES ESTRITOS — respeite CADA limite abaixo. Textos que excederem serão cortados automaticamente.

COVER (slots e limites):
{summarize_slot_constraints(cover_slots)}
{f"Dicas de composição: {cover_hints}" if cover_hints else ""}

BODY (slots e limites):
{summarize_slot_constraints(body_slots)}
{f"Dicas de composição: {body_hints}" if body_hints else ""}

CTA (slots e limites):
{summarize_slot_constraints(cta_slots)}

Tom desejado: {ctx.tone or "informativo e claro"}.
Chamada final deve direcionar para: {ctx.cta_action or "DM"}.

Saída obrigatória: JSON válido seguindo exatamente o contrato abaixo:
{{
  "format": "carousel",
  "slides": [
    {{"n":1,"role":"cover","headline":"...","subhead":"...","kicker":"...","body":null,"bullets":[],"cta":null,"image_brief":"..."}},
    ...,
    {{"n":8,"role":"cta","headline":"...","cta":"...","subcta":"...","image_brief":"..."}}
  ]
}}
"""
        return system_prompt, user_prompt

    def _build_stories_prompt(self, project: Project, ctx: OutlineRequestContext) -> tuple[str, str]:
        frame_slots = self._get_slot_schema(project, "stories/frame")
        cta_slots = self._get_slot_schema(project, "stories/cta")

        frame_hints = build_composition_hints(frame_slots)

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

⚠️ LIMITES ESTRITOS:

FRAME (slots e limites):
{summarize_slot_constraints(frame_slots)}
{f"Dicas: {frame_hints}" if frame_hints else ""}

CTA FRAME (slots e limites):
{summarize_slot_constraints(cta_slots)}

Tom: {ctx.tone or "envolvente e direto"}.
CTA final deve instruir: {ctx.cta_action or "DM"} com palavra-chave {ctx.cta_trigger_word or "CASA"}.

Saída obrigatória (JSON puro):
{{
  "format": "stories_10x",
  "frames": [
    {{"n":1,"role":"frame","kicker":"...","headline":"...","support":"...","image_brief":"...","progress":"1/10"}},
    ...,
    {{"n":10,"role":"frame_cta","headline":"...","cta":"...","trigger_word":"CASA","support":"...","image_brief":"...","progress":"10/10"}}
  ],
  "cta": {{"action":"DM","trigger_word":"CASA"}}
}}
"""
        return system_prompt, user_prompt

    # ── Response parsing with 2-pass compress ───────────────────────

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

            # Pass 1: detect overflows that need auto-rewrite
            overflows = detect_overflow_slots(entry, slot_schema)
            if overflows and self.openai is not None:
                for slot_key, info in overflows.items():
                    # Handle list item keys like "bullets[2]"
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
            for warning in warnings:
                logger.info("Slide %s warning: %s", role.value, warning)

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

    # ── Fallback (stub) ─────────────────────────────────────────────

    def _fallback_payload(self, project: Project, ctx: OutlineRequestContext) -> dict[str, Any]:
        topic = ctx.topic or "Projeto"
        if project.type == ProjectType.CAROUSEL:
            slides = []
            slides.append({
                "n": 1,
                "role": "cover",
                "headline": f"{topic}: visão geral",
                "subhead": "Resumo rápido",
                "kicker": "Introdução",
                "body": None,
                "bullets": [],
                "cta": None,
                "subcta": None,
                "image_brief": "Capa tipográfica",
            })
            for n in range(2, 8):
                slides.append({
                    "n": n,
                    "role": "body",
                    "headline": f"Ponto {n-1}",
                    "support": f"Contexto do ponto {n-1}",
                    "body": f"Detalhes do ponto {n-1} sobre {topic}",
                    "bullets": [f"Insight {i}" for i in range(1, 4)],
                    "cta": None,
                    "subcta": None,
                    "image_brief": "Imagem ilustrativa",
                })
            slides.append({
                "n": 8,
                "role": "cta",
                "headline": "Continue a conversa",
                "cta": ctx.cta_action or "DM",
                "subcta": "Fale com a equipe",
                "image_brief": "CTA minimalista",
            })
            return {"format": "carousel", "slides": slides}

        frames = []
        for n in range(1, 10):
            frames.append({
                "n": n,
                "role": "frame",
                "kicker": f"{topic} #{n}",
                "headline": f"Take {n}",
                "support": f"Detalhe {n} sobre {topic}",
                "image_brief": "Visual minimalista",
                "progress": f"{n}/10",
            })
        frames.append({
            "n": 10,
            "role": "frame_cta",
            "headline": "Chame no direct",
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
