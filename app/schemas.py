from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

IssueType = Literal["grammar", "spelling", "style"]
SeverityType = Literal["error", "warning", "info"]
ModeType = Literal["best_quality", "hybrid", "fast"]
EngineType = Literal["llm", "hybrid", "languagetool", "fallback"]


class PlainRange(BaseModel):
    start: int = Field(ge=0)
    end: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_range(self) -> "PlainRange":
        if self.end < self.start:
            raise ValueError("plainRange.end must be >= start")
        return self


class Issue(BaseModel):
    type: IssueType
    severity: SeverityType
    message: str
    shortMessage: str
    plainRange: PlainRange
    context: str
    suggestions: list[str] = Field(default_factory=list)
    replacement: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    ruleId: str | None = None


class CheckOptions(BaseModel):
    skipTags: list[str] = Field(default_factory=lambda: ["script", "style", "code", "pre"])
    mode: ModeType = "best_quality"
    returnCorrectedHtml: bool = False
    maxSuggestions: int = Field(default=5, ge=1, le=20)
    maxChunkChars: int = Field(default=1200, ge=300, le=4000)


class CheckRequest(BaseModel):
    requestId: str | None = None
    contentType: Literal["text/html"] = "text/html"
    language: str = "en-US"
    html: str
    options: CheckOptions = Field(default_factory=CheckOptions)


class Stats(BaseModel):
    engine: EngineType
    latencyMs: int = Field(ge=0)
    chunks: int = Field(ge=0)
    cacheHit: bool


class CheckResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requestId: str | None = None
    detectedLanguage: str
    plainText: str
    issues: list[Issue]
    stats: Stats


class LLMIssueDraft(BaseModel):
    type: IssueType
    severity: SeverityType
    message: str
    shortMessage: str
    spanStart: int = Field(ge=0)
    spanEnd: int = Field(ge=0)
    context: str
    suggestions: list[str] = Field(default_factory=list)
    replacement: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    ruleId: str | None = None


class LLMIssuesPayload(BaseModel):
    issues: list[LLMIssueDraft] = Field(default_factory=list)
