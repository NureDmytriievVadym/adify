# List recipes
default:
    @just --list

# Install web and backend dependencies
install:
    npm ci
    uv sync --project backend --frozen

# Web dev server with HMR
web:
    npm run dev -- --host 0.0.0.0

# API with reload
backend port="8000":
    uv run --project backend uvicorn adify_api.main:app --app-dir backend/src --reload --host 0.0.0.0 --port {{port}}

# Start PostgreSQL and Redis in Docker
infra:
    docker compose up -d postgres redis

# Formatting, lint, Svelte/TypeScript, backend tests, production build
check:
    npm run format:check
    npm run lint
    npm run check
    uv run --project backend ruff check backend
    uv run --project backend ruff format --check backend
    uv run --project backend pytest backend/tests
    npm run build

# Playwright suite; extra args go to Playwright
e2e *args:
    npm run test:e2e -- {{args}}
