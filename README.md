# AI-Powered Website Link Analysis API

> **Submission README** — Python Practical Test (FastAPI + LLM)
> Source brief: `link-analysis.md` · Maximum duration: 2 hours · Submission: public GitHub repository + deployed live demo

| Details | Information |
|---|---|
| **Technology** | Python 3.x, FastAPI, Uvicorn, Pydantic, HTTPX, BeautifulSoup |
| **AI Integration** | Google Gemini 2.5 Flash-Lite (primary) · OpenAI GPT-5 mini (fallback) |
| **Endpoint** | `POST http://localhost:4000/link-analysis` |
| **API Documentation** | `http://localhost:4000/docs` |
| **Submission** | Public GitHub Repository + live deployed endpoint |

---

## 1. Summary

This application accepts a website URL, fetches and cleans the page content, sends the cleaned content to a Large Language Model (LLM), and returns a structured JSON analysis in five sections. The goal is to turn any business website into actionable **competitor, search-query, SEO, service, and audience intelligence** without inventing data.

The service is a single-endpoint FastAPI application. It validates the URL (including SSRF protection), fetches the HTML with strict timeouts, extracts only meaningful text and metadata, builds a focused prompt, asks the LLM for schema-conformant JSON, validates that response, and returns it to the caller. Failures are handled gracefully with clear HTTP error responses.

The repository also documents an independent LLM platform comparison (cost, speed, accuracy, context window, JSON reliability) and a final model recommendation with per-analysis cost estimates.

---

## 2. What the API returns

| # | Section | Purpose |
|---|---|---|
| 1 | Competitor vs Your Brand Details | Brand overview, category, products/services, at least 3 reliable competitors, their strengths/gaps, your advantages, and positioning opportunities. |
| 2 | Top 5 Target Search Queries | Five queries mapped to Google, Facebook, Instagram, LinkedIn and X, each with intent, relevance and audience. No invented search volumes. |
| 3 | SEO Improvement | Primary/secondary/long-tail keywords, recommended SEO title, meta description, and supporting content ideas. |
| 4 | Top 5 Services | The five most important services with description, target industry, target customer and main benefit. Inferred items are clearly labelled. |
| 5 | Target Audience Identification | Primary/secondary audiences, industry segments, business types, customer profiles, geography, needs/challenges, interests, and marketing segments. |

Every insight must be grounded in the submitted website. Anything not directly found on the page is labelled as an AI-generated suggestion.

---

## 3. Features

- Single, well-documented REST endpoint on port **4000**
- URL validation and **SSRF protection** (blocks localhost, private/Loopback/link-local ranges, non-HTTP(S) schemes)
- Robust fetching: timeouts, redirects, custom user agent, status-code checks, size limits
- Content extraction from title, meta tags, headings, body text, canonical links and structured data
- Cleaning pipeline: removes scripts/styles/navigation noise, collapses duplicates, truncates to a token budget
- LLM integration with **structured JSON output** and Pydantic validation
- Retry and fallback model strategy for reliability
- Optional in-memory **cache** keyed by URL + content fingerprint to reduce cost
- Consistent error handling and human-readable messages
- Ready for deployment on any ASGI host (Render, Railway, Fly.io, Cloud Run, etc.)

---

## 4. Tech stack

| Layer | Choice |
|---|---|
| API framework | FastAPI |
| Server | Uvicorn |
| Data validation | Pydantic v2 |
| HTTP client | HTTPX (or Requests) |
| HTML parsing | BeautifulSoup4 (or equivalent) |
| LLM client | Provider REST APIs via HTTPX (Gemini, OpenAI, Anthropic) — no vendor SDK required |
| Configuration | Environment variables via `pydantic-settings` and `.env` |
| Tests | Pytest + FastAPI TestClient |

---

## 5. Project structure

```text
ai-link-analysis/
│
├── app/
│   ├── main.py                 # FastAPI app, routes, exception handlers
│   ├── config.py               # Settings loaded from environment
│   ├── schemas.py              # Request/response Pydantic models
│   │
│   ├── services/
│   │   ├── website_extractor.py  # Fetch + HTML extraction + cleaning
│   │   ├── llm_service.py        # LLM client, prompts, JSON parsing, retry
│   │   ├── analysis_service.py   # Orchestration of all five sections
│   │   └── competitor_service.py # Competitor-specific prompt/validation
│   │
│   └── utils/
│       └── validators.py       # URL validation + SSRF checks
│
├── tests/
│   └── test_link_analysis.py
│
├── .env.example                # Safe placeholder variables, no secrets
├── requirements.txt
└── README.md                   # This file
```

A deeper, task-by-task build plan is maintained in **`IMPLEMENTATION_GUIDE.md`**.

---

## 6. Setup and execution

### 6.1 Prerequisites

1. Python 3.10 or newer installed and available on the command line.
2. A Gemini API key (Google AI Studio) and/or an OpenAI API key for the fallback model.
3. Git and a GitHub account for the public submission repository.
4. Optional: an account on a hosting platform for the required live demo.

### 6.2 Local setup

1. Create the project folder described in Section 5 and initialise it as a Git repository.
2. Create and activate a Python virtual environment (`venv`) inside the folder.
3. Install the dependencies listed in `requirements.txt` into that virtual environment.
4. Copy `.env.example` to `.env` and fill in your API key(s).
5. Confirm the `.gitignore` file excludes `.env`, virtual-environment folders, caches and compiled files.
6. Run a quick import check to confirm the app module loads without errors.

### 6.3 Environment variables

| Variable | Purpose | Default / example |
|---|---|---|
| `LLM_PROVIDER` | Primary provider selector | `gemini` |
| `GEMINI_API_KEY` | Google AI Studio key | `<your-key>` |
| `GEMINI_MODEL` | Primary model id | `gemini-2.5-flash-lite` |
| `OPENAI_API_KEY` | First fallback provider key | `<your-key>` |
| `FALLBACK_PROVIDER` | First fallback provider | `openai` |
| `FALLBACK_MODEL` | OpenAI provider model id | `gpt-5-mini` |
| `ANTHROPIC_API_KEY` | Second fallback provider key | `<your-key>` |
| `ANTHROPIC_MODEL` | Anthropic provider model id | `claude-haiku-4-5` |
| `REQUEST_TIMEOUT_SECONDS` | Website fetch timeout | `10` |
| `LLM_TIMEOUT_SECONDS` | LLM call timeout | `45` |
| `MAX_FETCH_BYTES` | Maximum downloaded HTML size | `5000000` |
| `MAX_CONTENT_TOKENS` | Cleaned content cap sent to the LLM | `15000` |
| `MAX_URL_LENGTH` / `MAX_REDIRECTS` | URL length and redirect limits | `2048` / `5` |
| `TEMPERATURE` / `MAX_OUTPUT_TOKENS` | Generation controls | `0.2` / `4000` |
| `MAX_RETRIES` | Retries per provider before falling back | `1` |
| `CACHE_TTL_SECONDS` | Cache lifetime per analysed page | `3600` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |

Never commit real keys. Only commit `.env.example` with placeholders. If no key is configured the app still starts, but `/link-analysis` returns HTTP 503 with `llm_not_configured`.

### 6.4 Run the server

1. From the project root, with the virtual environment active, start Uvicorn pointing at `app.main:app`.
2. Bind host `0.0.0.0` and port `4000` so it matches the required endpoint.
3. Open the interactive documentation at `http://localhost:4000/docs` and confirm the `/link-analysis` route is listed.

The exact command: `uvicorn app.main:app --host 0.0.0.0 --port 4000`

### 6.5 Verify

1. Send the sample request in Section 7.2 from the docs UI or an API client.
2. Confirm the response has `success: true`, the submitted `website`, and all five analysis keys.
3. Send an invalid URL and a blocked private URL to confirm graceful error responses.

---

## 7. API usage

### 7.1 Endpoint

`POST http://localhost:4000/link-analysis`

Request body: a JSON object with a single `url` string.

### 7.2 Sample request

```json
{
  "url": "https://example.com"
}
```

### 7.3 Sample response

```json
{
  "success": true,
  "website": "https://example.com",
  "brand": {
    "name": "ABC Technologies",
    "category": "Technology Services",
    "summary": "A technology company providing digital solutions to small and mid-sized businesses."
  },
  "analysis": {
    "competitor_analysis": {
      "brand_name": "ABC Technologies",
      "brand_category": "Technology Services",
      "brand_summary": "A technology company providing digital solutions to small businesses.",
      "brand_overview": "Your brand overview based on the submitted page",
      "competitors": [
        {
          "name": "XYZ Technologies",
          "main_service": "Web Development",
          "target_market": "Enterprise",
          "strengths": ["Established brand", "Broad enterprise client base"],
          "weaknesses": ["Higher pricing", "Slow delivery cycles"],
          "source": "ai_suggestion"
        }
      ],
      "strengths": ["Affordable solutions"],
      "weaknesses": ["Limited brand awareness"],
      "your_advantages": ["Affordable solutions", "Faster turnaround"],
      "opportunities": ["Improve online visibility", "Publish customer case studies"]
    },
    "target_search_queries": [
      {
        "query": "Best web development company",
        "platform": "Google",
        "intent": "Service Search",
        "business_relevance": "Directly matches the core service",
        "target_audience": "Business owners seeking a vendor"
      }
    ],
    "seo_improvements": {
      "primary_keyword": "web development company",
      "secondary_keywords": ["website development services", "custom web solutions"],
      "long_tail_keywords": ["affordable web development for startups"],
      "recommended_title": "Web Development Company | Affordable Custom Solutions",
      "meta_description": "Professional web development services for startups and growing businesses.",
      "supporting_content": ["Service landing pages", "FAQ page", "Industry-specific pages"]
    },
    "top_services": [
      {
        "service_name": "Web Development",
        "description": "Design and build responsive business websites",
        "target_industry": "Technology Services",
        "target_customer": "Small businesses",
        "main_benefit": "Establishes a professional online presence",
        "source": "website_content"
      }
    ],
    "target_audience": {
      "primary_audience": ["Small business owners"],
      "secondary_audience": ["Startups"],
      "industries": ["Technology", "Retail"],
      "business_types": ["SMB", "Startup"],
      "customer_profiles": ["Owner seeking growth"],
      "location": "Not specified on site",
      "customer_needs": ["Affordable digital presence"],
      "interests": ["Website design", "Online visibility"],
      "recommended_segments": ["Local service businesses", "Early-stage startups"]
    }
  }
}
```

> The example above is illustrative and shortened. Real responses must contain five queries, five services, at least three competitors where reliable information exists, and fully populated fields.

### 7.4 Error responses

| Situation | HTTP status | Behaviour |
|---|---|---|
| Missing or malformed `url` | 422 | Pydantic validation error from FastAPI |
| Invalid URL format or disallowed scheme | 400 | Clear message explaining the URL problem |
| Private/internal address (SSRF) | 400 | Request rejected before any network call |
| Website unreachable, timeout, 4xx/5xx | 502 | Graceful message; no partial analysis returned |
| LLM provider failure after retries | 503 | Message indicating analysis is temporarily unavailable |
| LLM response fails schema validation | 503 | Fallback model attempted first, then a clear error |

---

## 8. Testing

1. Run the suite from the project root: `python -m pytest -q`. The current suite has 18 passing tests.
2. Coverage includes: valid URL happy path, invalid URL, private IP rejection, redirect-to-private rejection, fetch timeout, no-content pages, LLM failure mapping, cache reuse, and response schema completeness.
3. No real API keys or network calls are required — external clients are mocked.
4. Capture a short log or screenshot of a successful request and the `/docs` page for the submission.

---

## 9. LLM platform comparison and final recommendation

> Prices below are **list prices per 1 million tokens checked in November 2026**. They are estimates for planning and must be re-verified against each provider's official pricing page before final submission. Response times and accuracy ratings are **estimates**, not measured benchmarks.

### 9.1 Comparison table

| Provider | Model | Input $/1M | Output $/1M | Cached input $/1M | Context window | Structured JSON support | Est. speed | Est. accuracy for this task | Recommendation |
|---|---|---:|---:|---:|---|---|---|---|---|
| Google | Gemini 2.5 Flash-Lite | $0.10 | $0.40 | $0.01 | 1,048,576 | Native JSON mode / schema output | Very fast (~1–3 s) | Good extraction, adequate insight | **Primary choice** |
| Google | Gemini 2.5 Flash | $0.30 | $2.50 | $0.03 | 1,048,576 | Native JSON mode / schema output | Fast (~2–5 s) | Better reasoning | Strong upgrade option |
| OpenAI | GPT-5 mini | $0.25 | $2.00 | $0.025 | Large (~400k*) | Strict Structured Outputs | Moderate (~3–6 s) | Strong reasoning | **Fallback choice** |
| OpenAI | GPT-4.1 mini | $0.40 | $1.60 | $0.10 | ~1,047,576* | Strict Structured Outputs | Fast (~2–5 s) | Strong | Alternative with 1M context |
| Anthropic | Claude Haiku 5.5 | $0.10 | $0.50 | — | 200,000* | JSON via tool use / prompting | Moderate (~2–5 s) | Good | Viable second fallback |

\* Context figures marked with an asterisk should be confirmed in the provider's current model documentation.

### 9.2 Best model selection

Selection is based on the brief's six criteria:

1. **Accuracy in understanding website content** — Gemini 2.5 Flash-Lite is adequate for extraction and keyword/service identification; the versioned Gemini family follows the same instruction-following conventions as larger Flash models.
2. **Response speed** — Flash-Lite is optimised for low latency, which matters because the API is interactive.
3. **Low API cost** — it is the cheapest option among the compared models with a 1M-token context.
4. **Reliable structured JSON generation** — Gemini supports JSON response configuration and schema-constrained output; Pydantic validation is still applied on our side.
5. **Relevant competitor and SEO insight** — quality is sufficient when the prompt includes explicit field definitions and grounding rules.
6. **Large content handling** — the ~1M token context lets the full cleaned page fit in a single call, avoiding chunking and repeated calls.

### 9.3 Cost optimization

1. Strip HTML, scripts, styles, cookies banners, navigation and duplicate boilerplate before sending content.
2. Send only the meaningful text blocks: title, meta description, headings, main body, and product/service sections.
3. Deduplicate repeated sentences and truncate to the configured token cap (default 15,000 tokens).
4. Keep the system prompt short but explicit; put field rules in the schema rather than long prose.
5. Use one LLM call for all five sections instead of five separate calls.
6. Route simple extraction work (if split) to the cheaper model and reserve stronger models for insight synthesis.
7. Cache results by URL + content fingerprint so an unchanged page is not re-analysed.
8. Retry at most once with the primary model, then fall back; avoid unbounded retry loops.
9. Log token usage per request and alert on anomalous growth.

### 9.4 Final LLM recommendation

| Item | Recommendation |
|---|---|
| Provider | Google |
| Model | `gemini-2.5-flash-lite` |
| Estimated input tokens per analysis | ~12,000 (cleaned page ~9,000 + prompt ~3,000) |
| Estimated output tokens per analysis | ~3,500 (five populated sections) |
| Estimated API cost per analysis | ~$0.0026 (12k × $0.10/M + 3.5k × $0.40/M) |
| Expected response time | ~2–4 s end-to-end estimate (fetch + LLM) |
| Reason for selection | Lowest cost, very large context, fast, native structured JSON, adequate insight quality for this use case |
| Alternative / fallback | OpenAI `gpt-5-mini` (~$0.010 per analysis) on schema failure or provider error |
| Second fallback | Anthropic `claude-haiku-5.5` if both primary and first fallback are unavailable |
| Balancing approach | Clean + cap content, single call, schema validation, one retry, then fallback, with caching to avoid repeat spend |

---

## 10. Security

- API keys are read only from environment variables and never logged or returned.
- `.env` is git-ignored; only `.env.example` is committed.
- URL validation rejects non-HTTP(S) schemes and resolves hostnames to block private, loopback, link-local and reserved IP ranges before fetching (SSRF protection).
- Fetch size and timeouts are bounded to prevent resource exhaustion.
- Error messages are informative but do not leak provider credentials or internal stack traces.

---

## 11. Deployment

1. Push the finished repository to GitHub and set it to **Public**.
2. Deploy the FastAPI app to a publicly accessible ASGI host.
3. Set all environment variables in the hosting dashboard (never in source files).
4. Confirm the live endpoint `POST /link-analysis` returns structured JSON for a sample URL.
5. Record the following links for submission:

| Requirement | Value |
|---|---|
| Live Demo | `<your-domain>` |
| API Endpoint | `<your-domain>/link-analysis` |
| API Documentation | `<your-domain>/docs` |

---

## 12. Submission checklist

- [ ] Complete Python source code uploaded to GitHub
- [ ] Repository is **Public**
- [ ] `README.md` includes setup and execution instructions
- [ ] `README.md` includes sample API request and response
- [ ] Screenshots or logs demonstrating the implementation are included
- [ ] LLM comparison and final recommendation are included
- [ ] No API keys, passwords or credentials committed
- [ ] `.env.example` present with placeholder values
- [ ] Tests included and passing
- [ ] Application deployed with a working live demo URL
- [ ] `/docs` link shared for testing
- [ ] Verified follow of Dxora Technologies on LinkedIn and CREST on Instagram
- [ ] LinkedIn and Instagram profile links prepared for verification

---

## 13. Final submission email

**To:** hr@chivoxai.com
**Subject:** `<Your Name> - Python Practical Link Analysis test review`

**Body:**

1. Full Name
2. Demo Link
3. Public GitHub Repository Link
4. Contact Number
5. Current Location
6. Preferred Date and Time for Final Discussion

---

## 14. Verification steps

1. Follow Dxora Technologies on LinkedIn: https://www.linkedin.com/company/dxora-technologies
2. Follow CREST on Instagram: https://www.instagram.com/crestspot/
3. Share your own LinkedIn and Instagram profile links in the final email.

---

## 15. Reference

All requirements are taken from `link-analysis.md`, including the five analysis sections, technical requirements, evaluation criteria (100 marks), LLM research expectations, submission instructions and panel interview topics. See `IMPLEMENTATION_GUIDE.md` for the complete task-by-task build plan.
