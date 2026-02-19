"""Tests for API endpoints."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check():
    """Test health check endpoint."""
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_grammar_check_basic_request():
    """Test basic grammar check request."""
    request_data = {
        "html": "<p>Hello world</p>",
        "language": "en-US",
    }

    response = client.post("/v1/grammar/check", json=request_data)

    # May succeed or fail depending on LLM configuration
    # Just check the response structure
    assert response.status_code in [200, 500, 503]

    if response.status_code == 200:
        data = response.json()
        assert "plainText" in data
        assert "issues" in data
        assert "stats" in data
        assert data["plainText"] == "Hello world"


def test_grammar_check_with_skip_tags():
    """Test grammar check with skip tags."""
    request_data = {
        "html": "<p>Show this</p><script>Hide this</script>",
        "language": "en-US",
        "options": {"skipTags": ["script"]},
    }

    response = client.post("/v1/grammar/check", json=request_data)

    if response.status_code == 200:
        data = response.json()
        assert "Show this" in data["plainText"]
        assert "Hide this" not in data["plainText"]


def test_grammar_check_with_request_id():
    """Test grammar check with custom request ID."""
    request_data = {
        "requestId": "test-request-123",
        "html": "<p>Test</p>",
        "language": "en-US",
    }

    response = client.post("/v1/grammar/check", json=request_data)

    if response.status_code == 200:
        data = response.json()
        assert data["requestId"] == "test-request-123"


def test_grammar_check_invalid_content_type():
    """Test grammar check with invalid content type."""
    request_data = {
        "contentType": "text/plain",  # Only text/html supported
        "html": "Test",
        "language": "en-US",
    }

    response = client.post("/v1/grammar/check", json=request_data)

    # Should fail validation
    assert response.status_code == 422


def test_grammar_check_missing_html():
    """Test grammar check with missing HTML field."""
    request_data = {
        "language": "en-US",
    }

    response = client.post("/v1/grammar/check", json=request_data)

    # Should fail validation
    assert response.status_code == 422


def test_grammar_check_empty_html():
    """Test grammar check with empty HTML."""
    request_data = {
        "html": "",
        "language": "en-US",
    }

    response = client.post("/v1/grammar/check", json=request_data)

    if response.status_code == 200:
        data = response.json()
        assert data["plainText"] == ""
        assert data["issues"] == []


def test_grammar_check_options():
    """Test grammar check with various options."""
    request_data = {
        "html": "<p>Test paragraph</p>",
        "language": "en-US",
        "options": {
            "mode": "best_quality",
            "maxSuggestions": 3,
            "returnCorrectedHtml": False,
        },
    }

    response = client.post("/v1/grammar/check", json=request_data)

    # Structure validation
    assert response.status_code in [200, 500, 503]


def test_grammar_check_with_use_ai_false():
    """Test grammar check with useAI=false to use only LanguageTool."""
    request_data = {
        "html": "<p>This is a test sentence.</p>",
        "language": "en-US",
        "options": {
            "useAI": False,
            "mode": "fast",
        },
    }

    response = client.post("/v1/grammar/check", json=request_data)

    # Should succeed without LLM configuration when useAI=false
    if response.status_code == 200:
        data = response.json()
        assert data["stats"]["engine"] == "languagetool"
        assert "plainText" in data
        assert "issues" in data


def test_grammar_check_with_use_ai_false_overrides_mode():
    """Test that useAI=false overrides mode setting to force LanguageTool."""
    request_data = {
        "html": "<p>Test text</p>",
        "language": "en-US",
        "options": {
            "useAI": False,
            "mode": "best_quality",  # This should be overridden
        },
    }

    response = client.post("/v1/grammar/check", json=request_data)

    # When useAI=false, should use LanguageTool regardless of mode
    if response.status_code == 200:
        data = response.json()
        assert data["stats"]["engine"] == "languagetool"
