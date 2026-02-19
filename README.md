# Grammar Check Service

High-quality English grammar checking service for HTML strings, powered by LLM technology.

## Features

- 🎯 **Best-in-class quality**: Uses LLM (GPT-4o-mini by default) for superior grammar correction
- 🏷️ **HTML-aware**: Safely parses HTML and extracts only visible text
- 🔧 **Configurable**: Skip specific HTML tags, adjust chunk sizes, set max suggestions
- 🚀 **Production-ready**: Includes Docker support, health checks, and structured logging
- 📊 **Detailed feedback**: Returns issues with severity, suggestions, confidence scores, and context
- 🛡️ **Robust**: Built-in retry logic, error handling, and graceful fallbacks

## Quick Start

### Prerequisites

- Python 3.11+
- OpenAI API key (or compatible LLM API)

### Installation

```bash
# Clone the repository
git clone https://github.com/PStarH/grammar-check.git
cd grammar-check

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

Copy the example environment file and configure your LLM API:

```bash
cp .env.example .env
```

Edit `.env` and set your API key:

```env
LLM_API_KEY=your-api-key-here
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

### Run the Server

```bash
# Development
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Using Docker

```bash
# Build and run with docker-compose
docker-compose up -d

# Or build manually
docker build -t grammar-check .
docker run -p 8000:8000 --env-file .env grammar-check
```

## API Documentation

### Health Check

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

### Grammar Check

**Endpoint:** `POST /v1/grammar/check`

#### Request Schema

```json
{
  "requestId": "optional-client-id",
  "contentType": "text/html",
  "language": "en-US",
  "html": "<p>He go to school yesterday.</p>",
  "options": {
    "skipTags": ["script", "style", "code", "pre"],
    "mode": "best_quality",
    "returnCorrectedHtml": false,
    "maxSuggestions": 5
  }
}
```

#### Request Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `requestId` | string | No | auto-generated | Client-provided request ID for tracking |
| `contentType` | string | No | "text/html" | Content type (only text/html supported) |
| `language` | string | No | "en-US" | Language code |
| `html` | string | Yes | - | HTML content to check |
| `options.skipTags` | array | No | ["script","style","code","pre"] | HTML tags to skip |
| `options.mode` | string | No | "best_quality" | Checking mode (see below) |
| `options.returnCorrectedHtml` | boolean | No | false | Return corrected HTML |
| `options.maxSuggestions` | number | No | 5 | Max suggestions per issue |

**Checking Modes:**
- `best_quality`: LLM-only (highest quality)
- `hybrid`: LLM with LanguageTool fallback
- `fast`: LanguageTool only (not fully implemented)

#### Response Schema

```json
{
  "requestId": "...",
  "detectedLanguage": "en",
  "plainText": "He go to school yesterday.",
  "issues": [
    {
      "type": "grammar",
      "severity": "error",
      "message": "Subject-verb agreement error. 'He' requires 'goes' or 'went'.",
      "shortMessage": "Subject-verb agreement",
      "plainRange": {
        "start": 3,
        "end": 5
      },
      "context": "He go to school",
      "suggestions": ["went", "goes"],
      "replacement": "went",
      "confidence": 0.95
    }
  ],
  "stats": {
    "latencyMs": 1234,
    "engine": "llm"
  }
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `requestId` | string | Request ID (echoed or generated) |
| `detectedLanguage` | string | Detected language code |
| `plainText` | string | Extracted visible text from HTML |
| `issues` | array | List of grammar issues found |
| `issues[].type` | string | Issue type: grammar, spelling, or style |
| `issues[].severity` | string | Severity: error, warning, or info |
| `issues[].message` | string | Detailed explanation |
| `issues[].shortMessage` | string | Brief label |
| `issues[].plainRange` | object | Character offsets in plainText |
| `issues[].context` | string | Text snippet around the issue |
| `issues[].suggestions` | array | Suggested corrections |
| `issues[].replacement` | string | Best suggestion |
| `issues[].confidence` | number | Confidence score (0.0-1.0) |
| `stats.latencyMs` | number | Processing time in milliseconds |
| `stats.engine` | string | Engine used: llm, hybrid, languagetool, fallback |

### Example Usage

#### Basic Check

```bash
curl -X POST http://localhost:8000/v1/grammar/check \
  -H "Content-Type: application/json" \
  -d '{
    "html": "<p>He go to school yesterday.</p>",
    "language": "en-US"
  }'
```

#### With Custom Options

```bash
curl -X POST http://localhost:8000/v1/grammar/check \
  -H "Content-Type: application/json" \
  -d '{
    "requestId": "req-123",
    "html": "<div><p>Their going to the store.</p><script>alert(\"test\");</script></div>",
    "language": "en-US",
    "options": {
      "skipTags": ["script", "style"],
      "mode": "best_quality",
      "maxSuggestions": 3
    }
  }'
```

#### Complex HTML

```bash
curl -X POST http://localhost:8000/v1/grammar/check \
  -H "Content-Type: application/json" \
  -d '{
    "html": "<article><h1>News Article</h1><p>The company have announced a new product. It will be available in stores soon.</p></article>",
    "language": "en-US"
  }'
```

## Development

### Install Development Dependencies

```bash
pip install -r requirements-dev.txt
```

### Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_html_extract.py

# Run with verbose output
pytest -v
```

### Code Formatting and Linting

```bash
# Format code with Black
black app/ tests/

# Lint with Ruff
ruff check app/ tests/

# Fix auto-fixable issues
ruff check --fix app/ tests/
```

## Project Structure

```
grammar-check/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── schemas.py           # Pydantic models
│   ├── html_extract.py      # HTML parsing and text extraction
│   ├── llm_client.py        # LLM integration
│   └── grammar_service.py   # Grammar checking orchestration
├── tests/
│   ├── __init__.py
│   ├── test_html_extract.py
│   ├── test_grammar_service.py
│   └── test_api.py
├── .env.example             # Example environment variables
├── .gitignore
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml           # Project configuration
├── requirements.txt         # Production dependencies
├── requirements-dev.txt     # Development dependencies
└── README.md
```

## Architecture

### HTML Processing Flow

1. **HTML Parsing**: Uses BeautifulSoup to safely parse HTML
2. **Tag Filtering**: Removes specified tags (script, style, etc.)
3. **Text Extraction**: Extracts only visible text nodes
4. **Normalization**: Converts HTML entities, normalizes whitespace
5. **Plain Text**: Returns clean text with character offsets

### Grammar Checking Flow

1. **Text Chunking**: Splits long text into manageable chunks (~2000 chars)
2. **LLM Processing**: Sends each chunk to LLM with structured prompt
3. **Issue Parsing**: Validates and parses JSON response from LLM
4. **Offset Merging**: Adjusts character offsets for merged results
5. **Response Building**: Constructs final response with statistics

### Error Handling

- **Retry Logic**: 3 attempts with exponential backoff for LLM calls
- **Timeouts**: 30-second timeout per LLM request
- **Fallback**: Returns empty issues list on error (graceful degradation)
- **Validation**: Strict JSON schema validation for LLM responses

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LLM_API_KEY` | Yes | - | API key for LLM service |
| `LLM_BASE_URL` | No | https://api.openai.com/v1 | Base URL for LLM API |
| `LLM_MODEL` | No | gpt-4o-mini | Model name to use |
| `LOG_LEVEL` | No | INFO | Logging level |

### Limits

- Maximum input length: 50,000 characters
- Chunk size: 2,000 characters
- LLM timeout: 30 seconds per request
- Max retries: 3 attempts

## Production Deployment

### Using Gunicorn

```bash
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 60 \
  --log-level info
```

### Using Docker Swarm

```yaml
version: '3.8'
services:
  grammar-check:
    image: grammar-check:latest
    deploy:
      replicas: 3
      restart_policy:
        condition: on-failure
    ports:
      - "8000:8000"
    environment:
      - LLM_API_KEY=${LLM_API_KEY}
```

### Health Monitoring

The service includes a `/health` endpoint that returns:
- HTTP 200 on success
- Service version
- Ready/alive status

Use this for:
- Load balancer health checks
- Kubernetes liveness/readiness probes
- Monitoring systems

## Troubleshooting

### LLM Service Not Configured

**Error**: `503 Service Unavailable: LLM service not configured`

**Solution**: Set the `LLM_API_KEY` environment variable

### JSON Parsing Errors

**Issue**: LLM returns invalid JSON

**Solution**: The service automatically tries to extract JSON from markdown code blocks and retries on failure

### High Latency

**Causes**:
- Long input text (gets chunked)
- Complex grammar issues
- LLM API latency

**Solutions**:
- Use smaller text chunks
- Consider caching for repeated checks
- Scale horizontally with multiple workers

## License

MIT License - see LICENSE file for details

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## Support

For issues, questions, or contributions, please open an issue on GitHub.