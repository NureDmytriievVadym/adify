.PHONY: install web backend check e2e

install:
	npm ci
	uv sync --project apps/backend --frozen

web:
	npm run dev -- --host 0.0.0.0

backend:
	uv run --project apps/backend uvicorn adify_api.main:app --app-dir apps/backend/src --reload --host 0.0.0.0 --port 8000

check:
	npm run format:check
	npm run lint
	npm run check
	uv run --project apps/backend ruff check apps/backend
	uv run --project apps/backend ruff format --check apps/backend
	uv run --project apps/backend pytest apps/backend/tests
	npm run build

e2e:
	npm run test:e2e
