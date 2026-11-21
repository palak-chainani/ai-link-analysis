"""API and LLM data contracts (T03).

The Pydantic models below are used three ways:
1. FastAPI request/response validation.
2. Validation of the raw LLM output.
3. Source of the JSON schema injected into the LLM prompt.
"""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, Field

Platform = Literal["Google", "Facebook", "Instagram", "LinkedIn", "X"]
Source = Literal["website_content", "ai_suggestion"]

REQUIRED_PLATFORMS = {"Google", "Facebook", "Instagram", "LinkedIn", "X"}


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------
class LinkAnalysisRequest(BaseModel):
    url: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="Public http/https website URL to analyse.",
    )


# ---------------------------------------------------------------------------
# Top-level brand summary
# ---------------------------------------------------------------------------
class Brand(BaseModel):
    name: str = Field(..., description="Brand name identified on the website.")
    category: str = Field(..., description="Main business category of the brand.")
    summary: str = Field(..., description="Short human-friendly business overview.")


# ---------------------------------------------------------------------------
# Section 1 - Competitor vs Your Brand
# ---------------------------------------------------------------------------
class CompetitorItem(BaseModel):
    name: str = Field(..., description="Competitor brand name.")
    main_service: str = Field(..., description="Competitor's main service or product.")
    target_market: str = Field(..., description="Competitor's target market segment.")
    strengths: list[str] = Field(..., description="Competitor strengths.")
    weaknesses: list[str] = Field(..., description="Competitor gaps or weaknesses.")
    source: Source = Field(
        ...,
        description="website_content if named on the page, otherwise ai_suggestion.",
    )


class CompetitorAnalysis(BaseModel):
    brand_name: str = Field(..., description="Your brand name from the website.")
    brand_category: str = Field(..., description="Your main business category.")
    brand_summary: str = Field(..., description="Your business overview.")
    brand_overview: str = Field(..., description="Overview of your brand in the market.")
    competitors: list[CompetitorItem] = Field(
        ..., description="At least three competitors when the category is clear."
    )
    strengths: list[str] = Field(..., description="Your brand's strengths.")
    weaknesses: list[str] = Field(..., description="Your brand's gaps or weaknesses.")
    your_advantages: list[str] = Field(..., description="Your competitive advantages.")
    opportunities: list[str] = Field(
        ..., description="Opportunities to improve market positioning."
    )


# ---------------------------------------------------------------------------
# Section 2 - Target search queries
# ---------------------------------------------------------------------------
class SearchQuery(BaseModel):
    query: str = Field(..., description="Realistic search phrase a customer might use.")
    platform: Platform = Field(..., description="One of the five supported platforms.")
    intent: str = Field(..., description="Short search intent label, e.g. Service Search.")
    business_relevance: str = Field(..., description="Why this query matters to the business.")
    target_audience: str = Field(..., description="Who is likely to use this query.")


# ---------------------------------------------------------------------------
# Section 3 - SEO improvement
# ---------------------------------------------------------------------------
class SeoImprovements(BaseModel):
    primary_keyword: str = Field(..., description="Primary keyword for the business.")
    secondary_keywords: list[str] = Field(..., description="Related secondary keywords.")
    long_tail_keywords: list[str] = Field(..., description="Specific long-tail keywords.")
    recommended_title: str = Field(..., description="Recommended SEO page title.")
    meta_description: str = Field(..., description="Short human-friendly meta description.")
    supporting_content: list[str] = Field(
        ..., description="Additional pages or articles that improve visibility."
    )


# ---------------------------------------------------------------------------
# Section 4 - Top services
# ---------------------------------------------------------------------------
class ServiceItem(BaseModel):
    service_name: str = Field(..., description="Name of the service.")
    description: str = Field(..., description="Short explanation of the service.")
    target_industry: str = Field(..., description="Relevant industry for this service.")
    target_customer: str = Field(..., description="Customer type for this service.")
    main_benefit: str = Field(..., description="Why customers need this service.")
    source: Source = Field(
        ...,
        description="website_content if explicitly on the page, otherwise ai_suggestion.",
    )


# ---------------------------------------------------------------------------
# Section 5 - Target audience
# ---------------------------------------------------------------------------
class TargetAudience(BaseModel):
    primary_audience: list[str] = Field(..., description="Primary customer groups.")
    secondary_audience: list[str] = Field(..., description="Secondary customer groups.")
    industries: list[str] = Field(..., description="Relevant industry segments.")
    business_types: list[str] = Field(..., description="Business types served.")
    customer_profiles: list[str] = Field(..., description="Representative customer profiles.")
    location: str = Field(
        ..., description="Geographic focus found on the page, or 'Not specified on site'."
    )
    customer_needs: list[str] = Field(..., description="Needs and challenges to solve.")
    interests: list[str] = Field(..., description="Potential customer interests.")
    recommended_segments: list[str] = Field(
        ..., description="Marketing-ready audience segments."
    )


# ---------------------------------------------------------------------------
# Analysis container and API responses
# ---------------------------------------------------------------------------
class AnalysisSections(BaseModel):
    competitor_analysis: CompetitorAnalysis
    target_search_queries: list[SearchQuery]
    seo_improvements: SeoImprovements
    top_services: list[ServiceItem]
    target_audience: TargetAudience


class LinkAnalysisResponse(BaseModel):
    success: bool = True
    website: str
    brand: Brand
    analysis: AnalysisSections


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    detail: str


class HealthResponse(BaseModel):
    status: str
    service: str


# ---------------------------------------------------------------------------
# Schema helpers used by the LLM service
# ---------------------------------------------------------------------------
def _dereference(schema: dict) -> dict:
    """Inline $defs so provider JSON-schema APIs receive a self-contained schema."""
    definitions = schema.get("$defs", {})

    def walk(node: object) -> object:
        if isinstance(node, dict):
            if "$ref" in node:
                name = str(node["$ref"]).rsplit("/", 1)[-1]
                return walk(definitions[name])
            cleaned: dict[str, object] = {}
            for key, value in node.items():
                if key in {"$defs", "title", "default", "examples"}:
                    continue
                cleaned[key] = walk(value)
            return cleaned
        if isinstance(node, list):
            return [walk(item) for item in node]
        return node

    return walk({key: value for key, value in schema.items() if key != "$defs"})  # type: ignore[return-value]


def llm_json_schema() -> dict:
    """Return the five-section analysis schema with no external references."""
    return _dereference(AnalysisSections.model_json_schema())


def schema_as_text() -> str:
    """Compact JSON schema text for prompt injection."""
    return json.dumps(llm_json_schema(), ensure_ascii=False, separators=(",", ":"))


def validate_analysis_constraints(analysis: AnalysisSections) -> list[str]:
    """Return a list of hard-constraint violations found in LLM output."""
    issues: list[str] = []

    queries = analysis.target_search_queries
    if len(queries) != 5:
        issues.append(f"target_search_queries must contain exactly 5 items, got {len(queries)}")
    platforms = {item.platform for item in queries}
    if platforms != REQUIRED_PLATFORMS:
        issues.append(
            "target_search_queries must cover Google, Facebook, Instagram, LinkedIn and X"
        )
    if any(not item.query.strip() for item in queries):
        issues.append("target_search_queries contains an empty query")

    services = analysis.top_services
    if len(services) != 5:
        issues.append(f"top_services must contain exactly 5 items, got {len(services)}")
    names = [item.service_name.strip().lower() for item in services]
    if len(names) != len(set(names)):
        issues.append("top_services contains duplicate service names")
    if any(not item.service_name.strip() for item in services):
        issues.append("top_services contains an empty service name")

    competitors = analysis.competitor_analysis.competitors
    if not competitors:
        issues.append("competitor_analysis.competitors must not be empty")
    if any(not item.name.strip() for item in competitors):
        issues.append("competitor_analysis.competitors contains an empty name")

    seo = analysis.seo_improvements
    if not seo.primary_keyword.strip():
        issues.append("seo_improvements.primary_keyword must not be empty")
    if not seo.recommended_title.strip() or not seo.meta_description.strip():
        issues.append("seo_improvements title and meta description must not be empty")

    audience = analysis.target_audience
    list_fields = {
        "primary_audience": audience.primary_audience,
        "secondary_audience": audience.secondary_audience,
        "industries": audience.industries,
        "recommended_segments": audience.recommended_segments,
    }
    for field_name, values in list_fields.items():
        if not values:
            issues.append(f"target_audience.{field_name} must not be empty")

    return issues
