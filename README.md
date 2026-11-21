# AI-Powered Website Link Analysis API

FastAPI service that analyzes a public website URL and returns structured business intelligence across competitor, search-query, SEO, service, and target-audience insights. The analysis is grounded in extracted website content and validated against a strict JSON schema.

## Quick Links

| Resource | Link |
|---|---|
| Live Demo | https://ai-link-analysis-l0mt.onrender.com |
| API Documentation (Swagger UI) | https://ai-link-analysis-l0mt.onrender.com/docs |
| API Endpoint | `POST https://ai-link-analysis-l0mt.onrender.com/link-analysis` |
| Public GitHub Repository | https://github.com/palak-chainani/ai-link-analysis |
| Implementation Evidence Log | [docs/demo-log.txt](docs/demo-log.txt) |

## Overview

The API accepts a website URL, fetches and cleans the page content, sends the cleaned content to an LLM, and returns a structured JSON response with five analysis sections. The service is designed to avoid invented metrics and to clearly label AI-suggested items where page content does not explicitly provide them.

### What the API returns

| Section | Purpose |
|---|---|
| `competitor_analysis` | Brand overview, category, products/services context, competitors, strengths, weaknesses, advantages, and opportunities. |
| `target_search_queries` | 5 platform-specific search queries (Google, Facebook, Instagram, LinkedIn, X) with intent, relevance, and target audience. |
| `seo_improvements` | Primary/secondary/long-tail keywords, recommended title, meta description, and supporting content ideas. |
| `top_services` | Top 5 services with description, target industry, target customer, main benefit, and source label. |
| `target_audience` | Primary/secondary audiences, industries, business types, customer profiles, location, needs, interests, and segments. |

## Features

- **Single analysis endpoint:** `POST /link-analysis`
- **URL validation & SSRF protection:** rejects invalid schemes and blocks localhost/private/link-local/reserved addresses before fetching.
- **Robust website extraction:** fetches HTML with timeout/size/redirect limits and extracts meaningful text from title, meta, headings, body, canonical, and structured data hints.
- **Content cleaning & token budgeting:** removes noisy content, deduplicates, and caps extracted content before sending to the LLM.
- **Structured LLM output:** prompts the model for schema-conformant JSON; response is parsed and validated with Pydantic.
- **Provider fallback/retry:** configurable primary/fallback LLM providers with retry handling for transient/provider/schema failures.
- **Caching:** in-memory cache keyed by final URL + content fingerprint to reduce repeated LLM cost.
- **Clear error handling:** returns meaningful 400/422/502/503 errors for validation, fetch, and LLM failures.
- **Interactive docs:** FastAPI Swagger UI available at `/docs`.

## Tech Stack

| Layer | Technology |
|---|---|
| API framework | FastAPI |
| Server | Uvicorn |
| Validation | Pydantic v2 / pydantic-settings |
| HTTP client | HTTPX |
| HTML parsing | BeautifulSoup4 |
| LLM integration | Provider REST APIs via HTTPX (Gemini primary, OpenAI/Anthropic fallback support) |
| Testing | Pytest |

## Project Structure

```text
.
├── app/
│   ├── main.py                     # FastAPI app, routes, exception handlers
│   ├── config.py                   # Environment-based settings
│   ├── schemas.py                  # Request/response and LLM schema models
│   ├── services/
│   │   ├── analysis_service.py     # End-to-end orchestration + cache
│   │   ├── website_extractor.py    # Fetch, SSRF-safe flow integration, extraction/cleaning
│   │   ├── llm_service.py          # Prompting, provider calls, parsing, validation, retries
│   │   └── competitor_service.py   # Competitor/brand grounding rules
│   └── utils/
│       └── validators.py           # URL validation and SSRF checks
├── docs/
│   └── demo-log.txt                # Sanitized implementation evidence/logs
├── tests/
│   └── test_link_analysis.py
├── .env.example                    # Placeholder environment variables (no secrets)
├── requirements.txt
└── README.md
```

## Setup and Execution

### Prerequisites

- Python 3.10+ (project tested with Python 3.x; deployed on Render)
- Git
- A Gemini API key (recommended primary provider). OpenAI/Anthropic keys are optional fallbacks.

### 1. Clone and enter the project

```bash
git clone https://github.com/palak-chainani/ai-link-analysis.git
cd ai-link-analysis
```

### 2. Create and activate a virtual environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy the example file and fill in your values:

```powershell
Copy-Item .env.example .env
```

```bash
# macOS/Linux
cp .env.example .env
```

Edit `.env` and set at least:

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your-gemini-api-key-here
GEMINI_MODEL=gemini-3.5-flash-lite
```

> **Important:** Never commit `.env` or real API keys. Only `.env.example` with placeholders should be committed.

#### Key environment variables

| Variable | Purpose | Default / Example |
|---|---|---|
| `LLM_PROVIDER` | Primary LLM provider | `gemini` |
| `GEMINI_API_KEY` | Gemini API key | placeholder in `.env.example` |
| `GEMINI_MODEL` | Gemini model ID | `gemini-3.5-flash-lite` |
| `OPENAI_API_KEY` | OpenAI fallback key (optional) | placeholder |
| `FALLBACK_PROVIDER` | Fallback provider | `openai` |
| `FALLBACK_MODEL` | OpenAI fallback model | `gpt-5-mini` |
| `ANTHROPIC_API_KEY` | Anthropic fallback key (optional) | placeholder |
| `ANTHROPIC_MODEL` | Anthropic model ID | `claude-haiku-4-5` |
| `REQUEST_TIMEOUT_SECONDS` | Website fetch timeout | `10` |
| `LLM_TIMEOUT_SECONDS` | LLM request timeout | `45` |
| `MAX_FETCH_BYTES` | Max HTML bytes fetched | `5000000` |
| `MAX_CONTENT_TOKENS` | Max extracted content budget | `15000` |
| `TEMPERATURE` | LLM generation temperature | `0.2` |
| `MAX_OUTPUT_TOKENS` | LLM output token cap | `4000` |
| `MAX_RETRIES` | Retries per provider | `1` |
| `CACHE_TTL_SECONDS` | Cache TTL | `3600` |
| `LOG_LEVEL` | Logging level | `INFO` |

### 5. Run the API locally

```bash
uvicorn app.main:app --host 0.0.0.0 --port 4000 --reload
```

The server will start at `http://localhost:4000`.

- Swagger UI: `http://localhost:4000/docs`
- Health check: `http://localhost:4000/health`

## API Usage

### Endpoint

`POST /link-analysis`

### Request body

```json
{
  "url": "https://www.zoho.com"
}
```

### cURL example

```bash
curl -X POST "http://localhost:4000/link-analysis" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.zoho.com"}'
```

**PowerShell:**
```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:4000/link-analysis" -ContentType "application/json" -Body '{"url":"https://www.zoho.com"}' | ConvertTo-Json -Depth 20
```

### Sample response (trimmed example)

```json
{
  "success": true,
  "website": "https://www.zoho.com/",
  "brand": {
    "name": "Zoho",
    "category": "Cloud Software Suite",
    "summary": "Zoho offers an end-to-end cloud software suite with 50+ applications covering sales, marketing, finance, HR, and more for businesses of all sizes."
  },
  "analysis": {
    "competitor_analysis": {
      "brand_name": "Zoho",
      "brand_category": "Cloud Software Suite",
      "competitors": [
        {
          "name": "Microsoft",
          "main_service": "Cloud Productivity and Office Suite",
          "target_market": "Global enterprises and small businesses",
          "strengths": ["Widespread market adoption"],
          "weaknesses": ["Complex pricing tiers"],
          "source": "ai_suggestion"
        }
      ],
      "strengths": ["Unified platform with 50+ applications"],
      "weaknesses": ["High feature volume might require onboarding guidance for new users"],
      "your_advantages": ["Privacy-focused approach with no ad-based revenue models"],
      "opportunities": ["Expand messaging on enterprise scalability"]
    },
    "target_search_queries": [
      {
        "query": "best cloud software suite for business",
        "platform": "Google",
        "intent": "Service Search",
        "business_relevance": "Captures high-intent users looking for comprehensive business software solutions.",
        "target_audience": "Business owners and IT decision makers"
      }
    ],
    "seo_improvements": {
      "primary_keyword": "cloud software suite",
      "secondary_keywords": ["business software", "unified platform"],
      "long_tail_keywords": ["all in one cloud software suite for businesses"],
      "recommended_title": "Zoho | Cloud Software Suite for Businesses",
      "meta_description": "A unique and powerful software suite for businesses.",
      "supporting_content": ["Customer Stories", "Enterprise Solutions"]
    },
    "top_services": [
      {
        "service_name": "Zoho One",
        "description": "Unified platform with 50+ applications for business operations.",
        "target_industry": "All Industries",
        "target_customer": "Startups, mid-sized companies, and enterprises",
        "main_benefit": "Runs the entire business on a single platform.",
        "source": "website_content"
      }
    ],
    "target_audience": {
      "primary_audience": ["Startups", "Mid-sized companies", "Enterprises"],
      "secondary_audience": ["Business owners", "CEOs"],
      "industries": ["Sales and Marketing", "Finance", "Human Resources"],
      "business_types": ["Growing organizations", "Global enterprises"],
      "customer_profiles": ["Startup founders", "IT decision makers"],
      "location": "Global with specific regional focus mentioned for India and UAE",
      "customer_needs": ["End-to-end business software coverage", "Data privacy and security"],
      "interests": ["Cloud technology innovation", "Business growth"],
      "recommended_segments": ["Enterprise software buyers", "SME owners seeking all-in-one platforms"]
    }
  }
}
```

> The full live response includes 5 search queries (one per required platform), 5 services, and at least 3 competitors when category context is clear. See [docs/demo-log.txt](docs/demo-log.txt) for a complete sanitized captured response.

### Error responses

| Situation | Status | Typical code/behavior |
|---|---:|---|
| Invalid/malformed URL or blocked private/local address | 400 | URL validation / SSRF protection error |
| No analysable content extracted | 422 | `no_analysable_content` |
| Website fetch failure / timeout / upstream HTTP error | 502 | Fetch-related error |
| LLM not configured / provider failure / invalid LLM output after retries | 503 | LLM configuration or analysis unavailable error |
| Unexpected server error | 500 | Generic internal error (traceback logged server-side) |

## Implementation Evidence (Logs)

Sanitized execution evidence is included in [`docs/demo-log.txt`](docs/demo-log.txt). It contains:

- `python -m pytest -q` result (`18 passed`)
- `GET /health` response
- `GET /docs` verification (Swagger/OpenAPI markers present)
- Successful `POST /link-analysis` request and full sanitized JSON response

### Quick evidence excerpt

```text
## Pytest
Command: python -m pytest -q
..................                                                       [100%]
18 passed in 1.02s

## Health check
Status: 200
{"status":"ok","service":"link-analysis"}

## API docs verification
Status: 200
Contains Swagger/OpenAPI UI markers: True
```

## LLM Platform Comparison and Final Recommendation

> Pricing/context/speed figures below are planning estimates checked against public provider pricing/model documentation in November 2026 and should be re-verified before production procurement decisions. Latency and quality observations are workload-dependent.

### Comparison table

| Provider | Model | Est. Input $/1M | Est. Output $/1M | Context Window | Structured JSON Support | Est. Speed | Fit for this task | Notes |
|---|---|---:|---:|---:|---|---|---|---|
| Google | Gemini 3.5 Flash-Lite | $0.30 | $2.50 | ~1M | Native JSON/schema-oriented output | Fast | **Primary** | Best balance of cost, speed, large context, and reliable structured extraction. |
| Google | Gemini 2.5 Flash | $0.30 | $2.50 | ~1M | Native JSON/schema-oriented output | Fast | Strong upgrade | Better reasoning in some cases; similar cost class. |
| OpenAI | GPT-5 mini | $0.25 | $2.00 | Large (verify current docs) | Strong structured outputs/JSON mode support | Moderate | **Fallback** | Good reasoning and JSON reliability; useful when Gemini fails. |
| OpenAI | GPT-4.1 mini | $0.40 | $1.60 | ~1M (verify) | Strong structured outputs | Fast/Moderate | Alternative | Higher input cost than GPT-5 mini in many cases. |
| Anthropic | Claude Haiku 4.5 | $0.10 | $0.50 | ~200k (verify) | Tool/JSON prompting patterns | Moderate | Second fallback | Very cost-effective, but smaller context and different schema strategy. |

### Final recommendation

| Item | Recommendation |
|---|---|
| **Primary provider/model** | Google Gemini (`gemini-3.5-flash-lite`) |
| **Fallback provider/model** | OpenAI (`gpt-5-mini`) via `FALLBACK_PROVIDER=openai` |
| **Why** | Gemini 3.5 Flash-Lite provides a strong cost/latency/context balance for single-call, schema-validated website analysis. |
| **Estimated token usage per analysis** | ~12,000 input tokens + ~3,500 output tokens (estimate; varies by site size/content) |
| **Estimated cost per analysis** | ~\$0.0124 (12k × $0.30/M + 3.5k × $2.50/M), excluding network/hosting overhead |
| **Expected response time** | ~2–6s typical end-to-end (fetch + LLM), depending on target site and model latency |

### Cost / reliability optimizations used

- Clean and trim HTML before LLM call (remove scripts/styles/nav/noise).
- Cap extracted content (`MAX_CONTENT_TOKENS`) to control prompt size.
- Use **one LLM call** for all five sections.
- Validate response with Pydantic + custom constraints; retry/fallback on invalid output.
- Cache results by URL + content fingerprint (`CACHE_TTL_SECONDS`).
- Configure timeouts/retries via environment variables.

## Testing

Run the test suite from the project root:

```bash
python -m pytest -q
```

Current local evidence: **18 passed** (see [docs/demo-log.txt](docs/demo-log.txt)).

The tests cover key behaviors including URL validation/SSRF protection, fetch/content handling, LLM failure mapping, cache behavior, and response schema completeness using mocked external dependencies (no real API keys required).

## Deployment Notes

The project is deployed as a FastAPI ASGI app (Render). For deployment:

1. Set environment variables in the hosting platform dashboard (do not commit `.env`).
2. Use a start command such as `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
3. Verify `/health`, `/docs`, and `POST /link-analysis` after deploy.
4. After changing env vars on Render, save/redeploy so the running process picks them up.

## Security Notes

- API keys are loaded from environment variables only; never hardcode or log secrets.
- `.env` is ignored by git; `.env.example` contains placeholders only.
- SSRF protections block localhost/private/reserved network targets before fetching.
- Fetch size, redirects, and timeouts are bounded.
- Error responses avoid leaking credentials or internal stack traces.