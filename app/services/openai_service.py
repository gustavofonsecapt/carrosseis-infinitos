from __future__ import annotations

import json
from typing import Any

from fastapi import status

from app.core.errors import AppError
from openai import OpenAI

from app.core.config import settings

DEFAULT_MODEL = "gpt-4.1-mini"


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
