"""Pydantic models for request and response schemas."""

from typing import Literal

from pydantic import BaseModel, Field


class CheckOptions(BaseModel):
    """Options for grammar checking."""

    skipTags: list[str] = Field(
        default=["script", "style", "code", "pre"],
        description="HTML tags to skip during text extraction",
    )
    mode: Literal["best_quality", "hybrid", "fast"] = Field(
        default="best_quality",
        description=(
            "Checking mode: best_quality (LLM), "
            "hybrid (LLM+LanguageTool), fast (LanguageTool only)"
        ),
    )
    returnCorrectedHtml: bool = Field(default=False, description="Whether to return corrected HTML")
    maxSuggestions: int = Field(default=5, description="Maximum number of suggestions per issue")


class GrammarCheckRequest(BaseModel):
    """Request model for grammar check endpoint."""

    requestId: str | None = Field(
        default=None, description="Optional client-provided request ID"
    )
    contentType: Literal["text/html"] = Field(
        default="text/html", description="Content type (currently only text/html supported)"
    )
    language: str = Field(default="en-US", description="Language code (e.g., en-US, en-GB)")
    html: str = Field(..., description="HTML string to check")
    options: CheckOptions = Field(
        default_factory=CheckOptions, description="Optional checking options"
    )


class PlainRange(BaseModel):
    """Character range in plain text."""

    start: int = Field(..., description="Start offset in plainText")
    end: int = Field(..., description="End offset in plainText")


class GrammarIssue(BaseModel):
    """A single grammar issue."""

    type: Literal["grammar", "spelling", "style"] = Field(..., description="Type of issue")
    severity: Literal["error", "warning", "info"] = Field(..., description="Severity level")
    message: str = Field(..., description="Human-readable detailed message")
    shortMessage: str = Field(..., description="Short label for the issue")
    plainRange: PlainRange = Field(..., description="Character range in plainText")
    context: str = Field(..., description="Snippet around the error")
    suggestions: list[str] = Field(
        default_factory=list, description="List of suggested corrections"
    )
    replacement: str | None = Field(
        default=None, description="Single best replacement (if available)"
    )
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Confidence score (0.0-1.0)")


class ResponseStats(BaseModel):
    """Statistics about the response."""

    latencyMs: int = Field(..., description="Request processing latency in milliseconds")
    engine: Literal["llm", "hybrid", "languagetool", "fallback"] = Field(
        ..., description="Engine used for checking"
    )


class GrammarCheckResponse(BaseModel):
    """Response model for grammar check endpoint."""

    requestId: str | None = Field(
        default=None, description="Request ID (echoed from request or generated)"
    )
    detectedLanguage: str = Field(..., description="Detected language code")
    plainText: str = Field(..., description="Extracted visible text from HTML")
    issues: list[GrammarIssue] = Field(default_factory=list, description="List of detected issues")
    stats: ResponseStats = Field(..., description="Response statistics")
    correctedHtml: str | None = Field(
        default=None, description="Corrected HTML (if returnCorrectedHtml=true)"
    )


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(default="ok")
    version: str = Field(default="0.1.0")


class ErrorResponse(BaseModel):
    """Error response model."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    requestId: str | None = Field(default=None, description="Request ID if available")
