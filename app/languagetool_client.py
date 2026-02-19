from __future__ import annotations

import os

import httpx

from app.schemas import Issue, PlainRange


class LanguageToolClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("LANGUAGETOOL_URL", "")
        self.timeout = float(os.getenv("LANGUAGETOOL_TIMEOUT_SECONDS", "3"))

    @property
    def enabled(self) -> bool:
        return bool(self.base_url)

    async def check(self, text: str, language: str) -> list[Issue]:
        if not self.enabled:
            return []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            res = await client.post(
                self.base_url.rstrip("/") + "/v2/check",
                data={"text": text, "language": language},
            )
            res.raise_for_status()
            payload = res.json()
        issues: list[Issue] = []
        for m in payload.get("matches", []):
            offset = int(m.get("offset", 0))
            length = int(m.get("length", 0))
            replacements = [r.get("value", "") for r in m.get("replacements", [])][:5]
            non_empty_replacements = [s for s in replacements if s]
            issues.append(
                Issue(
                    type="grammar",
                    severity="warning",
                    message=m.get("message", "LanguageTool suggestion"),
                    shortMessage=m.get("shortMessage") or "LanguageTool",
                    plainRange=PlainRange(start=offset, end=offset + length),
                    context=m.get("context", {}).get(
                        "text", text[max(0, offset - 20) : offset + length + 20]
                    ),
                    suggestions=non_empty_replacements,
                    replacement=non_empty_replacements[0] if non_empty_replacements else None,
                    confidence=0.6,
                    ruleId=m.get("rule", {}).get("id"),
                )
            )
        return issues
