from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import status

from app.core.errors import AppError
from openai import OpenAI

from app.core.config import settings

DEFAULT_MODEL = "gpt-4.1-mini"

logger = logging.getLogger(__name__)


class OpenAIService:
    def __init__(self, model: str = DEFAULT_MODEL):
        if not settings.openai_api_key:
            raise AppError(
                "service_unavailable",
                "OPENAI_API_KEY not configured",
                status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = model

    def complete_json(self, system_prompt: str, user_prompt: str, *, max_output_tokens: int = 1600) -> dict[str, Any]:
        response = self.client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_output_tokens=max_output_tokens,
        )
        text = response.output_text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise AppError(
                "invalid_payload",
                "OpenAI returned invalid JSON",
                status.HTTP_502_BAD_GATEWAY,
            ) from exc

    def compress_slot(self, slot_name: str, original_text: str, max_chars: int, *, language: str = "pt-BR") -> str:
        """Rewrite a single slot value to fit within max_chars while preserving meaning and style."""
        system_prompt = (
            f"You are a copywriting editor. Rewrite the text to fit within {max_chars} characters. "
            f"Preserve the original meaning, tone, and style. Output ONLY the rewritten text, nothing else. "
            f"Language: {language}."
        )
        user_prompt = (
            f"Slot: {slot_name}\n"
            f"Max chars: {max_chars}\n"
            f"Original ({len(original_text)} chars):\n{original_text}"
        )
        try:
            response = self.client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.5,
                max_output_tokens=200,
            )
            result = response.output_text.strip().strip('"').strip("'")
            if len(result) <= max_chars:
                logger.info("Compress OK for '%s': %d -> %d chars", slot_name, len(original_text), len(result))
                return result
            # Still too long — will be truncated downstream
            logger.warning("Compress for '%s' still over limit: %d > %d", slot_name, len(result), max_chars)
            return result[:max_chars].rstrip()
        except Exception:
            logger.exception("Compress failed for slot '%s', will truncate", slot_name)
            return original_text[:max_chars].rstrip()
