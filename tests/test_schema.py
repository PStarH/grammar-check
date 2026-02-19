import pytest
from pydantic import ValidationError

from app.schemas import CheckResponse


def test_response_schema_strict_rejects_extra() -> None:
    with pytest.raises(ValidationError):
        CheckResponse.model_validate(
            {
                "requestId": "1",
                "detectedLanguage": "en",
                "plainText": "x",
                "issues": [],
                "stats": {"engine": "fallback", "latencyMs": 1, "chunks": 1, "cacheHit": False},
                "extra": "not allowed",
            }
        )
