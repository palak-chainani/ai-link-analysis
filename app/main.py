"""FastAPI application and HTTP error mapping (T14)."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .config import get_settings
from .schemas import (
    ErrorResponse,
    HealthResponse,
    LinkAnalysisRequest,
    LinkAnalysisResponse,
)
from .services.analysis_service import analyze_url, configure_cache
from .services.llm_service import LLMConfigurationError, LLMError
from .services.website_extractor import FetchError, NoAnalysableContentError
from .utils.validators import URLValidationError

logger = logging.getLogger(__name__)

DESCRIPTION = """
Analyse a public website and return structured competitor, search-query, SEO,
service and target-audience insights generated from the page content by an LLM.

Start with `POST /link-analysis` and a JSON body containing a `url` field.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    configure_cache(settings)
    if not settings.configured_providers():
        logger.warning(
            "No LLM API key configured. Requests will fail until a provider key is set."
        )
    else:
        logger.info("LLM provider ready: %s", settings.configured_providers()[0])
    yield


app = FastAPI(
    title="AI-Powered Website Link Analysis API",
    description=DESCRIPTION,
    version="1.0.0",
    lifespan=lifespan,
)


def _error(status: int, code: str, detail: str) -> JSONResponse:
    payload = ErrorResponse(success=False, error=code, detail=detail)
    return JSONResponse(status_code=status, content=payload.model_dump())


@app.exception_handler(URLValidationError)
async def url_validation_handler(request: Request, exc: URLValidationError) -> JSONResponse:
    return _error(400, exc.code, str(exc))


@app.exception_handler(NoAnalysableContentError)
async def no_content_handler(request: Request, exc: NoAnalysableContentError) -> JSONResponse:
    return _error(422, exc.code, str(exc))


@app.exception_handler(FetchError)
async def fetch_error_handler(request: Request, exc: FetchError) -> JSONResponse:
    return _error(502, exc.code, str(exc))


@app.exception_handler(LLMConfigurationError)
async def llm_config_handler(request: Request, exc: LLMConfigurationError) -> JSONResponse:
    return _error(503, exc.code, str(exc))


@app.exception_handler(LLMError)
async def llm_error_handler(request: Request, exc: LLMError) -> JSONResponse:
    return _error(503, exc.code, str(exc))


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error while processing %s", request.url.path)
    return _error(500, "internal_error", "An unexpected server error occurred")


@app.get("/health", response_model=HealthResponse, tags=["Diagnostics"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="link-analysis")


@app.post(
    "/link-analysis",
    response_model=LinkAnalysisResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid or blocked URL"},
        422: {"model": ErrorResponse, "description": "No analysable page content"},
        502: {"model": ErrorResponse, "description": "Website could not be fetched"},
        503: {"model": ErrorResponse, "description": "LLM analysis unavailable"},
    },
    tags=["Analysis"],
)
async def link_analysis(payload: LinkAnalysisRequest) -> LinkAnalysisResponse:
    settings = get_settings()
    return await analyze_url(payload.url, settings)
