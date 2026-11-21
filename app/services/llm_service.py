"""LLM integration: prompts, provider calls, JSON validation and retries (T07)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.parse import quote

import httpx

from ..config import Settings
from ..schemas import AnalysisSections, llm_json_schema, schema_as_text, validate_analysis_constraints
from .competitor_service import competitor_prompt_rules
from .website_extractor import PageData

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Base LLM failure."""

    code = "analysis_unavailable"


class LLMConfigurationError(LLMError):
    code = "llm_not_configured"


class LLMProviderError(LLMError):
    code = "llm_provider_error"


class LLMInvalidResponseError(LLMError):
    code = "llm_invalid_response"


class AnalysisUnavailable(LLMError):
    code = "analysis_unavailable"


# ---------------------------------------------------------------------------
# Prompt construction (Appendix B)
# ---------------------------------------------------------------------------
def _system_prompt(extra_rules: str) -> str:
    return f"""\
You are an expert digital marketing, competitor and SEO analyst.
Analyse the supplied website content and return ONE JSON object only.

GROUNDING RULES:
- Use only facts present in the supplied content for brand, service, audience and
  location claims. If something is not on the page, say "Not specified on site".
- Never output search volume, ranking position, traffic, keyword difficulty,
  market share or revenue figures.
- For competitor and service objects, use source "website_content" only when the
  item is explicitly named on the page; otherwise use "ai_suggestion".
- Keep every string concise and specific to this business. No generic filler.

{extra_rules}

SECTION REQUIREMENTS:
1. competitor_analysis: brand_name, brand_category, brand_summary, brand_overview,
   competitors (at least three when the category is clear), strengths, weaknesses,
   your_advantages and opportunities.
2. target_search_queries: exactly 5 objects covering these platforms exactly once
   each: Google, Facebook, Instagram, LinkedIn, X. Each object needs query,
   platform, intent, business_relevance and target_audience. Intent is a short
   label such as "Service Search" or "B2B Search".
3. seo_improvements: primary_keyword, secondary_keywords, long_tail_keywords,
   recommended_title, meta_description and supporting_content. The primary keyword
   should appear in the recommended title.
4. top_services: exactly 5 unique services, each with service_name, description,
   target_industry, target_customer, main_benefit and source.
5. target_audience: all nine fields must be present and non-empty, including a
   location string. Use "Not specified on site" when the page gives no location.

OUTPUT FORMAT:
Return raw JSON only. Do not use Markdown fences or add explanatory text.
The JSON must validate against this schema:
{schema_as_text()}
"""


def _user_prompt(page: PageData) -> str:
    headings = "\n".join(f"- {item}" for item in page.headings) or "- none found"
    structured = "\n".join(f"- {item}" for item in page.structured_data) or "- none found"
    flags = ", ".join(f"{key}={str(value).lower()}" for key, value in page.flags.items())
    return f"""\
Final URL: {page.final_url}
Page title: {page.title}
Meta description: {page.meta_description}
Canonical URL: {page.canonical_url}
Open Graph title: {page.og_title or 'none'}
Open Graph description: {page.og_description or 'none'}

HEADINGS:
{headings}

STRUCTURED DATA HINTS:
{structured}

SOURCE GROUNDING FLAGS:
{flags}

CLEANED PAGE CONTENT (approx {page.token_estimate} tokens):
<<<CONTENT
{page.text}
CONTENT>>>

Analyse the content above and return the five-section JSON object now.
"""


# ---------------------------------------------------------------------------
# Schema transformations for provider-specific JSON schema APIs
# ---------------------------------------------------------------------------
def _gemini_schema(schema: dict) -> dict:
    """Gemini requires uppercase type names and no additionalProperties key."""

    def walk(node: object) -> object:
        if isinstance(node, dict):
            result: dict[str, object] = {}
            for key, value in node.items():
                if key == "additionalProperties":
                    continue
                if key == "type" and isinstance(value, str):
                    result[key] = value.upper()
                else:
                    result[key] = walk(value)
            return result
        if isinstance(node, list):
            return [walk(item) for item in node]
        return node

    return walk(schema)  # type: ignore[return-value]


def _openai_schema(schema: dict) -> dict:
    """OpenAI strict mode requires additionalProperties:false on every object."""

    def walk(node: object) -> object:
        if isinstance(node, dict):
            result = {key: walk(value) for key, value in node.items()}
            if result.get("type") == "object":
                result["additionalProperties"] = False
                properties = result.get("properties", {})
                result.setdefault("required", list(properties))
            return result
        if isinstance(node, list):
            return [walk(item) for item in node]
        return node

    return walk(schema)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Provider calls - REST is used so no vendor SDK is required to run the app
# ---------------------------------------------------------------------------
def _safe_error(response: httpx.Response) -> str:
    snippet = re.sub(r"\s+", " ", response.text)[:200]
    return f"provider returned HTTP {response.status_code}: {snippet}"


def _usage(data: dict[str, Any], provider: str) -> dict[str, int]:
    if provider == "gemini":
        meta = data.get("usageMetadata", {})
        return {
            "input": int(meta.get("promptTokenCount", 0)),
            "output": int(meta.get("candidatesTokenCount", 0)),
        }
    usage = data.get("usage", {})
    if provider == "anthropic":
        return {
            "input": int(usage.get("input_tokens", 0)),
            "output": int(usage.get("output_tokens", 0)),
        }
    return {
        "input": int(usage.get("prompt_tokens", 0)),
        "output": int(usage.get("completion_tokens", 0)),
    }


async def _call_gemini(
    system: str, user: str, model: str, key: str, settings: Settings
) -> tuple[str, dict[str, int]]:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{quote(model, safe='')}:generateContent"
    )
    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {
            "temperature": settings.temperature,
            "maxOutputTokens": settings.max_output_tokens,
            "responseMimeType": "application/json",
            "responseSchema": _gemini_schema(llm_json_schema()),
        },
    }
    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            response = await client.post(url, params={"key": key}, json=payload)
    except httpx.RequestError as exc:
        raise LLMProviderError("Gemini request failed") from exc

    if response.status_code >= 400:
        raise LLMProviderError(f"Gemini {_safe_error(response)}")

    try:
        data = response.json()
    except ValueError as exc:
        raise LLMProviderError("Gemini returned a non-JSON response") from exc

    candidates = data.get("candidates") or []
    if not candidates:
        raise LLMProviderError("Gemini returned no candidates")
    candidate = candidates[0]
    finish = candidate.get("finishReason")
    if finish not in (None, "STOP", "MAX_TOKENS"):
        raise LLMProviderError(f"Gemini stopped generation with reason {finish}")
    parts = candidate.get("content", {}).get("parts", [])
    text = "".join(str(part.get("text", "")) for part in parts if isinstance(part, dict))
    if not text.strip():
        raise LLMProviderError("Gemini returned empty content")
    return text, _usage(data, "gemini")


async def _call_openai(
    system: str, user: str, model: str, key: str, settings: Settings
) -> tuple[str, dict[str, int]]:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {key}"}
    strict_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "link_analysis",
            "strict": True,
            "schema": _openai_schema(llm_json_schema()),
        },
    }
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": strict_format,
        "max_completion_tokens": settings.max_output_tokens,
    }

    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 400 and "json_schema" in response.text.lower():
                # Some models do not support strict schemas; fall back to JSON mode.
                payload["response_format"] = {"type": "json_object"}
                response = await client.post(url, headers=headers, json=payload)
    except httpx.RequestError as exc:
        raise LLMProviderError("OpenAI request failed") from exc

    if response.status_code >= 400:
        raise LLMProviderError(f"OpenAI {_safe_error(response)}")

    try:
        data = response.json()
    except ValueError as exc:
        raise LLMProviderError("OpenAI returned a non-JSON response") from exc

    try:
        message = data["choices"][0]["message"]
    except (KeyError, IndexError) as exc:
        raise LLMProviderError("OpenAI returned an unexpected response shape") from exc
    content = message.get("content", "")
    if isinstance(content, list):
        content = "".join(
            str(part.get("text", "")) for part in content if isinstance(part, dict)
        )
    if not str(content).strip():
        raise LLMProviderError("OpenAI returned empty content")
    return str(content), _usage(data, "openai")


async def _call_anthropic(
    system: str, user: str, model: str, key: str, settings: Settings
) -> tuple[Any, dict[str, int]]:
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": settings.max_output_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
        "tools": [
            {
                "name": "submit_analysis",
                "description": "Return the structured website analysis.",
                "input_schema": llm_json_schema(),
            }
        ],
        "tool_choice": {"type": "tool", "name": "submit_analysis"},
    }
    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.RequestError as exc:
        raise LLMProviderError("Anthropic request failed") from exc

    if response.status_code >= 400:
        raise LLMProviderError(f"Anthropic {_safe_error(response)}")

    try:
        data = response.json()
    except ValueError as exc:
        raise LLMProviderError("Anthropic returned a non-JSON response") from exc

    for block in data.get("content", []):
        if isinstance(block, dict) and block.get("type") == "tool_use":
            tool_input = block.get("input")
            if isinstance(tool_input, dict):
                return tool_input, _usage(data, "anthropic")
    text_blocks = [
        str(block.get("text", ""))
        for block in data.get("content", [])
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    text = "".join(text_blocks)
    if not text.strip():
        raise LLMProviderError("Anthropic returned no analysable content")
    return text, _usage(data, "anthropic")


# ---------------------------------------------------------------------------
# Parsing and orchestration
# ---------------------------------------------------------------------------
def _parse_json(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        raise LLMInvalidResponseError("LLM returned an unsupported response type")

    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise LLMInvalidResponseError("LLM response did not contain a JSON object")
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMInvalidResponseError(f"LLM returned invalid JSON: {exc.msg}") from exc
    if not isinstance(parsed, dict):
        raise LLMInvalidResponseError("LLM JSON root must be an object")
    return parsed


async def generate_analysis(page: PageData, settings: Settings) -> AnalysisSections:
    """Produce a validated five-section analysis using primary + fallback providers."""
    providers = settings.configured_providers()
    if not providers:
        raise LLMConfigurationError(
            "No LLM API key is configured. Set GEMINI_API_KEY, OPENAI_API_KEY "
            "or ANTHROPIC_API_KEY in the environment."
        )

    system = _system_prompt(competitor_prompt_rules(page.flags))
    base_user = _user_prompt(page)
    last_error: Exception | None = None

    for provider in providers:
        model = settings.model_for(provider)
        key = settings.api_key_for(provider)
        if not key:
            continue
        for attempt in range(settings.max_retries + 1):
            user = base_user
            if attempt > 0 and last_error is not None:
                user = (
                    base_user
                    + "\n\nCORRECTION REQUEST:\nThe previous response failed validation: "
                    + str(last_error)
                    + "\nReturn a corrected JSON object only, with every required field."
                )
            try:
                if provider == "gemini":
                    raw, usage = await _call_gemini(system, user, model, key, settings)
                elif provider == "openai":
                    raw, usage = await _call_openai(system, user, model, key, settings)
                else:
                    raw, usage = await _call_anthropic(system, user, model, key, settings)

                parsed = _parse_json(raw)
                analysis = AnalysisSections.model_validate(parsed)
                issues = validate_analysis_constraints(analysis)
                if issues:
                    raise LLMInvalidResponseError("; ".join(issues))

                logger.info(
                    "analysis generated provider=%s model=%s attempt=%s input_tokens=%s "
                    "output_tokens=%s",
                    provider,
                    model,
                    attempt + 1,
                    usage["input"],
                    usage["output"],
                )
                return analysis

            except (LLMProviderError, LLMInvalidResponseError, ValueError) as exc:
                last_error = exc
                logger.warning(
                    "LLM attempt failed provider=%s model=%s attempt=%s reason=%s",
                    provider,
                    model,
                    attempt + 1,
                    str(exc)[:200],
                )

    raise AnalysisUnavailable(
        f"All LLM attempts failed. Last error: {str(last_error)[:200] if last_error else 'unknown'}"
    )
