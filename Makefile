.PHONY: install web backend check e2e

install:
	npm ci
	uv sync --project backend --frozen

web:
	npm run dev -- --host 0.0.0.0

backend:
	uv run --project backend uvicorn adify_api.main:app --app-dir backend/src --reload --host 0.0.0.0 --port 8000

check:
	npm run format:check
	npm run lint
	npm run check
	uv run --project backend ruff check backend
	uv run --project backend ruff format --check backend
	uv run --project backend pytest backend/tests
	npm run build

e2e:
	npm run test:e2e
