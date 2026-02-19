"""FastAPI application for grammar checking service."""

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.grammar_service import GrammarService
from app.html_extract import extract_plain_text
from app.llm_client import LLMClient
from app.schemas import (
    ErrorResponse,
    GrammarCheckRequest,
    GrammarCheckResponse,
    HealthResponse,
    ResponseStats,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global service instance
grammar_service: GrammarService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown."""
    global grammar_service

    # Startup
    logger.info("Starting grammar check service...")
    try:
        llm_client = LLMClient()
        grammar_service = GrammarService(llm_client=llm_client)
        logger.info("Service initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize service: {e}")
        # Allow app to start even if LLM is not configured
        grammar_service = GrammarService(llm_client=None)

    yield

    # Shutdown
    logger.info("Shutting down grammar check service...")


app = FastAPI(
    title="Grammar Check Service",
    description="High-quality English grammar checking service for HTML strings",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="InternalServerError",
            message=str(exc),
        ).model_dump(),
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(status="ok", version="0.1.0")


@app.post("/v1/grammar/check", response_model=GrammarCheckResponse)
async def check_grammar(request: GrammarCheckRequest):
    """Check grammar in HTML content.

    Args:
        request: Grammar check request

    Returns:
        Grammar check response with issues
    """
    start_time = time.time()

    # Generate request ID if not provided
    request_id = request.requestId or str(uuid.uuid4())

    logger.info(
        f"Processing request {request_id}: "
        f"mode={request.options.mode}, "
        f"html_length={len(request.html)}"
    )

    try:
        # Extract plain text from HTML
        plain_text = extract_plain_text(request.html, skip_tags=request.options.skipTags)

        logger.info(f"Request {request_id}: Extracted {len(plain_text)} characters")

        # Check grammar
        if not grammar_service or not grammar_service.llm_client:
            if request.options.useAI and request.options.mode in ["best_quality", "hybrid"]:
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "LLM service not configured. "
                        "Please set LLM_API_KEY environment variable or set useAI=false."
                    ),
                )

        issues, engine = await grammar_service.check_text(
            plain_text,
            mode=request.options.mode,
            max_suggestions=request.options.maxSuggestions,
            use_ai=request.options.useAI,
        )

        # Calculate latency
        latency_ms = int((time.time() - start_time) * 1000)

        logger.info(
            f"Request {request_id}: Found {len(issues)} issues " f"in {latency_ms}ms using {engine}"
        )

        # Build response
        response = GrammarCheckResponse(
            requestId=request_id,
            detectedLanguage=request.language.split("-")[0],  # en-US -> en
            plainText=plain_text,
            issues=issues,
            stats=ResponseStats(
                latencyMs=latency_ms,
                engine=engine,
            ),
        )

        # Add corrected HTML if requested
        if request.options.returnCorrectedHtml:
            # This would require implementing HTML correction logic
            # For now, return None
            response.correctedHtml = None

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Request {request_id} failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Grammar check failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
