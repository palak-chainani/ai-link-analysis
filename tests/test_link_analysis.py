"""Tests for the link-analysis API (T16). External services are always mocked."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app
from app.schemas import (
    AnalysisSections,
    CompetitorAnalysis,
    CompetitorItem,
    SearchQuery,
    SeoImprovements,
    ServiceItem,
    TargetAudience,
    validate_analysis_constraints,
)
from app.services.analysis_service import _cache
from app.services.llm_service import AnalysisUnavailable
from app.services.website_extractor import (
    FetchTimeoutError,
    NoAnalysableContentError,
    PageData,
    fetch_html,
)
from app.utils.validators import BlockedAddressError, DisallowedSchemeError, ensure_public_url, validate_url

PLATFORMS = ["Google", "Facebook", "Instagram", "LinkedIn", "X"]


@pytest.fixture(autouse=True)
def clear_cache():
    _cache.clear()
    yield
    _cache.clear()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def settings():
    return Settings()


@pytest.fixture
def page():
    return PageData(
        final_url="https://example.com/",
        title="ABC Technologies",
        meta_description="Digital solutions for small businesses.",
        canonical_url="https://example.com/",
        og_title="",
        og_description="",
        headings=["Web Development", "About Us"],
        text="ABC Technologies provides web development and digital solutions for startups.",
        structured_data=[],
        token_estimate=120,
        flags={"has_title": True, "has_meta_description": True},
    )


@pytest.fixture
def analysis():
    competitor = CompetitorAnalysis(
        brand_name="ABC Technologies",
        brand_category="Technology Services",
        brand_summary="Digital solutions for small businesses.",
        brand_overview="A technology services provider focused on SMB clients.",
        competitors=[
            CompetitorItem(
                name=f"Competitor {index}",
                main_service="Web Development",
                target_market="Small businesses",
                strengths=["Established brand"],
                weaknesses=["High pricing"],
                source="ai_suggestion",
            )
            for index in range(1, 4)
        ],
        strengths=["Affordable solutions"],
        weaknesses=["Limited brand awareness"],
        your_advantages=["Fast delivery"],
        opportunities=["Improve online visibility"],
    )
    queries = [
        SearchQuery(
            query=f"best digital solution for {platform}",
            platform=platform,
            intent="Service Search",
            business_relevance="Matches core service",
            target_audience="Business owners",
        )
        for platform in PLATFORMS
    ]
    seo = SeoImprovements(
        primary_keyword="web development company",
        secondary_keywords=["website development services"],
        long_tail_keywords=["affordable web development for startups"],
        recommended_title="Web Development Company | ABC Technologies",
        meta_description="Professional web development for growing businesses.",
        supporting_content=["Service landing pages", "FAQ page"],
    )
    services = [
        ServiceItem(
            service_name=f"Service {index}",
            description="Responsive business websites.",
            target_industry="Technology",
            target_customer="Small businesses",
            main_benefit="Professional online presence",
            source="website_content",
        )
        for index in range(1, 6)
    ]
    audience = TargetAudience(
        primary_audience=["Small business owners"],
        secondary_audience=["Startups"],
        industries=["Technology", "Retail"],
        business_types=["SMB", "Startup"],
        customer_profiles=["Owner seeking growth"],
        location="Not specified on site",
        customer_needs=["Affordable digital presence"],
        interests=["Website design"],
        recommended_segments=["Local service businesses"],
    )
    return AnalysisSections(
        competitor_analysis=competitor,
        target_search_queries=queries,
        seo_improvements=seo,
        top_services=services,
        target_audience=audience,
    )


def _pipeline_patches(page, analysis):
    return (
        patch("app.services.analysis_service.ensure_public_url", return_value=page.final_url),
        patch(
            "app.services.analysis_service.fetch_html",
            new=AsyncMock(return_value=("<html></html>", page.final_url)),
        ),
        patch("app.services.analysis_service.extract_page_data", return_value=page),
        patch("app.services.analysis_service.generate_analysis", new=AsyncMock(return_value=analysis)),
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------
def test_happy_path_returns_all_five_sections(client, page, analysis):
    patches = _pipeline_patches(page, analysis)
    with patches[0], patches[1], patches[2], patches[3]:
        response = client.post("/link-analysis", json={"url": "https://example.com"})

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["website"] == page.final_url
    assert body["brand"]["name"] == "ABC Technologies"
    assert set(body["analysis"]) == {
        "competitor_analysis",
        "target_search_queries",
        "seo_improvements",
        "top_services",
        "target_audience",
    }
    assert len(body["analysis"]["target_search_queries"]) == 5
    assert len(body["analysis"]["top_services"]) == 5
    assert {item["platform"] for item in body["analysis"]["target_search_queries"]} == set(PLATFORMS)


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# URL validation and SSRF
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("url", ["ftp://example.com", "file:///etc/passwd", "javascript:alert(1)"])
def test_disallowed_schemes_rejected(client, url):
    response = client.post("/link-analysis", json={"url": url})
    assert response.status_code == 400
    assert response.json()["success"] is False


@pytest.mark.parametrize("url", ["http://127.0.0.1", "http://localhost", "http://192.168.1.10"])
def test_private_addresses_rejected_without_network(client, url):
    response = client.post("/link-analysis", json={"url": url})
    assert response.status_code == 400
    assert response.json()["error"] in {"invalid_url", "blocked_address"}


def test_validate_url_rejects_credentials_and_custom_ports():
    with pytest.raises(ValueError):
        validate_url("https://user:pass@example.com")
    with pytest.raises(ValueError):
        validate_url("https://example.com:8080/path")


def test_redirect_to_private_address_is_blocked(settings):
    first = "https://example.com/"
    internal = "http://127.0.0.1/admin"

    class Stream:
        def __init__(self, response):
            self.response = response

        async def __aenter__(self):
            return self.response

        async def __aexit__(self, *args):
            return False

    redirect = MagicMock()
    redirect.status_code = 302
    redirect.headers = {"location": internal}
    redirect.url = first

    http_client = MagicMock()
    http_client.stream.return_value = Stream(redirect)

    with patch(
        "app.services.website_extractor.ensure_public_url",
        side_effect=[first, first, BlockedAddressError("blocked redirect target")],
    ):
        with pytest.raises(BlockedAddressError):
            asyncio.run(fetch_html(first, settings, http_client))


def test_ensure_public_url_normalises_url():
    assert ensure_public_url("HTTPS://Example.com") == "https://example.com/"


# ---------------------------------------------------------------------------
# Failure handling
# ---------------------------------------------------------------------------
def test_fetch_timeout_maps_to_502(client, page):
    with patch("app.services.analysis_service.ensure_public_url", return_value=page.final_url), patch(
        "app.services.analysis_service.fetch_html",
        new=AsyncMock(side_effect=FetchTimeoutError("Timed out")),
    ):
        response = client.post("/link-analysis", json={"url": "https://example.com"})

    assert response.status_code == 502
    assert response.json()["error"] == "website_timeout"


def test_no_analysable_content_maps_to_422(client, page):
    with patch("app.services.analysis_service.ensure_public_url", return_value=page.final_url), patch(
        "app.services.analysis_service.fetch_html",
        new=AsyncMock(return_value=("<html></html>", page.final_url)),
    ), patch(
        "app.services.analysis_service.extract_page_data",
        side_effect=NoAnalysableContentError("No readable text"),
    ):
        response = client.post("/link-analysis", json={"url": "https://example.com"})

    assert response.status_code == 422
    assert response.json()["error"] == "no_analysable_content"


def test_llm_failure_maps_to_503(client, page):
    with patch("app.services.analysis_service.ensure_public_url", return_value=page.final_url), patch(
        "app.services.analysis_service.fetch_html",
        new=AsyncMock(return_value=("<html></html>", page.final_url)),
    ), patch("app.services.analysis_service.extract_page_data", return_value=page), patch(
        "app.services.analysis_service.generate_analysis",
        new=AsyncMock(side_effect=AnalysisUnavailable("All providers failed")),
    ):
        response = client.post("/link-analysis", json={"url": "https://example.com"})

    assert response.status_code == 503
    assert response.json()["success"] is False


def test_request_validation_error(client):
    response = client.post("/link-analysis", json={"url": ""})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Caching and constraint validation
# ---------------------------------------------------------------------------
def test_cache_hit_avoids_second_llm_call(client, page, analysis):
    generate_mock = AsyncMock(return_value=analysis)
    with patch("app.services.analysis_service.ensure_public_url", return_value=page.final_url), patch(
        "app.services.analysis_service.fetch_html",
        new=AsyncMock(return_value=("<html></html>", page.final_url)),
    ), patch("app.services.analysis_service.extract_page_data", return_value=page), patch(
        "app.services.analysis_service.generate_analysis", new=generate_mock
    ):
        client.post("/link-analysis", json={"url": "https://example.com"})
        client.post("/link-analysis", json={"url": "https://example.com"})
        assert generate_mock.call_count == 1


def test_constraint_validation_detects_missing_queries(analysis):
    trimmed = analysis.model_copy(update={"target_search_queries": analysis.target_search_queries[:4]})
    issues = validate_analysis_constraints(trimmed)
    assert any("exactly 5" in issue for issue in issues)


def test_constraint_validation_detects_duplicate_services(analysis):
    services = list(analysis.top_services)
    services[1] = services[0]
    altered = analysis.model_copy(update={"top_services": services})
    issues = validate_analysis_constraints(altered)
    assert any("duplicate" in issue for issue in issues)
