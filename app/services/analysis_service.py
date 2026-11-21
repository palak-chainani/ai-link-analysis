"""End-to-end orchestration of the link-analysis pipeline (T13 and part of T15)."""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass

from ..config import Settings
from ..schemas import LinkAnalysisResponse
from ..utils.validators import ensure_public_url
from .competitor_service import build_brand
from .llm_service import generate_analysis
from .website_extractor import extract_page_data, fetch_html

logger = logging.getLogger(__name__)


class _AnalysisCache:
    """Small bounded in-memory cache keyed by URL plus content fingerprint."""

    def __init__(self, ttl_seconds: int, max_entries: int = 256) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._entries: dict[str, tuple[float, LinkAnalysisResponse]] = {}

    def get(self, key: str) -> LinkAnalysisResponse | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        created, value = entry
        if time.monotonic() - created > self.ttl_seconds:
            self._entries.pop(key, None)
            return None
        return value

    def set(self, key: str, value: LinkAnalysisResponse) -> None:
        if len(self._entries) >= self.max_entries:
            oldest = min(self._entries, key=lambda item: self._entries[item][0])
            self._entries.pop(oldest, None)
        self._entries[key] = (time.monotonic(), value)

    def clear(self) -> None:
        self._entries.clear()


_cache = _AnalysisCache(ttl_seconds=3600)


def configure_cache(settings: Settings) -> None:
    """Apply configured TTL at application startup."""
    global _cache
    _cache = _AnalysisCache(ttl_seconds=settings.cache_ttl_seconds)


async def analyze_url(url: str, settings: Settings) -> LinkAnalysisResponse:
    """Validate, fetch, extract, analyse and return a complete structured response."""
    started = time.monotonic()

    validated_url = ensure_public_url(url, settings.max_url_length)
    logger.info("validated url for analysis host=%s", validated_url.split("/")[2])

    html, final_url = await fetch_html(validated_url, settings)
    page = extract_page_data(html, final_url, settings)
    logger.info(
        "page extracted tokens=%s flags=%s",
        page.token_estimate,
        sum(page.flags.values()),
    )

    fingerprint = hashlib.sha256(
        f"{final_url}\n{page.text}".encode("utf-8", errors="replace")
    ).hexdigest()
    cached = _cache.get(fingerprint)
    if cached is not None:
        logger.info("cache hit; skipping LLM call")
        return cached

    analysis = await generate_analysis(page, settings)
    response = LinkAnalysisResponse(
        success=True,
        website=final_url,
        brand=build_brand(analysis, page),
        analysis=analysis,
    )
    _cache.set(fingerprint, response)
    logger.info("analysis complete duration_seconds=%.2f", time.monotonic() - started)
    return response
