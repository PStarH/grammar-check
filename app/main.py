from __future__ import annotations

from fastapi import FastAPI

from app.grammar_service import GrammarService
from app.schemas import CheckRequest, CheckResponse

app = FastAPI(title="Grammar Checker", version="0.1.0")
service = GrammarService()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/grammar/check", response_model=CheckResponse)
async def grammar_check(req: CheckRequest) -> CheckResponse:
    return await service.check(req)
