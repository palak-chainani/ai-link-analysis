"""Website fetching and content extraction (T05 and T06)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup

from ..config import Settings
from ..utils.validators import ensure_public_url

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 LinkAnalysisBot/1.0"
)

NOISE_PATTERN = re.compile(
    r"cookie|banner|modal|popup|newsletter|advert|sidebar|footer|"
    r"navigation|comment|promo|overlay|social|related|subscribe",
    re.IGNORECASE,
)
SERVICE_PATTERN = re.compile(
    r"\b(service|services|solution|solutions|offer|we provide|our work|product)\b",
    re.IGNORECASE,
)
COMPETITOR_PATTERN = re.compile(
    r"\b(competitor|alternative|compare|versus|vs\.?)\b", re.IGNORECASE
)
LOCATION_PATTERN = re.compile(
    r"\b(address|located|based in|city|street|phone|zip|postcode|we serve)\b",
    re.IGNORECASE,
)
REDIRECT_STATUSES = {301, 302, 303, 307, 308}


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class FetchError(Exception):
    """Base fetch failure."""

    code = "website_fetch_failed"

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


class FetchTimeoutError(FetchError):
    code = "website_timeout"


class FetchConnectionError(FetchError):
    code = "website_unreachable"


class BadStatusError(FetchError):
    code = "website_bad_status"


class BadContentTypeError(FetchError):
    code = "website_bad_content_type"


class FetchTooLargeError(FetchError):
    code = "website_too_large"


class TooManyRedirectsError(FetchError):
    code = "website_redirect_loop"


class NoAnalysableContentError(FetchError):
    code = "no_analysable_content"


# ---------------------------------------------------------------------------
# Page data contract
# ---------------------------------------------------------------------------
@dataclass
class PageData:
    final_url: str
    title: str
    meta_description: str
    canonical_url: str
    og_title: str
    og_description: str
    headings: list[str]
    text: str
    structured_data: list[str] = field(default_factory=list)
    token_estimate: int = 0
    flags: dict[str, bool] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# T05 - fetching with manual, validated redirects
# ---------------------------------------------------------------------------
async def fetch_html(
    url: str,
    settings: Settings,
    client: httpx.AsyncClient | None = None,
) -> tuple[str, str]:
    """Fetch HTML, validating every redirect hop against the SSRF guard."""
    owns_client = client is None
    http = client or httpx.AsyncClient(
        follow_redirects=False,
        timeout=httpx.Timeout(settings.request_timeout_seconds),
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
    )

    try:
        current = ensure_public_url(url, settings.max_url_length)
        for _ in range(settings.max_redirects + 1):
            ensure_public_url(current, settings.max_url_length)

            try:
                async with http.stream("GET", current) as response:
                    if response.status_code in REDIRECT_STATUSES:
                        location = response.headers.get("location")
                        if not location:
                            raise FetchError("Redirect response contained no Location header")
                        current = urljoin(str(response.url), location)
                        continue

                    if response.status_code >= 400:
                        raise BadStatusError(
                            f"Website returned HTTP {response.status_code}"
                        )

                    content_type = response.headers.get("content-type", "").lower()
                    if "html" not in content_type:
                        raise BadContentTypeError(
                            f"Expected an HTML page, received content type "
                            f"'{content_type or 'unknown'}'"
                        )

                    chunks: list[bytes] = []
                    total = 0
                    async for chunk in response.aiter_bytes(chunk_size=65536):
                        total += len(chunk)
                        if total > settings.max_fetch_bytes:
                            raise FetchTooLargeError(
                                f"Website exceeds the {settings.max_fetch_bytes} byte limit"
                            )
                        chunks.append(chunk)

                    charset_match = re.search(r"charset=([\w\-]+)", content_type)
                    charset = charset_match.group(1) if charset_match else "utf-8"
                    try:
                        html = b"".join(chunks).decode(charset, errors="replace")
                    except LookupError:
                        html = b"".join(chunks).decode("utf-8", errors="replace")

                    return html, str(response.url)

            except httpx.TimeoutException as exc:
                raise FetchTimeoutError("Timed out while fetching the website") from exc
            except httpx.RequestError as exc:
                raise FetchConnectionError("Could not connect to the website") from exc

        raise TooManyRedirectsError(
            f"Website redirected more than {settings.max_redirects} times"
        )
    finally:
        if owns_client:
            await http.aclose()


# ---------------------------------------------------------------------------
# T06 - extraction and cleaning
# ---------------------------------------------------------------------------
def _meta_content(soup: BeautifulSoup, *selectors: dict[str, str]) -> str:
    for tag in soup.find_all("meta"):
        for selector in selectors:
            if all(tag.get(key, "").strip().lower() == value.lower() for key, value in selector.items()):
                content = tag.get("content", "")
                if content:
                    return str(content).strip()
    return ""


def _clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip()


def _deduplicate(lines: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for line in lines:
        cleaned = _clean_line(line)
        if len(cleaned) < 3:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def _truncate(text: str, token_cap: int) -> tuple[str, int]:
    estimated = max(1, len(text) // 4)
    if estimated <= token_cap:
        return text, estimated

    kept: list[str] = []
    total = 0
    for line in text.splitlines():
        line_tokens = max(1, len(line) // 4)
        if total + line_tokens > token_cap:
            break
        kept.append(line)
        total += line_tokens
    return "\n".join(kept) + "\n[content truncated]", total


def _structured_hints(soup: BeautifulSoup) -> list[str]:
    hints: list[str] = []
    for script in soup.find_all("script"):
        script_type = str(script.get("type", "")).lower()
        if "ld+json" not in script_type:
            continue
        try:
            payload = json.loads(script.string or script.get_text() or "")
        except (ValueError, TypeError):
            continue
        items = payload if isinstance(payload, list) else [payload]
        for item in items:
            if not isinstance(item, dict):
                continue
            kind = item.get("@type", "")
            name = item.get("name", "")
            hint = f"{kind}: {name}".strip(": ").strip()
            if hint:
                hints.append(hint)
    return _deduplicate(hints)[:10]


def _main_content(soup: BeautifulSoup) -> Any:
    candidates = [soup.find("main"), soup.find("article"), soup.find(attrs={"role": "main"})]
    for found in candidates:
        if found and len(found.get_text(" ", strip=True)) > 120:
            return found

    candidates = [
        node
        for node in soup.find_all(["div", "section"])
        if len(node.get_text(" ", strip=True)) > 200
    ]
    if candidates:
        return max(candidates, key=lambda node: len(node.get_text(" ", strip=True)))
    return soup.body or soup


def extract_page_data(html: str, final_url: str, settings: Settings) -> PageData:
    """Parse HTML into compact, grounded content suitable for the LLM."""
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup.find_all(["script", "style", "noscript", "iframe", "svg", "canvas", "form"]):
        tag.decompose()
    for tag in list(soup.find_all(True)):
        attributes = " ".join(
            [
                " ".join(tag.get("class", []) if isinstance(tag.get("class", []), list) else []),
                str(tag.get("id", "")),
                str(tag.get("role", "")),
            ]
        )
        if NOISE_PATTERN.search(attributes):
            tag.decompose()

    title = _clean_line(soup.title.get_text(" ", strip=True)) if soup.title else ""
    meta_description = _meta_content(soup, {"name": "description"})
    canonical_tag = soup.find("link", rel=lambda value: value and "canonical" in value)
    canonical_url = str(canonical_tag.get("href", "")).strip() if canonical_tag else ""
    og_title = _meta_content(soup, {"property": "og:title"}, {"name": "og:title"})
    og_description = _meta_content(
        soup, {"property": "og:description"}, {"name": "og:description"}
    )

    headings = _deduplicate(
        [heading.get_text(" ", strip=True) for heading in soup.find_all(["h1", "h2", "h3"])]
    )[:40]

    structured_data = _structured_hints(soup)

    main = _main_content(soup)
    for break_tag in main.find_all("br"):
        break_tag.replace_with("\n")
    raw_text = main.get_text(separator="\n", strip=True)
    body_lines = _deduplicate(raw_text.splitlines())

    # Headings carry the most signal, so place them first before truncation.
    combined = _deduplicate(headings + body_lines)
    cleaned_text = "\n".join(combined)
    cleaned_text, token_estimate = _truncate(cleaned_text, settings.max_content_tokens)

    if token_estimate < 20 or not cleaned_text.strip():
        raise NoAnalysableContentError(
            "The website did not contain enough readable text to analyse"
        )

    flags = {
        "has_title": bool(title),
        "has_meta_description": bool(meta_description),
        "has_headings": bool(headings),
        "has_body": bool(body_lines),
        "service_terms_found": bool(SERVICE_PATTERN.search(cleaned_text)),
        "competitor_terms_found": bool(COMPETITOR_PATTERN.search(cleaned_text)),
        "location_terms_found": bool(LOCATION_PATTERN.search(cleaned_text)),
    }

    host = urlsplit(final_url).netloc
    if not title:
        title = host

    return PageData(
        final_url=final_url,
        title=title,
        meta_description=meta_description or "Not specified on site",
        canonical_url=canonical_url or final_url,
        og_title=og_title,
        og_description=og_description,
        headings=headings,
        text=cleaned_text,
        structured_data=structured_data,
        token_estimate=token_estimate,
        flags=flags,
    )
