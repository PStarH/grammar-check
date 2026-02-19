# Grammar Check (HTML -> Grammar/Spelling/Style JSON)

Best-quality English grammar/spelling/style checker for HTML strings with a FastAPI API, multi-pass LLM pipeline, fallback support, caching, and an evaluation harness.

## Features
- **Strict JSON API**: `POST /v1/grammar/check`
- **HTML visible-text extraction** with configurable `skipTags` and deterministic offsets
- **Multi-pass LLM** pipeline: detect + verify (prompt-versioned)
- **Hybrid/fallback modes**: optional LanguageTool
- **Performance controls**: async concurrency, timeout, chunking, request/chunk TTL cache, latency p50/p95 logs
- **Evaluation harness**: curated cases + precision/recall/suggestion-quality metrics

## Quickstart
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env
uvicorn app.main:app --reload
```

Health:
```bash
curl http://localhost:8000/health
```

Grammar API:
```bash
curl -X POST http://localhost:8000/v1/grammar/check \
  -H 'content-type: application/json' \
  -d '{
    "requestId":"req-1",
    "contentType":"text/html",
    "language":"en-US",
    "html":"<p>He go to school yesterday.</p>",
    "options":{
      "skipTags":["script","style","code","pre"],
      "mode":"best_quality",
      "returnCorrectedHtml":false,
      "maxSuggestions":5,
      "maxChunkChars":1200
    }
  }'
```

## API shape
Request and response follow strict schema in `app/schemas.py`.

## Architecture
- `app/main.py`: routes
- `app/schemas.py`: request/response and LLM schema
- `app/html_extract.py`: visible text extraction and normalization
- `app/chunking.py`: paragraph/sentence-ish chunking with offsets
- `app/llm_client.py`: OpenAI-compatible async client + strict JSON parsing/retries
- `app/languagetool_client.py`: optional fallback/complement
- `app/grammar_service.py`: orchestration, merging, heuristics, caching, latency stats
- `prompts/v1_detect.txt`, `prompts/v1_verify.txt`: prompt templates

## How to iterate quality
1. Edit `prompts/v1_detect.txt` / `prompts/v1_verify.txt` or create `prompts/v2_*.txt`.
2. Set `PROMPT_VERSION=v2` in env.
3. Run:
   ```bash
   make eval
   ```
4. Review `eval/results.json` and compare precision/recall/suggestion quality.
5. Add new targeted cases under `eval/cases/` for observed regressions.

## Evaluation harness
- Cases: `eval/cases/*.json` (15+ included)
- Runner: `scripts/run_eval.py`
- Metrics:
  - precision/recall via span-overlap + type matching
  - suggestion quality heuristic (`replacement` should be meaningful)

Run:
```bash
make eval
cat eval/results.json
```

## Testing & linting
```bash
make test
make lint
make format
```

## Performance knobs
- `LLM_TIMEOUT_SECONDS`
- `CONCURRENCY_LIMIT`
- `CACHE_TTL_SECONDS`
- `maxChunkChars` request option
- `mode`: `best_quality`, `hybrid`, `fast`

## Docker
```bash
docker compose up --build
```

## Notes
- LLM is the primary engine for best quality.
- If LLM fails/timeouts and no LanguageTool configured, API still returns 200 with empty issues and `stats.engine="fallback"`.
