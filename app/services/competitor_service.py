"""Competitor-section rules and brand shaping (T08)."""

from __future__ import annotations

from ..schemas import AnalysisSections, Brand
from .website_extractor import PageData

COMPETITOR_RULES = """\
COMPETITOR ANALYSIS RULES:
- Report your brand name, main business category and a short business overview in
  brand_name, brand_category and brand_summary. Take them from the page content.
- Identify at least three relevant competitors when the business category is clear.
- Every competitor object must include name, main_service, target_market, strengths,
  weaknesses and source.
- Set source to "website_content" only when the competitor is explicitly named on
  the submitted page. Otherwise set source to "ai_suggestion".
- Never invent market share, revenue, traffic or ranking figures.
- your_advantages and opportunities must reference real signals from the page
  (for example pricing claims, service breadth, missing case studies or weak SEO).
"""


def competitor_prompt_rules(flags: dict[str, bool]) -> str:
    """Return competitor rules adapted to what the page actually contains."""
    rules = [COMPETITOR_RULES]
    if flags.get("competitor_terms_found"):
        rules.append(
            "- The page mentions competitors or comparisons: prefer those named brands "
            "and mark them website_content."
        )
    else:
        rules.append(
            "- The page does not appear to name competitors: suggest plausible "
            "category-relevant competitors and label each one ai_suggestion."
        )
    if not flags.get("has_meta_description"):
        rules.append(
            "- No meta description was found; derive the overview from headings and body text."
        )
    return "\n".join(rules)


def build_brand(analysis: AnalysisSections, page: PageData) -> Brand:
    """Build the top-level brand object from the validated competitor section."""
    section = analysis.competitor_analysis
    name = section.brand_name.strip() or page.title or "Unknown brand"
    category = section.brand_category.strip() or "Business Services"
    summary = (
        section.brand_summary.strip()
        or section.brand_overview.strip()
        or page.meta_description
        or "Business overview not specified on site."
    )
    return Brand(name=name, category=category, summary=summary)
