from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import httpx
from pydantic import ValidationError

from app.schemas import LLMIssuesPayload


class LLMClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        self.api_key = os.getenv("LLM_API_KEY", "")
        self.model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "12"))
        self.prompt_version = os.getenv("PROMPT_VERSION", "v1")
        self.max_retries = int(os.getenv("LLM_MAX_RETRIES", "2"))
        self._client = httpx.AsyncClient(timeout=self.timeout)

    def _load_prompt(self, stage: str) -> str:
        path = Path("prompts") / f"{self.prompt_version}_{stage}.txt"
        return path.read_text(encoding="utf-8")

    async def _chat_completion(self, system: str, user: str) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        response = await self._client.post(
            f"{self.base_url}/chat/completions", headers=headers, json=payload
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    async def extract_issues(self, chunk_text: str, language: str) -> LLMIssuesPayload:
        detect_prompt = self._load_prompt("detect")
        verify_prompt = self._load_prompt("verify")
        detection = await self._call_with_validation(detect_prompt, chunk_text, language)
        verification_input = json.dumps(detection.model_dump(), ensure_ascii=False)
        return await self._call_with_validation(
            verify_prompt, chunk_text, language, verification_input
        )

    async def _call_with_validation(
        self,
        system_prompt: str,
        chunk_text: str,
        language: str,
        prior_json: str | None = None,
    ) -> LLMIssuesPayload:
        user_payload: dict[str, Any] = {
            "language": language,
            "chunkText": chunk_text,
        }
        if prior_json:
            user_payload["priorOutput"] = prior_json

        compact_prompt = json.dumps(user_payload, ensure_ascii=False)
        errors: list[str] = []
        for attempt in range(self.max_retries + 1):
            try:
                system_prompt_attempt = (
                    system_prompt if attempt == 0 else system_prompt + "\nReturn JSON only."
                )
                content = await self._chat_completion(system_prompt_attempt, compact_prompt)
                parsed = json.loads(content)
                return LLMIssuesPayload.model_validate(parsed)
            except (httpx.HTTPError, json.JSONDecodeError, ValidationError) as exc:
                errors.append(str(exc))
                if attempt == self.max_retries:
                    break
                await asyncio.sleep(0.2 * (attempt + 1))
        raise RuntimeError(
            f"LLM extraction failed after retries: {errors[-1] if errors else 'unknown error'}"
        )

    async def close(self) -> None:
        await self._client.aclose()
