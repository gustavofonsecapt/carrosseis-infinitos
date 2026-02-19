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
from app.utils.slots import enforce_slot_limits, summarize_slot_constraints

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
            prompt = self._build_carousel_prompt(ctx)
        else:
            prompt = self._build_stories_prompt(ctx)

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

    def _build_carousel_prompt(self, ctx: OutlineRequestContext) -> tuple[str, str]:
        cover_slots = template_registry.get_slots("carousel/cover")
        body_slots = template_registry.get_slots("carousel/body")
        cta_slots = template_registry.get_slots("carousel/cta")

        system_prompt = (
            "Você é um roteirista especializado em carrosséis do Instagram. "
            "Produza textos concisos, em português do Brasil, com uma ideia por slide."
        )

        user_prompt = f"""
Gere um roteiro completo para um carrossel de 8 páginas (n=1..8) sobre o tema "{ctx.topic}".
Papel de cada slide:
1 = cover, 2-7 = body, 8 = cta.
Respeite os limites dos templates:
COVER:
{summarize_slot_constraints(cover_slots)}
BODY:
{summarize_slot_constraints(body_slots)}
CTA:
{summarize_slot_constraints(cta_slots)}

Tom desejado: {ctx.tone or "informativo e claro"}.
Chamada final deve direcionar para: {ctx.cta_action or "DM"}.

Saída obrigatória: JSON válido seguindo exatamente o contrato abaixo (sem Markdown, sem texto adicional):
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

    def _build_stories_prompt(self, ctx: OutlineRequestContext) -> tuple[str, str]:
        frame_slots = template_registry.get_slots("stories/frame")
        cta_slots = template_registry.get_slots("stories/cta")

        system_prompt = (
            "Você escreve roteiros para sequências de stories (1080x1920). "
            "Cada quadro deve ser curto, com progressão narrativa." 
        )

        user_prompt = f"""
Gere um roteiro para 10 stories (n=1..10) sobre "{ctx.topic}".
Quadros 1-9 = role "frame". Quadro 10 = role "frame_cta" com CTA final.
Respeite os limites dos templates:
FRAME:
{summarize_slot_constraints(frame_slots)}
CTA FRAME:
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
            slot_schema = self._slot_schema_for_role(role)
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
                )
            )
        return slides

    def _slot_schema_for_role(self, role: SlideRole) -> dict[str, Any]:
        if role == SlideRole.COVER:
            return template_registry.get_slots("carousel/cover")
        if role == SlideRole.BODY:
            return template_registry.get_slots("carousel/body")
        if role == SlideRole.CTA:
            return template_registry.get_slots("carousel/cta")
        if role == SlideRole.FRAME:
            return template_registry.get_slots("stories/frame")
        if role == SlideRole.FRAME_CTA:
            return template_registry.get_slots("stories/cta")
        raise AppError("invalid_payload", "Unsupported slide role", status.HTTP_400_BAD_REQUEST)

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
