.PHONY: install generate generate-no-cache test test-api test-e2e report clean help

# ── Setup ──────────────────────────────────────────────────────────────────
install:
	npm ci
	npx playwright install --with-deps chromium
	pip install pyyaml

# ── Test Generation ────────────────────────────────────────────────────────
generate:
	@echo "→ Generating tests (cache enabled)..."
	python scripts/generate_tests.py

generate-no-cache:
	@echo "→ Generating tests (cache disabled — fresh LLM calls)..."
	python scripts/generate_tests.py --no-cache

generate-api-only:
	python scripts/generate_tests.py --api-only

generate-e2e-only:
	python scripts/generate_tests.py --e2e-only

# ── Test Execution ─────────────────────────────────────────────────────────
test: generate
	npm test

test-api: generate-api-only
	npm run test:api

test-e2e: generate-e2e-only
	npm run test:web

# ── Reporting ──────────────────────────────────────────────────────────────
report:
	npm run report

# ── Cleanup ────────────────────────────────────────────────────────────────
clean:
	rm -rf generated_test/tests/api/*.spec.ts
	rm -rf generated_test/tests/web/*.spec.ts
	rm -rf playwright-report/
	rm -rf test-results/
	rm -rf screenshots/

help:
	@echo ""
	@echo "Available commands:"
	@echo "  make install           Install all dependencies"
	@echo "  make generate          Generate tests (with LLM cache)"
	@echo "  make generate-no-cache Force fresh LLM generation"
	@echo "  make test              Generate + run all tests"
	@echo "  make test-api          Generate + run API tests only"
	@echo "  make test-e2e          Generate + run E2E tests only"
	@echo "  make report            Open Playwright HTML report"
	@echo "  make clean             Remove generated tests + reports"
	@echo ""
	@echo "Required env var: GEMINI_API_KEY"
	@echo "Copy .env.example → .env and fill in values before running locally."
