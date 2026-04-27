# AI-Driven API Automation & CI Gating

> Senior SDET Challenge — PayMongo  
> Playwright · TypeScript · Gemini LLM · GitHub Actions

---

## Quick Start

```bash
# 1. Install dependencies
make install

# 2. Set environment variables
cp .env.example .env
# Edit .env — set GEMINI_API_KEY, STAGING_API_URL, STAGING_BASE_URL

# 3. Generate tests + run everything
make test
```

---

## Project Structure

```
.
├── README.md
├── Makefile                        # Orchestration commands
├── swagger.yaml                    # API specification (source of truth)
├── playwright.config.ts            # Unmodified template config
├── package.json                    # Unmodified template deps
├── tsconfig.json
├── .env.example                    # Secret template — never commit .env
│
├── scripts/
│   ├── generate_tests.py           # LLM generation script (main entrypoint)
│   └── github_action.yaml          # CI/CD pipeline definition
│
├── config/
│   └── environment.ts              # Unmodified template env config
│
└── generated_test/                 # All generated output goes here
    ├── utils/
    │   ├── api-helper.ts           # Unmodified template helper
    │   └── test-utils.ts           # Unmodified template helper
    ├── page-objects/
    │   └── base-page.ts            # Unmodified template base class
    └── tests/
        ├── api/                    # LLM-generated API tests
        │   ├── api-health.spec.ts
        │   ├── api-validate-card.spec.ts
        │   ├── api-validate-email.spec.ts
        │   └── api-checkout.spec.ts
        └── web/                    # LLM-generated E2E tests
            └── checkout-flow.spec.ts
```

---

## 1. LLM Prompt Design

Two prompt templates are used — both live in `scripts/generate_tests.py`.

### API Prompt
Constructed per-endpoint from the parsed Swagger spec. Each prompt contains:
- The HTTP method + path
- Full request body schema (resolved from `$ref`)
- All response schemas per status code
- Strict rules: use `ApiHelper`, cover happy path + edge cases, schema-aware assertions, no `test.skip()`

Key design decisions:
- **Low temperature (0.2)** for deterministic, consistent output across regenerations
- **Schema injection** — the full resolved schema is in the prompt so Gemini asserts specific fields, not just status codes
- **One prompt per endpoint** — keeps context small, avoids model confusion between endpoints

### E2E Prompt
A single prompt describing the checkout page business flow. Contains:
- Field list (name, address, email, card, CVV, expiry)
- Selector priority rules (data-testid → ARIA → label → name/id)
- Available API endpoints for cross-validation
- Requirement to cover the full happy path AND one negative case

---

## 2. How Swagger → Playwright Tests

```
swagger.yaml
    │
    ▼
generate_tests.py
    │  • yaml.safe_load() parses the spec
    │  • Resolves all $ref definitions inline
    │  • Builds one structured prompt per endpoint
    │
    ▼
Gemini API (gemini-2.0-flash, temp=0.2)
    │
    ▼
validate_generated_test()
    │  • Checks for required imports
    │  • Checks for test.describe() + test() + expect()
    │  • API tests must use ApiHelper
    │  • Rejects hallucinated structure before writing
    │
    ▼
generated_test/tests/api/*.spec.ts
```

---

## 3. How the Generation Process Works

```bash
# Standard run (uses cache for identical prompts)
python scripts/generate_tests.py

# Force fresh LLM calls (e.g. after Swagger changes)
python scripts/generate_tests.py --no-cache

# Partial generation
python scripts/generate_tests.py --api-only
python scripts/generate_tests.py --e2e-only
```

**Cache strategy:** Each prompt is SHA-256 hashed. If the same prompt hash exists in `.generation_cache/`, the cached `.ts` file is reused — no API call, no cost, no rate limit risk. Changing the Swagger or prompt template changes the hash, triggering a fresh call automatically. This makes generation **idempotent**.

**Rate limit handling:** If Gemini returns HTTP 429, the script retries up to 3 times with exponential backoff (5s, 10s, 15s).

---

## 4. How CI Gates Production

The GitHub Actions workflow (`scripts/github_action.yaml`) has 4 jobs:

```
PR opened / push to main
        │
        ▼
┌─────────────────────┐
│  generate-tests     │  Calls Gemini, validates output, uploads artifact
│  (fails PR if LLM   │
│   generation fails) │
└────────┬────────────┘
         │ (parallel)
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌────────┐
│api-    │ │e2e-    │
│tests   │ │tests   │
└────┬───┘ └───┬────┘
     └────┬────┘
          ▼
   ┌──────────────┐
   │ quality-gate │  Fails PR if either job failed
   └──────────────┘
```

PRs **cannot be merged** if any job fails. Artifacts (HTML report, JUnit XML, screenshots) are retained for 30 days.

**To use as a production deployment gate:** Add a `deploy` job that `needs: [quality-gate]` and only runs on `push` to `main`. Tests act as the final green light before deployment.

---

## 5. Scaling to Many Endpoints

The current approach scales linearly — one LLM call per endpoint. For APIs with 50+ endpoints:

- **Parallel generation:** Run multiple `generate_tests.py` subprocesses concurrently (split by tag/path)
- **Cache is the multiplier:** After first run, regeneration for unchanged endpoints is instant (cache hit)
- **Swagger-driven:** Adding a new endpoint to the spec automatically generates a new test on next CI run — no human intervention needed
- **Batch prompting:** Group CRUD endpoints for the same resource into a single prompt to reduce API calls

---

## 6. Preventing Hallucinated / Incorrect Tests

**Before writing:**
- `validate_generated_test()` checks structural requirements (imports, describe blocks, assertions)
- Tests that fail validation are rejected — not written to disk

**At runtime:**
- Generated tests run against a real API — if the test asserts a non-existent field or wrong status code, it fails visibly in CI
- JUnit XML output captures exact failure messages for review

**Recommended additions for production:**
- TypeScript compiler check (`tsc --noEmit`) on generated files before running
- Diff-based review: commit generated tests to a branch and require human review on changes

---

## 7. Handling Flaky or Unstable Tests

Playwright config already handles this:
- `retries: 2` on CI — transient network failures auto-retry
- `trace: 'retain-on-failure'` — full trace available for debugging
- `screenshot: 'only-on-failure'` + `video: 'retain-on-failure'`

Additional strategies:
- API tests have no UI flakiness by design — they're deterministic if the API is stable
- E2E: `waitForLoadState('networkidle')` before interactions prevents race conditions
- Avoid `page.waitForTimeout()` — use explicit element/network waits instead

---

## 8. E2E Selector Strategy & Stability

The E2E prompt instructs Gemini to use selectors in this priority order:

1. `[data-testid="..."]` — most stable, immune to CSS/text changes
2. ARIA roles: `getByRole('button', { name: 'Submit' })`
3. Label associations: `getByLabel('Email address')`
4. `name` / `id` attributes as fallback

The prompt explicitly forbids CSS class selectors and XPath — they break on UI refactors.

---

## 9. Preventing Flaky Frontend Tests

- **Network idle wait:** `waitForLoadState('networkidle')` before form interactions
- **Intercept API calls:** Use `page.waitForResponse('/api/checkout')` instead of fixed timeouts after submit
- **Retry on CI:** `retries: 2` catches one-off infrastructure hiccups
- **Stable test data:** `TestUtils.generateTestData()` uses timestamps to avoid conflicts between parallel runs
- **No hardcoded waits:** All waits are condition-based (element visible, network idle, text present)

---

## Secret Handling

| Secret | Local | CI |
|---|---|---|
| `GEMINI_API_KEY` | `.env` file (gitignored) | GitHub Actions Secret |
| `STAGING_API_URL` | `.env` file | GitHub Actions Secret |
| `STAGING_BASE_URL` | `.env` file | GitHub Actions Secret |
| `API_SECRET_KEY` | `.env` file | GitHub Actions Secret |

**Never** commit `.env`. It is in `.gitignore`. The generation script reads `GEMINI_API_KEY` from `os.environ` — it will raise a clear error if not set.

To add secrets in GitHub: `Settings → Secrets and variables → Actions → New repository secret`

---

## Bonus Features Implemented

| Feature | Status |
|---|---|
| Schema-aware assertions | ✅ Full response schema injected into prompt |
| LLM output validation before saving | ✅ `validate_generated_test()` guardrails |
| Deterministic generation (low temperature) | ✅ `temperature: 0.2` |
| Parallel CI execution | ✅ API + E2E jobs run in parallel |
| Rate-limit handling | ✅ Exponential backoff, 3 retries |
| Idempotent test regeneration | ✅ SHA-256 prompt cache |
| Intelligent caching | ✅ Cache invalidates on prompt/swagger change |
