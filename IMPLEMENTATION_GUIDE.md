# Implementation Guide — AI-Powered Website Link Analysis API

**Purpose:** This is the single source of truth for building the project defined in `link-analysis.md`. Any developer or coding agent can read this file from top to bottom and implement the entire application without guessing requirements. It is written as step-by-step instructions and checklists only — no code snippets — so the implementer decides the exact syntax while this guide fixes the *what*, *why*, *order* and *acceptance criteria*.

**Companion file:** `README.md` is the submission-ready document (summary, setup, sample request/response, LLM comparison, submission checklist). This guide is the internal build plan.

---

## Table of contents

1. [How to use this guide](#1-how-to-use-this-guide)
2. [Scope summary](#2-scope-summary)
3. [Architecture and data flow](#3-architecture-and-data-flow)
4. [Task map and dependencies](#4-task-map-and-dependencies)
5. [T01 — Repository and environment setup](#t01--repository-and-environment-setup)
6. [T02 — Configuration and secrets](#t02--configuration-and-secrets)
7. [T03 — Request and response schemas](#t03--request-and-response-schemas)
8. [T04 — URL validation and SSRF protection](#t04--url-validation-and-ssrf-protection)
9. [T05 — Website fetching](#t05--website-fetching)
10. [T06 — HTML extraction and content cleaning](#t06--html-extraction-and-content-cleaning)
11. [T07 — LLM service, prompts and structured output](#t07--llm-service-prompts-and-structured-output)
12. [T08 — Section 1: Competitor vs Your Brand](#t08--section-1-competitor-vs-your-brand)
13. [T09 — Section 2: Top 5 Target Search Queries](#t09--section-2-top-5-target-search-queries)
14. [T10 — Section 3: SEO Improvement](#t10--section-3-seo-improvement)
15. [T11 — Section 4: Top 5 Services](#t11--section-4-top-5-services)
16. [T12 — Section 5: Target Audience Identification](#t12--section-5-target-audience-identification)
17. [T13 — Analysis orchestration](#t13--analysis-orchestration)
18. [T14 — FastAPI endpoint and error handling](#t14--fastapi-endpoint-and-error-handling)
19. [T15 — Logging, caching and cost control](#t15--logging-caching-and-cost-control)
20. [T16 — Tests](#t16--tests)
21. [T17 — LLM research documentation](#t17--llm-research-documentation)
22. [T18 — Deployment](#t18--deployment)
23. [T19 — Submission and verification](#t19--submission-and-verification)
24. [Definition of done](#24-definition-of-done)
25. [Evaluation criteria mapping](#25-evaluation-criteria-mapping)
26. [Risk register and troubleshooting](#26-risk-register-and-troubleshooting)
27. [Appendix A — Response field dictionary](#appendix-a--response-field-dictionary)
28. [Appendix B — Prompt construction rules](#appendix-b--prompt-construction-rules)

---

## 1. How to use this guide

1. Read Sections 1–4 once before writing any code. They define the whole system.
2. Execute tasks **T01 through T19 in order**. Each task lists its inputs (what must exist first) and outputs (what it produces). Do not start a task until its inputs are ready.
3. For every task, work through the numbered steps, then verify the task checklist before moving on.
4. Use the "Pitfalls" list in each task as a review checklist during your final pass.
5. Keep `README.md` updated as you complete T17–T19; it is the graded submission artifact.
6. If you are an agent resuming partial work, check the Definition of Done in Section 24 and work backwards to find unfinished tasks.

**Conventions used here:**
- **Must** = hard requirement from the brief; failure loses marks or breaks the API.
- **Should** = strong best practice; implement unless there is a clear reason not to.
- **May** = optional enhancement.

---

## 2. Scope summary

### 2.1 The problem

Given one business website URL, produce a structured analysis that helps a marketer understand the brand, its competitors, the searches customers use, SEO gaps, the top services, and the target audience. The analysis must be derived from the actual page content and an LLM, not from generic boilerplate.

### 2.2 The deliverable

| Deliverable | Description |
|---|---|
| One REST endpoint | `POST http://localhost:4000/link-analysis` |
| One request field | `url` (valid http/https website URL) |
| One structured response | `success`, `website`, `brand`, `analysis` with five nested sections |
| Source code | Python package under `app/` with services and utilities |
| Tests | Pytest suite under `tests/` |
| Documentation | `README.md` with setup, samples, LLM research, submission details |
| Public repo | GitHub repository, public, no secrets |
| Live demo | Deployed API with working `/docs` |

### 2.3 Explicit constraints from the brief

1. Use actual website content; do not return generic results unrelated to the submitted site.
2. Use an LLM to understand and analyse the extracted content.
3. Competitor information must be based on credible research **or** clearly marked as AI-generated.
4. Never invent Google or social media search volumes.
5. Handle website access restrictions and API failures gracefully.
6. Protect API keys and credentials.
7. Validate URLs and prevent access to private/internal network addresses (SSRF protection).
8. Return valid, structured JSON.
9. Use current provider pricing for the LLM comparison.
10. Distinguish measured benchmarks from estimates; do not claim maximum accuracy without testing.

### 2.4 Out of scope

1. User accounts, authentication, billing or rate limiting UI.
2. Actual social-media posting or scheduling (despite the parent folder name, the brief is strictly link analysis).
3. Real search-volume/SEO APIs (unless explicitly added as an optional enhancement).
4. Front-end interface beyond the auto-generated FastAPI `/docs`.

---

## 3. Architecture and data flow

### 3.1 Layered structure

| Layer | Files | Responsibility |
|---|---|---|
| Entry point | `app/main.py` | Create FastAPI app, register route, register exception handlers, health check |
| Configuration | `app/config.py` | Load and validate environment variables into a settings object at startup |
| Contracts | `app/schemas.py` | Pydantic models for request, response and every nested section |
| Validation utils | `app/utils/validators.py` | URL syntax validation, DNS resolution, SSRF guard, token estimation helper |
| Extraction | `app/services/website_extractor.py` | Fetch HTML, parse it, clean it, return structured page data |
| LLM | `app/services/llm_service.py` | Build prompts, call provider, parse and repair JSON, retry/fallback |
| Domain | `app/services/competitor_service.py` | Competitor prompt assembly and grounding checks |
| Orchestration | `app/services/analysis_service.py` | Coordinate extract → prompt → LLM → validate → response |

### 3.2 Request lifecycle (happy path)

1. Client posts JSON with `url`.
2. Pydantic validates the request body.
3. Validator checks URL syntax and scheme, resolves hostname, rejects private/reserved addresses.
4. Extractor fetches the page with a bounded timeout and size limit, following redirects.
5. Extractor parses HTML and returns title, meta, headings, main text, canonical URL and detected language.
6. Cleaner removes noise, deduplicates, truncates to the token cap, and records which fields were actually found.
7. Analysis service passes the cleaned content plus the source-grounding flags to the LLM service.
8. LLM service builds one system prompt and one user prompt, requests schema-conformant JSON, and calls the primary provider.
9. The raw LLM string is parsed and validated against the Pydantic response schema.
10. If validation fails, retry once with a corrective prompt; if it still fails, call the fallback provider.
11. Analysis service assembles the final response object with `success: true` and the submitted website.
12. FastAPI serialises it as JSON and returns HTTP 200.

### 3.3 Failure paths

| Failure | Where detected | Result |
|---|---|---|
| Missing/invalid `url` field | Pydantic request validation | HTTP 422 |
| Bad scheme or private IP | Validator | HTTP 400, no network call made |
| Fetch timeout / DNS failure / non-2xx | Extractor | HTTP 502 with descriptive message |
| Empty or non-HTML content | Extractor | HTTP 422/502 with "no analysable content" message |
| Provider timeout / auth error | LLM service | Retry, then fallback, then HTTP 503 |
| Malformed LLM JSON | LLM service | Repair attempt, then fallback, then HTTP 503 |
| Schema validation failure | Analysis service | Same as malformed JSON |

### 3.4 Design principles

1. **Grounding first:** pass explicit "found on page" flags to the LLM so it can label inferred items.
2. **Single LLM call:** produce all five sections in one response to minimise cost and latency.
3. **Fail closed:** never return a partially invented analysis; return a clear error instead.
4. **Bounded resources:** timeouts, content size limits and token caps everywhere.
5. **Observability:** log durations, token counts, provider used and error reasons (never keys or full content).

---

## 4. Task map and dependencies

| Task | Deliverable | Depends on | Brief marks covered |
|---|---|---|---|
| T01 | Repo, virtual env, dependencies | — | Code quality / docs |
| T02 | Config + `.env.example` | T01 | Error handling / docs |
| T03 | Pydantic schemas | T01 | API structure, structured output |
| T04 | URL validator + SSRF guard | T02 | Extraction, security |
| T05 | Website fetcher | T04 | Extraction (15) |
| T06 | Extractor + cleaner | T05 | Extraction (15) |
| T07 | LLM service + prompts | T02, T03 | LLM integration (15) |
| T08 | Competitor section logic | T03, T07 | Competitor analysis (15) |
| T09 | Search query section logic | T03, T07 | Competitor/search (15) |
| T10 | SEO section logic | T03, T07 | SEO (10) |
| T11 | Services section logic | T03, T07 | Services/audience (10) |
| T12 | Audience section logic | T03, T07 | Services/audience (10) |
| T13 | Orchestration service | T06, T08–T12 | All analysis sections |
| T14 | Endpoint + error handlers | T03, T13 | API structure (10) |
| T15 | Logging, cache, cost control | T07, T13 | Cost optimisation (15) |
| T16 | Tests | T14 | Error handling/quality (10) |
| T17 | LLM research in README | T07 | LLM research (15) |
| T18 | Deployment | T14, T16 | Verification |
| T19 | Submission + email | T17, T18 | Submission |

---

## T01 — Repository and environment setup

**Objective:** Create a clean, version-controlled project skeleton that matches the structure in the brief.

**Inputs:** The `link-analysis.md` brief and an empty working folder.

**Outputs:** Project folder tree, Git repository, virtual environment, `requirements.txt`, `.gitignore`.

### Steps

1. Create the folder tree exactly as shown in the brief (Section 7): `app/`, `app/services/`, `app/utils/`, `tests/`, plus root-level `.env.example`, `requirements.txt`, `README.md`.
2. Add empty `__init__.py` files to `app/`, `app/services/` and `app/utils/` so they are importable packages.
3. Initialise Git in the folder and create an initial commit with the skeleton.
4. Create a Python virtual environment inside the project and activate it.
5. Add the runtime dependencies to `requirements.txt`: FastAPI, Uvicorn, Pydantic, HTTPX, BeautifulSoup4, the chosen LLM SDK(s), python-dotenv, and a JSON-schema validator if used.
6. Add development dependencies to a separate section or file: Pytest and HTTPX-based test client support.
7. Install dependencies into the virtual environment and record the versions used.
8. Create `.gitignore` and exclude: `.env`, virtual-environment folders, `__pycache__/`, `*.pyc`, `.pytest_cache/`, IDE folders, coverage files, and any log files.
9. Confirm `git status` shows only intended files as untracked/modified.

### Checklist

- [ ] Folder structure matches the brief
- [ ] All package directories are importable
- [ ] Git initialised with a clean initial commit
- [ ] `requirements.txt` contains pinned or bounded versions
- [ ] Virtual environment works and dependencies install
- [ ] `.gitignore` prevents secrets and caches from being committed

### Pitfalls

- Do not commit the virtual environment.
- Do not name the package `app` if a conflicting installed module causes import issues; keep the brief's structure unless there is a real conflict.
- Do not skip `.gitignore`; secret leakage is an explicit disqualifier.

---

## T02 — Configuration and secrets

**Objective:** Centralise all environment-driven settings so code never hardcodes keys, URLs or limits.

**Inputs:** T01.

**Outputs:** `app/config.py`, `.env.example`, verified `.env` (local only).

### Steps

1. Decide the full settings list: primary provider name, primary model id, primary API key, fallback provider name, fallback model id, fallback API key, request timeout in seconds, maximum fetched bytes, maximum content tokens, cache TTL, retry count, and log level.
2. Implement `config.py` so settings are loaded from environment variables at startup, with safe defaults for non-secret values.
3. Mark API keys as required only when their provider is actually selected; allow the app to start without a fallback key if the fallback is unused.
4. Validate settings at startup: numeric limits must be positive, provider names must be from the supported set, and model ids must be non-empty.
5. Create `.env.example` with every variable name, a short comment, and placeholder values only.
6. Create the local `.env` with real values and confirm it is git-ignored.
7. Add a startup sanity check that logs which provider/model is active without logging the key value.
8. Verify that changing a variable in `.env` changes the loaded setting after restart.

### Checklist

- [ ] No secret literal exists anywhere in tracked source files
- [ ] `.env.example` committed, `.env` ignored
- [ ] Settings validated at startup with clear error messages
- [ ] Provider and model are configurable without code edits

### Pitfalls

- Do not fall back to a hardcoded key when the environment variable is missing; fail fast instead.
- Do not log configuration objects wholesale — they contain keys.
- Keep the port at 4000 via the Uvicorn command, not necessarily as a config value, to match the brief.

---

## T03 — Request and response schemas

**Objective:** Define the exact data contract so the API and the LLM target the same structure.

**Inputs:** T01.

**Outputs:** `app/schemas.py` containing all Pydantic models.

### Steps

1. Create a request model with a single required `url` field of type string; add a maximum length to avoid abuse.
2. Create a top-level response model with fields: `success` (boolean), `website` (string), `brand` (nested object), `analysis` (nested object).
3. Create the `brand` model with `name`, `category`, `summary` — all strings.
4. Create the competitor analysis model containing: `brand_overview` (string), `competitors` (list of objects), `your_advantages` (list of strings), `opportunities` (list of strings), plus a `strengths` and `weaknesses` placeholder at the section level if you follow the brief's example shape.
5. Create the competitor item model with `name`, `main_service`, `target_market`, `strengths` (list), `weaknesses` (list) and `source` (literal such as `website_content` or `ai_suggestion`).
6. Create the search query item model with `query`, `platform`, `intent`, `business_relevance`, `target_audience`. Constrain `platform` to the five supported values: Google, Facebook, Instagram, LinkedIn, X.
7. Create the SEO model with `primary_keyword`, `secondary_keywords`, `long_tail_keywords`, `recommended_title`, `meta_description`, `supporting_content`.
8. Create the service item model with `service_name`, `description`, `target_industry`, `target_customer`, `main_benefit`, `source` (literal marking website-derived vs inferred).
9. Create the audience model with `primary_audience`, `secondary_audience`, `industries`, `business_types`, `customer_profiles`, `location`, `customer_needs`, `interests`, `recommended_segments` (lists of strings except `location`).
10. Create the `analysis` container model with exactly five fields: `competitor_analysis`, `target_search_queries`, `seo_improvements`, `top_services`, `target_audience`.
11. Add field descriptions to every model; these descriptions will be reused in the LLM prompt so the schema and prompt never drift.
12. Add validation constraints: minimum list lengths where the brief requires five queries and five services, and minimum three competitors when reliable data exists (make this a soft rule: validate presence, not forced fabrication).
13. Create a dedicated error response model with `success: false`, `error` code and `detail` message so failures are structured too.
14. Generate a JSON schema from these models and save or print it for reuse in T07.

### Checklist

- [ ] Every field in the brief's example response is represented
- [ ] Platform field is constrained to the five supported platforms
- [ ] `source` fields exist for competitor and service items
- [ ] No field invites a search-volume number
- [ ] Response model can be used directly to validate LLM output

### Pitfalls

- Do not make all fields optional; optional fields let the LLM silently omit required analysis.
- Do not add volume, ranking or traffic fields — the brief forbids invented metrics.
- Keep names stable; renaming a field later requires prompt and test changes.

---

## T04 — URL validation and SSRF protection

**Objective:** Accept only public http/https website URLs and block access to internal infrastructure.

**Inputs:** T02 (settings), T01 (utils folder).

**Outputs:** `app/utils/validators.py` with reusable validation functions and custom exceptions.

### Steps

1. Define a validation function that accepts a raw string and returns a normalised URL or raises a clear validation error.
2. Reject empty strings, strings with leading/trailing whitespace anomalies, and strings exceeding the configured maximum length.
3. Parse the URL and require scheme `http` or `https` only; reject `file`, `ftp`, `gopher`, `data`, `javascript` and scheme-relative URLs.
4. Require a hostname; reject URLs with userinfo, embedded credentials or malformed ports.
5. Reject non-standard ports unless you have a deliberate reason to allow them; document the decision.
6. Resolve the hostname to IP addresses. If resolution fails, raise a validation error.
7. For every resolved address, reject: loopback ranges, private ranges, link-local ranges, reserved/test ranges, unspecified addresses, and IPv4-mapped IPv6 equivalents of those ranges.
8. Reject hostnames that are literal IP addresses belonging to any blocked range (this prevents DNS-rebinding-style bypasses using raw IPs).
9. Reject well-known internal metadata hostnames and any hostname resolving to the cloud metadata endpoint address.
10. Re-validate the resolved address immediately before the actual network request in T05, so a DNS change between validation and fetch cannot bypass the guard (DNS rebinding defence).
11. Return a normalised URL string (scheme lowercased, host lowercased, default ports removed) for downstream use.
12. Define distinct exception types for invalid syntax, disallowed scheme, and blocked address so T14 can map them to HTTP 400 with precise messages.

### Checklist

- [ ] Only http/https accepted
- [ ] Localhost, 127.0.0.0/8, 10/8, 172.16/12, 192.168/16, 169.254/16 and IPv6 loopback/ULA/link-local rejected
- [ ] Literal-IP bypasses handled
- [ ] Re-check performed at fetch time
- [ ] Errors are distinct and descriptive

### Pitfalls

- Do not rely on string checks alone (for example, only blocking "localhost"); use parsed IP ranges.
- Do not let redirects reach internal addresses — apply the same guard to every redirect hop in T05.
- Do not skip IPv6; the brief says private/internal addresses generally.

---

## T05 — Website fetching

**Objective:** Retrieve the target HTML reliably and safely.

**Inputs:** T04 validator and exceptions.

**Outputs:** Fetching functions in `app/services/website_extractor.py` (or a dedicated fetch module) returning raw HTML plus metadata.

### Steps

1. Use an async HTTP client (HTTPX) with a configured total timeout and connect timeout from settings.
2. Send a realistic desktop user-agent string so sites do not immediately block the request.
3. Send an `Accept` header preferring HTML.
4. Disable automatic redirect following and handle redirects manually so each hop passes through the SSRF guard from T04.
5. Cap the number of redirects (for example five) and fail with a clear error if exceeded.
6. Stream the response body and abort if the configured maximum byte size is exceeded.
7. Check the final status code: 2xx proceeds; 3xx handled as redirects; 4xx/5xx raise a "website unavailable" error with the status code included in the message.
8. Validate the content type: require HTML or XHTML. Reject PDFs, images, JSON APIs and downloads with a clear message.
9. Honour charset from the content-type header, falling back to a sensible default, and decode safely.
10. Record the final URL after redirects and the response time for logging.
11. Raise one of a small set of fetch exceptions (timeout, connection error, bad status, bad content type, too large) so T14 can map them consistently.
12. Never retry more than once on transient network errors; respect the brief's time limit and avoid long hangs.

### Checklist

- [ ] Timeouts and size limits enforced
- [ ] Redirects manually followed and re-validated
- [ ] Status, content-type and size errors distinguished
- [ ] Final URL and duration captured for logs

### Pitfalls

- Automatic redirects are the most common SSRF bypass; do not enable them blindly.
- Some sites block generic Python user agents; a realistic UA materially improves success.
- Do not follow redirects to a different scheme such as `file://` — the guard in T04 must run each hop.

---

## T06 — HTML extraction and content cleaning

**Objective:** Convert raw HTML into compact, meaningful, structured text that the LLM can analyse cheaply.

**Inputs:** T05 (raw HTML and final URL).

**Outputs:** A structured "page data" object with cleaned fields and source-grounding flags; cleaning utilities.

### Steps

1. Parse the HTML with BeautifulSoup using a consistent parser.
2. Remove non-content elements entirely before reading text: `script`, `style`, `noscript`, `iframe`, `svg`, `canvas`, `form` controls, and inline event-bearing tags.
3. Remove common chrome: cookie banners, navigation menus, footers, sidebars, newsletter popups, and elements with classes/ids containing noise keywords such as `cookie`, `banner`, `nav`, `footer`, `modal`, `advert`, `sidebar`.
4. Extract and store: document title, meta description, canonical URL, Open Graph title/description, heading hierarchy (h1–h3), and any JSON-LD structured data blocks.
5. Identify the main content region using `<main>`, `<article>`, main content class names, or fallback to the largest text-bearing container; prefer semantic containers over the whole body.
6. Extract visible text from the main region, preserving paragraph and heading boundaries with newline separators.
7. Expand useful link text (for example service names in navigation) only if it appears to describe the business; discard unrelated link lists.
8. Normalise whitespace: collapse repeated spaces and blank lines, trim each line, and drop one-character fragments.
9. Deduplicate repeated blocks — especially repeated service descriptions, testimonials and footer text — using exact and near-duplicate detection.
10. Detect the page language from HTML attributes and record it; do not translate content.
11. Build a token estimate for the cleaned text using a simple word/character heuristic; if it exceeds the configured cap, keep the highest-value sections first (title, meta, h1/h2, main paragraphs) and truncate the remainder with a clear marker.
12. Produce source-grounding flags: `has_title`, `has_meta_description`, `has_headings`, `has_body`, `service_terms_found`, `competitor_terms_found`, `location_terms_found`. These tell the LLM which claims are supported by the page.
13. Return the structured page data object including final URL, extracted fields, cleaned text, token estimate and flags.
14. If the cleaned text is below a minimum useful threshold, raise a "no analysable content" error rather than sending an empty prompt.

### Checklist

- [ ] Scripts, styles and boilerplate removed
- [ ] Title, meta, headings, main text, canonical and JSON-LD captured
- [ ] Duplicates removed and whitespace normalised
- [ ] Token cap enforced with priority ordering
- [ ] Grounding flags produced
- [ ] Empty-content case handled

### Pitfalls

- Do not send raw HTML to the LLM; it wastes tokens and degrades output.
- Do not strip heading text while removing heading tags — preserve the text.
- Do not silently truncate the middle of a service description; truncate at block boundaries.
- Do not translate or rewrite page content before analysis; that introduces hallucination risk.

---

## T07 — LLM service, prompts and structured output

**Objective:** Build a reusable service that reliably turns cleaned page data into schema-valid JSON.

**Inputs:** T02 (settings), T03 (schemas), T06 (page data).

**Outputs:** `app/services/llm_service.py` with prompt builders, provider clients, JSON parsing, validation, retry and fallback.

### Steps

1. Initialise one client per configured provider from settings; keep clients reusable across requests.
2. Create a system prompt that fixes the role ("expert digital marketing and SEO analyst"), the task, the grounding rules, and the output contract.
3. Include the JSON schema (generated in T03) in the system prompt or the provider's native structured-output configuration, whichever the chosen provider supports best.
4. State explicit grounding rules in the prompt: use only page content for factual claims; label inferred items with the `source` field; never output search volumes, rankings or traffic estimates; if data is unavailable, say so in text rather than inventing a number.
5. State the exact section requirements in the prompt: five search queries across the five platforms, five services, at least three competitors where reliable information exists, full SEO fields, and all audience fields.
6. Build the user prompt from the structured page data: final URL, brand name, category hints, title, meta, headings, cleaned text, and the grounding flags. Clearly delimit each part so the model can distinguish source fields from instructions.
7. Request JSON-only output and instruct the model not to wrap the response in explanatory prose or Markdown fences.
8. Set a generation temperature that favours deterministic output (low value) because the task is analytical, not creative.
9. Set a maximum output token limit slightly above the expected size of the five sections to control cost.
10. Call the primary provider and capture the raw text response plus usage/token counts and latency.
11. Strip accidental Markdown code fences and leading/trailing prose, then parse the JSON.
12. Validate the parsed object against the Pydantic response schema from T03.
13. On parse or validation failure, make one corrective retry: tell the model the exact validation error and ask for corrected JSON only.
14. If the retry fails, call the fallback provider with the same prompts and validate again.
15. If all attempts fail, raise a dedicated `AnalysisUnavailable` exception carrying a short reason for logging and HTTP mapping.
16. Log provider used, attempt count, token counts, latency and error reason — never the full prompt or key.
17. Expose a single public function to the orchestrator that accepts page data and returns a validated analysis object.

### Checklist

- [ ] One call produces all five sections
- [ ] Structured JSON schema enforced by provider and by Pydantic
- [ ] Grounding and no-invented-metrics rules present in prompt
- [ ] Retry once, then fallback, then explicit failure
- [ ] Token usage and latency logged
- [ ] No credentials in logs

### Pitfalls

- Do not accept the first parseable JSON blindly; always validate against the schema.
- Do not allow the model to choose its own field names — enforce the T03 schema.
- Do not place the entire raw HTML in the prompt; use T06 output.
- Do not set a high temperature; it increases inconsistency across identical requests.

---

## T08 — Section 1: Competitor vs Your Brand

**Objective:** Produce the brand/competitor comparison grounded in the submitted page.

**Inputs:** T03 schemas, T07 LLM service.

**Outputs:** Competitor-specific prompt fragment and validation rules in `app/services/competitor_service.py`.

### Steps

1. Define the fields this section must fill: brand name, business overview, main category, main products/services, competitors (minimum three where reliable), competitor strengths, competitor weaknesses/gaps, your competitive advantages, and positioning opportunities.
2. Instruct the model to derive the brand name and category from the page title, headings and about text rather than guessing from the domain.
3. Instruct the model to identify competitors only when the page gives enough context (industry, geography, product category); otherwise produce clearly labelled AI suggestions with the `source` field set accordingly.
4. Require at least three competitor entries when the business category is clear, and allow fewer with an explanatory note when it is not — never fabricate named companies with invented facts.
5. Require each competitor to include strengths and weaknesses that are plausible and tied to the business category.
6. Require "your advantages" and "opportunities" to reference actual page signals (for example pricing claims, service breadth, lack of case studies).
7. Add a post-validation check that every competitor item has a non-empty name and at least one strength; reject and retry if not.
8. Map the section to the response model fields from T03 so no manual reshaping is needed later.

### Checklist

- [ ] Brand name and category grounded in page content
- [ ] Three competitors when reliable, labelled when inferred
- [ ] Strengths, weaknesses, advantages and opportunities all populated
- [ ] `source` field used correctly

### Pitfalls

- Do not let the LLM invent market-share numbers or revenue figures.
- Do not present AI-suggested competitors as verified research.
- Do not compare against unrelated global brands when the business is local.

---

## T09 — Section 2: Top 5 Target Search Queries

**Objective:** Generate five realistic search queries mapped to the five required platforms.

**Inputs:** T03 schemas, T07 LLM service.

**Outputs:** Query-section prompt fragment and validation rules.

### Steps

1. State the required count: exactly five query objects.
2. Require the five platforms to be represented as `Google`, `Facebook`, `Instagram`, `LinkedIn`, and `X` — one per query in the brief's example pattern, while allowing a platform to appear more than once only if all five are still covered.
3. For each query require: `query` text, `platform`, `intent`, `business_relevance`, `target_audience`.
4. Define intent vocabulary for consistency: service search, business discovery, inspiration, B2B search, service discovery, local search, product research.
5. Instruct the model to phrase queries the way real customers type them, using the brand's service terms and category from the page.
6. Repeat the rule that no search volume, ranking position or difficulty score may be included anywhere.
7. Add a post-validation check: count is five, every platform value is in the allowed set, and every query string is non-empty.
8. Confirm there is no field in the schema that could hold a fabricated volume number.

### Checklist

- [ ] Exactly five queries
- [ ] All five platforms covered
- [ ] Intent, relevance and audience populated for each
- [ ] No volume or ranking data anywhere

### Pitfalls

- Do not report platform-specific volume unless a real data source is integrated; the brief forbids it.
- Do not make every query identical across platforms; adapt phrasing to platform culture.

---

## T10 — Section 3: SEO Improvement

**Objective:** Produce practical keyword, title, meta and content recommendations.

**Inputs:** T03 schemas, T07 LLM service.

**Outputs:** SEO-section prompt fragment and validation rules.

### Steps

1. Require a `primary_keyword` derived from the brand's main service and category on the page.
2. Require a list of `secondary_keywords` covering related service and industry terms.
3. Require a list of `long_tail_keywords` that reflect specific customer intents (for example affordability, location, industry).
4. Require a `recommended_title` that includes the primary keyword, reads naturally, and stays within a typical title-length limit; instruct the model to keep it human-friendly rather than keyword-stuffed.
5. Require a `meta_description` that is short, human-friendly, includes relevant keywords and summarises the actual business.
6. Require `supporting_content` suggestions drawn from the brief's list: service landing pages, industry-specific pages, FAQs, blog topics, location-based pages and supporting business articles.
7. Instruct the model to justify choices implicitly through keyword relevance to page content, not through invented difficulty or volume numbers.
8. Add a post-validation check that all six fields exist, the keyword lists are non-empty, and the title/description are non-empty strings.

### Checklist

- [ ] All six SEO fields populated
- [ ] Primary keyword appears in the recommended title
- [ ] Meta description is short and business-specific
- [ ] Supporting content includes concrete page ideas
- [ ] No volume or difficulty metrics

### Pitfalls

- Do not generate generic SEO advice unrelated to the site.
- Do not exceed typical title/meta lengths; recommend limits in the prompt.

---

## T11 — Section 4: Top 5 Services

**Objective:** Identify the five most important services from the website.

**Inputs:** T03 schemas, T07 LLM service.

**Outputs:** Services-section prompt fragment and validation rules.

### Steps

1. Require exactly five service objects.
2. For each service require: `service_name`, `description`, `target_industry`, `target_customer`, `main_benefit`, and `source`.
3. Instruct the model to extract services from headings, service lists, navigation labels and body text before inferring any.
4. Require the `source` field to be `website_content` when the service name appears on the page and `ai_suggestion` when inferred from context.
5. When fewer than five services are explicitly listed, require the model to fill the remainder with clearly labelled, category-relevant suggestions rather than repeating the same service.
6. Require descriptions to be short and specific, benefits to explain customer value, and target fields to reflect the page's own audience language.
7. Add a post-validation check: count is five, names are unique, and every item has a valid `source` value.
8. Ensure the final response preserves the `source` labels without stripping them.

### Checklist

- [ ] Five unique services
- [ ] All five fields plus `source` populated
- [ ] Inferred services clearly labelled
- [ ] Names traceable to page content where possible

### Pitfalls

- Do not repeat one service five times with synonyms.
- Do not list company departments (for example "HR") as customer services.
- Do not remove source labels during response shaping — they are an explicit brief requirement.

---

## T12 — Section 5: Target Audience Identification

**Objective:** Identify who the business serves, with enough specificity to be actionable.

**Inputs:** T03 schemas, T07 LLM service.

**Outputs:** Audience-section prompt fragment and validation rules.

### Steps

1. Require all audience fields from the schema: `primary_audience`, `secondary_audience`, `industries`, `business_types`, `customer_profiles`, `location`, `customer_needs`, `interests`, `recommended_segments`.
2. Instruct the model to derive audiences from page language such as "we serve", case studies, testimonials, service descriptions and location mentions.
3. Require primary and secondary audiences to be distinct groups, for example small business owners versus enterprise procurement teams.
4. Require `location` to state the geographical focus found on the page, or explicitly say it is not specified — never guess a city.
5. Require `customer_needs` and `interests` to reflect problems the services solve, not generic demographics.
6. Require `recommended_segments` to be marketing-ready segments that could be used for targeting.
7. Add a post-validation check that all list fields are non-empty and `location` is a string.
8. Confirm the section contains no invented demographic statistics.

### Checklist

- [ ] All nine audience fields present
- [ ] Primary and secondary audiences distinct
- [ ] Location grounded or explicitly unknown
- [ ] Needs and segments actionable

### Pitfalls

- Do not invent age ranges, income brackets or population figures without evidence.
- Do not default to "everyone" as the audience.

---

## T13 — Analysis orchestration

**Objective:** Glue extraction, grounding flags, prompting, validation and response assembly into one service.

**Inputs:** T06 page data, T07 LLM service, T08–T12 section rules, T03 schemas.

**Outputs:** `app/services/analysis_service.py` exposing one function used by the endpoint.

### Steps

1. Accept the validated URL and the extracted page data as inputs.
2. Assemble the full prompt using the section fragments from T08–T12 and the page data from T06.
3. Call the LLM service once to obtain the validated analysis object.
4. Run the section-level post-validation checks from T08–T12 (counts, allowed platform values, unique services, non-empty fields, source labels).
5. If a check fails, trigger the same corrective retry path used in T07 rather than returning bad data.
6. Build the `brand` object from the competitor section's brand fields (name, category, summary) so the top-level response is consistent with the detailed analysis.
7. Build the final response with `success: true`, the normalised website URL, brand and the five-section analysis.
8. Validate the final response against the top-level Pydantic response model.
9. Return the validated model to the endpoint.
10. Keep orchestration free of HTTP concerns — it must be testable without a server.

### Checklist

- [ ] Single orchestration entry point
- [ ] All five sections present in output
- [ ] Top-level brand consistent with detailed analysis
- [ ] Final response validated against schema
- [ ] No direct HTTP framework dependency in this layer

### Pitfalls

- Do not duplicate prompt logic in the endpoint.
- Do not allow section checks to be silently skipped on retry.

---

## T14 — FastAPI endpoint and error handling

**Objective:** Expose the required HTTP API with predictable status codes and messages.

**Inputs:** T03 schemas, T04 exceptions, T05 exceptions, T07 exceptions, T13 orchestration.

**Outputs:** `app/main.py` with the route and exception handlers.

### Steps

1. Create the FastAPI application with a clear title and description so `/docs` is self-explanatory.
2. Register a `POST /link-analysis` route whose request body uses the T03 request model.
3. Inside the route: call the validator, then the extractor, then the orchestration service, then return the validated response model with HTTP 200.
4. Register a health route such as `GET /health` returning a simple status object for deployment monitoring.
5. Add exception handlers that map each custom exception family to the right status: URL/SSRF errors to 400, fetch errors to 502, no-content errors to 422, analysis-unavailable errors to 503.
6. Ensure Pydantic request validation errors keep FastAPI's default 422 response with field-level detail.
7. Add a catch-all handler for unexpected errors that returns a structured 500 without stack traces or sensitive data.
8. Ensure every error body follows the error model from T03 (`success: false`, `error`, `detail`).
9. Confirm the route appears in `/docs` and that the example request body can be submitted from the docs UI.
10. Verify the app starts with Uvicorn on host `0.0.0.0` and port `4000`.

### Checklist

- [ ] Endpoint path and method exactly match the brief
- [ ] Runs on port 4000
- [ ] `/docs` available and accurate
- [ ] All error families mapped to distinct status codes
- [ ] No stack traces or keys in error responses
- [ ] Health route present

### Pitfalls

- Do not catch all exceptions inside the route and return 200 with an error field; use proper HTTP status codes.
- Do not expose internal exception class names if they reveal implementation details unnecessarily.
- Do not forget to re-validate the URL at fetch time (T04/T05).

---

## T15 — Logging, caching and cost control

**Objective:** Make the service observable and economical, satisfying the brief's cost-optimisation requirement.

**Inputs:** T07 LLM service, T13 orchestration.

**Outputs:** Logging configuration and optional cache layer.

### Steps

1. Configure structured logging with timestamp, level, request id, provider, model, duration and token counts.
2. Log one line per pipeline stage: validation, fetch, extraction, LLM attempt, validation result, response.
3. Redact API keys and avoid logging full page text or full prompts.
4. Implement an in-memory cache keyed by a fingerprint of the normalised URL plus a hash of the cleaned content.
5. Give cached entries the configured TTL and cap the cache size to prevent unbounded memory growth.
6. Return cached analysis immediately when the fingerprint matches and the entry is fresh, skipping fetch and LLM entirely.
7. Invalidate on content change because the fingerprint includes cleaned content.
8. Track cumulative token usage and estimated cost per request for later reporting.
9. Add a simple concurrency-safe structure so simultaneous identical requests do not all trigger LLM calls (optional but recommended).
10. Document cache behaviour in the README cost-optimisation section.

### Checklist

- [ ] Stage-level logs present
- [ ] No secrets or full content in logs
- [ ] Cache keyed by URL + content fingerprint
- [ ] TTL and size bounds present
- [ ] Token/cost metrics captured

### Pitfalls

- Do not cache by URL alone; a changed page would return stale analysis.
- Do not let the cache grow without a size cap.
- Do not log the response body by default; it may be large.

---

## T16 — Tests

**Objective:** Prove each layer works and failures are graceful.

**Inputs:** T14 endpoint.

**Outputs:** `tests/test_link_analysis.py` and any supporting fixtures.

### Steps

1. Set up Pytest with a FastAPI TestClient and override external clients with mocks so no real network or paid API calls occur.
2. Create fixtures for representative cleaned page data covering a normal business site, a thin page, and a page with inferred-only content.
3. Test the happy path: valid URL returns 200, `success` is true, all five analysis keys exist, and counts are correct (five queries, five services).
4. Test that platform values are limited to the five allowed platforms.
5. Test that competitor and service `source` labels are present.
6. Test invalid URL formats and disallowed schemes return 400.
7. Test private/loopback addresses and literal internal IPs return 400 without any outgoing request.
8. Test redirect chains that point to private addresses are rejected.
9. Test fetch timeout, bad status, wrong content type and oversized body return the correct errors.
10. Test empty/thin content produces a "no analysable content" error.
11. Test malformed LLM JSON is repaired or falls back, and that total failure returns 503.
12. Test schema validation failure triggers corrective retry and fallback.
13. Test cache hit avoids a second LLM call.
14. Test that no key value appears in logs or responses.
15. Run the full suite and confirm all tests pass before deployment.

### Checklist

- [ ] Happy path and all major failure paths covered
- [ ] External services mocked
- [ ] No real API key needed for tests
- [ ] Tests assert schema completeness, not just status codes
- [ ] Suite passes

### Pitfalls

- Do not write tests that depend on a live website; they will be flaky.
- Do not only test status codes — assert the response structure and required counts.

---

## T17 — LLM research documentation

**Objective:** Fulfil Section 6 of the brief with a credible, honest comparison.

**Inputs:** T07 implementation experience and current provider documentation.

**Outputs:** Sections 9.1–9.4 of `README.md`.

### Steps

1. Compare at least three providers/models using the brief's criteria: provider, model, API cost (input and output), response speed, accuracy, context window, JSON support, recommendation.
2. Use current list prices from official provider pricing pages and record the date checked.
3. Mark any figure that cannot be verified as an estimate rather than a fact.
4. Describe response times as estimates unless you actually measured them; the brief explicitly forbids claiming measured accuracy without benchmarks.
5. Justify the chosen primary model against all six selection criteria in the brief.
6. Provide a cost calculation: estimated input tokens, estimated output tokens, and resulting cost per analysis, showing the arithmetic.
7. Name a fallback model and a second fallback, and state the exact trigger conditions for each.
8. Document all cost-optimisation techniques implemented (cleaning, dedupe, truncation, single call, caching, retry limits, token caps).
9. Add a note that prices must be re-verified before submission and that response times were estimated.
10. Ensure no claim of "maximum accuracy" appears without supporting tests.

### Checklist

- [ ] Three or more models compared
- [ ] All eight comparison criteria covered
- [ ] Pricing dated and sourced
- [ ] Measured vs estimated clearly distinguished
- [ ] Cost per analysis calculated with arithmetic shown
- [ ] Fallback and balancing approach documented

### Pitfalls

- Do not copy stale pricing from undated blog posts without checking the official page.
- Do not invent benchmark scores.
- Do not omit the "source dated" note; evaluators look for it.

---

## T18 — Deployment

**Objective:** Provide the publicly accessible demo required by the brief.

**Inputs:** T14 app, T16 passing tests, T02 production settings.

**Outputs:** Live demo URL, endpoint URL and `/docs` URL.

### Steps

1. Choose an ASGI-compatible host with a free or low-cost tier (for example Render, Railway, Fly.io or Cloud Run).
2. Add any platform-specific start command that runs Uvicorn on the platform-assigned host and port, while keeping local port 4000 unchanged.
3. Set every environment variable in the hosting dashboard; do not bake them into the image or repository.
4. Deploy from the public GitHub repository so the code and demo are linked.
5. Confirm the service starts and `/health` responds.
6. Send a sample request to the live `/link-analysis` endpoint and confirm a full five-section response.
7. Open the live `/docs` page and confirm it is publicly accessible.
8. Test one failure case on the live endpoint (invalid URL) to confirm graceful errors.
9. Record the three URLs for the submission email.
10. If the free tier sleeps, note the cold-start delay in the README so reviewers know to retry once.

### Checklist

- [ ] App publicly accessible
- [ ] Environment variables set in host, not in code
- [ ] `/link-analysis` works live
- [ ] `/docs` works live
- [ ] Failure case verified
- [ ] URLs recorded

### Pitfalls

- Do not expose the app on a host that requires authentication for reviewers.
- Do not leave the repository private — the brief requires public.
- Do not commit deployment secrets or platform tokens.

---

## T19 — Submission and verification

**Objective:** Complete all mandatory verification and email steps.

**Inputs:** T17 documentation, T18 live demo, public repository.

**Outputs:** Submitted application and email.

### Steps

1. Confirm the GitHub repository is public and contains all source, tests, `.env.example`, `requirements.txt`, `README.md` and screenshots/logs.
2. Confirm no API keys, passwords or private credentials exist anywhere in the repository, including commit history.
3. Confirm `README.md` contains setup instructions, sample request and response, LLM comparison, final recommendation and submission details.
4. Add screenshots or logs showing a successful API call and the `/docs` page.
5. Follow Dxora Technologies on LinkedIn using the link in the brief.
6. Follow CREST on Instagram using the link in the brief.
7. Prepare your own LinkedIn and Instagram profile links for verification.
8. Compose the email to hr@chivoxai.com with the exact subject format: `<Your Name> - Python Practical Link Analysis test review`.
9. Include in the body: full name, demo link, public GitHub repository link, contact number, current location, and preferred date/time for final discussion.
10. Send the email before the stated deadline and retain a copy.
11. Prepare for the final panel discussion by reviewing Python, FastAPI, extraction, prompt engineering, competitor/SEO intelligence, model selection and code quality topics listed in the brief.

### Checklist

- [ ] Repository public and complete
- [ ] No secrets anywhere
- [ ] README complete
- [ ] Screenshots/logs included
- [ ] Both accounts followed
- [ ] Profile links ready
- [ ] Email sent with correct subject and all six items

### Pitfalls

- Do not submit before the live demo is verified — reviewers will test it.
- Do not forget the social verification steps; they are mandatory.
- Do not use the wrong subject line format.

---

## 24. Definition of done

The project is complete only when **all** of the following are true:

1. `POST /link-analysis` works locally on port 4000 with a valid public URL.
2. The response contains `success`, `website`, `brand`, and all five sections under `analysis`.
3. Competitor analysis includes brand details and at least three competitors where reliable, with AI suggestions labelled.
4. Exactly five search queries are returned, covering Google, Facebook, Instagram, LinkedIn and X, with no invented volumes.
5. SEO section includes keywords, title, meta description and supporting content.
6. Exactly five services are returned with `source` labels.
7. Target audience section includes all nine fields and grounds location in the page.
8. Invalid URLs, private addresses, unreachable sites and LLM failures return graceful, structured errors.
9. API keys are only in environment variables and `.env` is git-ignored.
10. Tests pass without real network or API calls.
11. `README.md` contains setup, samples, LLM comparison, recommendation and submission details.
12. Repository is public and the app is deployed with a working live demo and `/docs`.

---

## 25. Evaluation criteria mapping

| Criteria | Marks | Where earned in this guide |
|---|---:|---|
| FastAPI implementation and API structure | 10 | T03, T14 |
| Website extraction and content understanding | 15 | T04, T05, T06 |
| LLM integration and structured output | 15 | T03, T07, T13 |
| Competitor and search query analysis | 15 | T08, T09 |
| SEO recommendations and keyword intelligence | 10 | T10 |
| Services and target audience identification | 10 | T11, T12 |
| LLM model research and cost optimization | 15 | T15, T17 |
| Error handling, code quality and documentation | 10 | T01, T02, T14, T16, README |
| **Total** | **100** | |

Use this table as a self-scoring sheet before submission.

---

## 26. Risk register and troubleshooting

| Risk | Symptom | Mitigation |
|---|---|---|
| Target site blocks the fetcher | 403 or empty body | Realistic user-agent, retry once, clear 502 error with status |
| Target site is JavaScript-only | Thin cleaned text | Fallback to meta/title/JSON-LD, then "no analysable content" error |
| LLM returns prose around JSON | Parse error | Strip fences, corrective retry with exact error |
| LLM omits required fields | Schema validation error | Pydantic validation + retry + fallback |
| LLM invents search volumes | Metric-like numbers in output | Explicit prompt ban + schema with no volume fields + post-check |
| Redirect to internal IP | SSRF guard trip | Manual redirect handling with per-hop validation (T04/T05) |
| DNS rebinding | Guard passes but fetch goes internal | Re-validate resolved IP immediately before request |
| Cost overrun | High token usage | Clean/dedupe/truncate, token cap, single call, cache, low temperature |
| Cold start on free host | Slow first request | Note in README; use `/health` warm-up |
| Secret leakage | Key visible in logs/repo | `.gitignore`, startup checks, log redaction, history scan before submission |

### Debugging order

1. Check settings load correctly and the intended provider/model is active.
2. Validate the URL independently of the app.
3. Inspect the cleaned page data fields and token count — most quality problems originate here.
4. Inspect the generated prompt structure (not the key) and confirm grounding flags are present.
5. Inspect raw LLM output and the exact validation error.
6. Check retry/fallback logs.
7. Only then look at the endpoint and response shaping.

---

## Appendix A — Response field dictionary

| Path | Type | Meaning |
|---|---|---|
| `success` | boolean | True when the analysis completed successfully |
| `website` | string | Normalised submitted URL |
| `brand.name` | string | Brand name found on the site |
| `brand.category` | string | Main business category |
| `brand.summary` | string | Short business overview |
| `analysis.competitor_analysis.brand_overview` | string | Overview of the submitted brand |
| `analysis.competitor_analysis.competitors` | array | Competitor objects with strengths/weaknesses and source |
| `analysis.competitor_analysis.strengths` | array | Brand strengths (if following example shape) |
| `analysis.competitor_analysis.your_advantages` | array | Competitive advantages |
| `analysis.competitor_analysis.opportunities` | array | Positioning improvements |
| `analysis.target_search_queries` | array | Five query objects across the five platforms |
| `analysis.seo_improvements` | object | Keywords, title, meta description, supporting content |
| `analysis.top_services` | array | Five service objects with source labels |
| `analysis.target_audience` | object | Nine audience fields including location and segments |
| `source` (competitor/service item) | string | `website_content` or `ai_suggestion` — grounding marker |

---

## Appendix B — Prompt construction rules

1. **System prompt:** role, task, output contract, grounding rules, no-invented-metrics rule, section requirements, JSON-only instruction.
2. **User prompt:** clearly delimited blocks for final URL, title, meta description, headings, cleaned body text, detected language and grounding flags.
3. **Schema injection:** include the JSON schema or use the provider's native structured-output mode; keep field descriptions authoritative.
4. **Grounding flags usage:** if a flag is false, instruct the model to say the information is not available on the page rather than inferring it silently.
5. **Source labelling:** require `ai_suggestion` for any competitor or service not explicitly found in content.
6. **Platform vocabulary:** enumerate the five allowed platform strings.
7. **Intent vocabulary:** provide a short list of accepted intent labels.
8. **Length controls:** specify title and meta description length guidance; set max output tokens.
9. **Determinism:** low temperature, JSON-only, no Markdown.
10. **Retry prompt:** include the exact validation error and request a corrected JSON object only.
11. **Never include:** API keys, internal file paths, raw HTML, or unrelated example businesses that could bias the output.

---

**End of guide.** Keep this file and `README.md` together in the repository root so any reviewer or agent can reconstruct the entire project from these two documents.
