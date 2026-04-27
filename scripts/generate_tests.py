#!/usr/bin/env python3
"""
AI-Driven Test Generation Script
Reads Swagger/OpenAPI spec + frontend context, calls Gemini API,
and writes Playwright test files into generated_test/tests/
"""

import os
import sys
import json
import time
import hashlib
import argparse
import urllib.request
import urllib.error
import yaml

# ── Config ─────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL   = "gemini-2.0-flash-lite"
GEMINI_URL     = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
)

SWAGGER_PATH   = os.path.join(os.path.dirname(__file__), "..", "swagger.yaml")
OUT_API_DIR    = os.path.join(os.path.dirname(__file__), "..", "generated_test", "tests", "api")
OUT_WEB_DIR    = os.path.join(os.path.dirname(__file__), "..", "generated_test", "tests", "web")
CACHE_DIR      = os.path.join(os.path.dirname(__file__), "..", ".generation_cache")

MAX_RETRIES    = 3
RETRY_DELAY    = 5   # seconds between retries

# ── Prompt Templates ────────────────────────────────────────────────────────
API_PROMPT_TEMPLATE = """
You are an expert QA automation engineer specializing in Playwright and TypeScript.

Generate a complete, production-ready Playwright API test file for the following endpoint.
You MUST follow this exact import and helper pattern from the project template:

```typescript
import {{ test, expect }} from '@playwright/test';
import {{ ApiHelper }} from '../../utils/api-helper';
```

Rules:
1. Use ApiHelper class for all HTTP calls (get, post, put, delete methods).
2. Group tests in test.describe() block named after the endpoint tag.
3. Cover: happy path, edge cases, invalid inputs, and schema validation.
4. Use expect() assertions for status codes AND response body fields.
5. Use schema-aware assertions — check every field in the response schema.
6. All test data must use realistic but safe values matching the schema examples.
7. Do NOT use test.skip() on real tests.
8. Output ONLY valid TypeScript code. No markdown fences, no explanations.

ENDPOINT SPECIFICATION:
Path: {path}
Method: {method}
Summary: {summary}
Description: {description}
Request Body Schema: {request_schema}
Response Schemas: {response_schemas}
Base API URL env var: process.env.STAGING_API_URL (already set via playwright.config.ts)
"""

E2E_PROMPT_TEMPLATE = """
You are an expert QA automation engineer specializing in Playwright E2E testing.

Generate a complete Playwright E2E test file for a payment checkout page.
You MUST follow this exact import pattern from the project template:

```typescript
import {{ test, expect }} from '@playwright/test';
import {{ TestUtils }} from '../../utils/test-utils';
```

Frontend checkout page details:
- URL: /checkout (relative to baseURL)
- Has fields: shipping name, shipping address, email
- Has payment fields: card number, expiry, CVV
- Has a submit button
- Shows a success state after checkout

Rules:
1. Use TestUtils class for fillField(), clickElement(), waitForText() helpers.
2. Cover the complete checkout flow: fill name → fill address → fill email → fill card → submit → verify success.
3. Cover at least one negative case: empty required field submission.
4. Use robust selectors in this priority order:
   a. data-testid attributes first (e.g. [data-testid="submit-button"])
   b. ARIA roles (e.g. role=button, name="Submit")
   c. label text associations
   d. name/id attributes as fallback
5. Add waitForPageLoad() after navigation.
6. Validate visible success state (text, element, URL change).
7. Use realistic test data (no "foo", "bar", "test123" placeholders).
8. Do NOT use test.skip() on real tests.
9. Output ONLY valid TypeScript code. No markdown fences, no explanations.

API endpoints available for validation:
- POST /api/validate-email  — body: {{ email: string }}
- POST /api/validate-card   — body: {{ cardNumber: string }}
- POST /api/checkout        — body: {{ amount, cardNumber, cvv, expiry }}

The page URL is controlled by environment.baseUrl (staging: process.env.STAGING_BASE_URL).
"""

# ── Helpers ─────────────────────────────────────────────────────────────────
def load_swagger(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def resolve_ref(swagger: dict, ref: str) -> dict:
    """Resolve $ref like '#/definitions/main.PaymentRequest'"""
    parts = ref.lstrip("#/").split("/")
    node = swagger
    for p in parts:
        node = node.get(p, {})
    return node


def extract_schema(swagger: dict, schema_ref: dict) -> dict:
    if "$ref" in schema_ref:
        return resolve_ref(swagger, schema_ref["$ref"])
    return schema_ref


def cache_key(prompt: str) -> str:
    return hashlib.sha256(prompt.encode()).hexdigest()[:16]


def read_cache(key: str) -> str | None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f"{key}.ts")
    if os.path.exists(path):
        with open(path) as f:
            return f.read()
    return None


def write_cache(key: str, content: str):
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f"{key}.ts")
    with open(path, "w") as f:
        f.write(content)


def call_gemini(prompt: str, use_cache: bool = True) -> str:
    """Call Gemini API with retry + caching."""
    if not GEMINI_API_KEY:
        raise EnvironmentError(
            "GEMINI_API_KEY environment variable is not set.\n"
            "Set it with: export GEMINI_API_KEY=your_key_here"
        )

    key = cache_key(prompt)
    if use_cache:
        cached = read_cache(key)
        if cached:
            print(f"  [cache hit] Using cached generation ({key})")
            return cached

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,      # Low temp = more deterministic output
            "topP": 0.8,
            "maxOutputTokens": 4096,
        },
    }

    data = json.dumps(payload).encode("utf-8")
    req  = urllib.request.Request(
        GEMINI_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = json.loads(resp.read().decode())
                text = body["candidates"][0]["content"]["parts"][0]["text"]
                # Strip markdown fences if model still adds them
                text = text.strip()
                if text.startswith("```"):
                    lines = text.split("\n")
                    text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
                if use_cache:
                    write_cache(key, text)
                return text
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = RETRY_DELAY * attempt
                print(f"  [rate limit] Attempt {attempt}/{MAX_RETRIES}. Waiting {wait}s...")
                time.sleep(wait)
            else:
                raise
        except Exception as e:
            if attempt == MAX_RETRIES:
                raise
            print(f"  [error] Attempt {attempt}/{MAX_RETRIES}: {e}. Retrying...")
            time.sleep(RETRY_DELAY)

    raise RuntimeError(f"Gemini API failed after {MAX_RETRIES} attempts.")


def validate_generated_test(content: str, filename: str) -> bool:
    """
    Guardrails: Basic validation before writing generated test.
    Catches hallucinated imports or missing test structure.
    """
    errors = []

    if "import { test, expect } from '@playwright/test'" not in content:
        errors.append("Missing required import: @playwright/test")
    if "test.describe(" not in content:
        errors.append("Missing test.describe() block")
    if "test(" not in content:
        errors.append("Missing test() cases")
    if "expect(" not in content:
        errors.append("Missing expect() assertions")

    # API tests must use ApiHelper
    if "api" in filename.lower() and "ApiHelper" not in content:
        errors.append("API test missing ApiHelper usage")

    # Web tests must use TestUtils or page
    if "web" in filename.lower() or "e2e" in filename.lower():
        if "TestUtils" not in content and "page." not in content:
            errors.append("E2E test missing page interactions")

    if errors:
        print(f"  [validation failed] {filename}:")
        for e in errors:
            print(f"    ✗ {e}")
        return False

    print(f"  [validation passed] {filename}")
    return True


def write_test_file(directory: str, filename: str, content: str):
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, filename)
    with open(path, "w") as f:
        f.write(content)
    print(f"  [written] {path}")


# ── Generation Functions ────────────────────────────────────────────────────
def generate_api_tests(swagger: dict, use_cache: bool = True):
    print("\n=== Generating API Tests ===")
    paths = swagger.get("paths", {})

    for path, methods in paths.items():
        for method, spec in methods.items():
            tag      = spec.get("tags", ["general"])[0]
            summary  = spec.get("summary", "")
            desc     = spec.get("description", "")

            # Extract request body schema
            req_schema = {}
            for param in spec.get("parameters", []):
                if param.get("in") == "body" and "schema" in param:
                    req_schema = extract_schema(swagger, param["schema"])

            # Extract response schemas
            resp_schemas = {}
            for status, resp in spec.get("responses", {}).items():
                if "schema" in resp:
                    resp_schemas[status] = extract_schema(swagger, resp["schema"])

            prompt = API_PROMPT_TEMPLATE.format(
                path=path,
                method=method.upper(),
                summary=summary,
                description=desc,
                request_schema=json.dumps(req_schema, indent=2),
                response_schemas=json.dumps(resp_schemas, indent=2),
            )

            safe_name = path.strip("/").replace("/", "-").replace("_", "-")
            filename  = f"{safe_name}.spec.ts"

            print(f"\n→ {method.upper()} {path} ({tag})")

            try:
                content = call_gemini(prompt, use_cache=use_cache)
                if validate_generated_test(content, filename):
                    write_test_file(OUT_API_DIR, filename, content)
                else:
                    print(f"  [skipped] Validation failed, test not written.")
            except Exception as e:
                print(f"  [error] Failed to generate: {e}")
                sys.exit(1)


def generate_e2e_tests(use_cache: bool = True):
    print("\n=== Generating E2E Frontend Tests ===")

    prompt   = E2E_PROMPT_TEMPLATE
    filename = "checkout-flow.spec.ts"

    print(f"\n→ Checkout E2E flow")

    try:
        content = call_gemini(prompt, use_cache=use_cache)
        if validate_generated_test(content, filename):
            write_test_file(OUT_WEB_DIR, filename, content)
        else:
            print(f"  [skipped] Validation failed, test not written.")
    except Exception as e:
        print(f"  [error] Failed to generate: {e}")
        sys.exit(1)


# ── Entry Point ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Generate Playwright tests using Gemini LLM")
    parser.add_argument("--no-cache",   action="store_true", help="Bypass generation cache")
    parser.add_argument("--api-only",   action="store_true", help="Only generate API tests")
    parser.add_argument("--e2e-only",   action="store_true", help="Only generate E2E tests")
    parser.add_argument("--swagger",    default=SWAGGER_PATH, help="Path to Swagger YAML file")
    args = parser.parse_args()

    use_cache = not args.no_cache

    if not os.path.exists(args.swagger):
        print(f"[error] Swagger file not found: {args.swagger}")
        sys.exit(1)

    print(f"[config] Swagger: {args.swagger}")
    print(f"[config] Cache: {'disabled' if not use_cache else 'enabled'}")
    print(f"[config] Model: {GEMINI_MODEL}")

    swagger = load_swagger(args.swagger)

    if not args.e2e_only:
        generate_api_tests(swagger, use_cache=use_cache)

    if not args.api_only:
        generate_e2e_tests(use_cache=use_cache)

    print("\n✅ Test generation complete.")
    print(f"   API tests → {OUT_API_DIR}")
    print(f"   E2E tests → {OUT_WEB_DIR}")


if __name__ == "__main__":
    main()
