from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass

from app.chunking import TextChunk, chunk_plain_text
from app.html_extract import extract_visible_text
from app.languagetool_client import LanguageToolClient
from app.llm_client import LLMClient
from app.schemas import CheckRequest, CheckResponse, Issue, PlainRange, Stats

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    expires_at: float
    value: object


class TTLCache:
    def __init__(self, ttl_seconds: int) -> None:
        self.ttl_seconds = ttl_seconds
        self._data: dict[str, CacheEntry] = {}

    def get(self, key: str) -> object | None:
        item = self._data.get(key)
        if not item:
            return None
        if item.expires_at < time.time():
            self._data.pop(key, None)
            return None
        return item.value

    def set(self, key: str, value: object) -> None:
        self._data[key] = CacheEntry(expires_at=time.time() + self.ttl_seconds, value=value)


class GrammarService:
    def __init__(self) -> None:
        ttl = int(os.getenv("CACHE_TTL_SECONDS", "300"))
        self.request_cache = TTLCache(ttl)
        self.chunk_cache = TTLCache(ttl)
        self.llm = LLMClient()
        self.languagetool = LanguageToolClient()
        self.semaphore = asyncio.Semaphore(int(os.getenv("CONCURRENCY_LIMIT", "4")))
        self.latencies: list[float] = []

    async def check(self, req: CheckRequest) -> CheckResponse:
        started = time.perf_counter()
        extraction = extract_visible_text(req.html, req.options.skipTags)
        plain = extraction.plain_text

        key_payload = {
            "language": req.language,
            "options": req.options.model_dump(),
            "plainText": plain,
        }
        request_key = hashlib.sha256(json.dumps(key_payload, sort_keys=True).encode()).hexdigest()
        cached = self.request_cache.get(request_key)
        if cached:
            out: CheckResponse = cached  # type: ignore[assignment]
            out.stats.cacheHit = True
            return out

        chunks = chunk_plain_text(plain, req.options.maxChunkChars)
        engine = "llm"

        issues: list[Issue] = []
        if req.options.mode == "fast" and self.languagetool.enabled:
            issues = await self.languagetool.check(plain, req.language)
            engine = "languagetool"
        else:
            try:
                chunk_issues = await asyncio.gather(
                    *(
                        self._check_chunk(c, req.language, req.options.maxSuggestions)
                        for c in chunks
                    )
                )
                issues = [issue for sub in chunk_issues for issue in sub]
                if req.options.mode == "hybrid" and self.languagetool.enabled:
                    issues.extend(await self.languagetool.check(plain, req.language))
                    engine = "hybrid"
            except Exception as exc:
                logger.warning("LLM pipeline failed, fallback path used: %s", exc)
                if self.languagetool.enabled:
                    issues = await self.languagetool.check(plain, req.language)
                    engine = "languagetool"
                else:
                    issues = []
                    engine = "fallback"

        latency_ms = int((time.perf_counter() - started) * 1000)
        self._record_latency(latency_ms)
        response = CheckResponse(
            requestId=req.requestId,
            detectedLanguage=req.language.split("-")[0].lower(),
            plainText=plain,
            issues=sorted(issues, key=lambda i: (i.plainRange.start, i.plainRange.end)),
            stats=Stats(engine=engine, latencyMs=latency_ms, chunks=len(chunks), cacheHit=False),
        )
        self.request_cache.set(request_key, response.model_copy(deep=True))
        return response

    async def _check_chunk(
        self, chunk: TextChunk, language: str, max_suggestions: int
    ) -> list[Issue]:
        key = hashlib.sha256(f"{language}|{chunk.text}".encode()).hexdigest()
        cached = self.chunk_cache.get(key)
        if cached:
            return cached  # type: ignore[return-value]

        async with self.semaphore:
            payload = await self.llm.extract_issues(chunk.text, language)

        issues: list[Issue] = []
        for draft in payload.issues:
            if draft.spanEnd <= draft.spanStart:
                continue
            if self._looks_like_false_positive(chunk.text, draft.spanStart, draft.spanEnd):
                continue
            severity = draft.severity
            if draft.type == "style" and severity != "error":
                severity = "info"
            issues.append(
                Issue(
                    type=draft.type,
                    severity=severity,
                    message=draft.message,
                    shortMessage=draft.shortMessage,
                    plainRange=PlainRange(
                        start=chunk.start + draft.spanStart, end=chunk.start + draft.spanEnd
                    ),
                    context=draft.context,
                    suggestions=draft.suggestions[:max_suggestions],
                    replacement=draft.replacement,
                    confidence=draft.confidence,
                    ruleId=draft.ruleId,
                )
            )
        self.chunk_cache.set(key, issues)
        return issues

    @staticmethod
    def _looks_like_false_positive(chunk_text: str, start: int, end: int) -> bool:
        snippet = chunk_text[start:end]
        if not snippet.strip():
            return True
        if snippet.startswith(("http://", "https://", "/", "C:\\")):
            return True
        if any(char.isdigit() for char in snippet) and "/" in snippet:
            return True
        return False

    def _record_latency(self, latency_ms: int) -> None:
        self.latencies.append(latency_ms)
        if len(self.latencies) > 200:
            self.latencies.pop(0)
        sorted_values = sorted(self.latencies)
        p50 = sorted_values[len(sorted_values) // 2]
        p95 = sorted_values[min(len(sorted_values) - 1, int(len(sorted_values) * 0.95))]
        logger.info("latency stats p50=%sms p95=%sms", p50, p95)
