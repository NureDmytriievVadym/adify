default:
    @just --list

# Development stack in the foreground with Compose Watch. Ctrl+C stops watching.
# Source edits are synced into the containers; no host bind mounts are used.
up *args:
    docker compose up --build --watch {{args}}

# Detached stack for checks, CI-like runs, or when you do not need live sync.
up-detached *args:
    docker compose up --build -d {{args}}

down *args:
    docker compose down {{args}}

logs *service:
    docker compose logs -f {{service}}

# The checks below run inside the running watcher containers, so they see synced code.
# Start the stack with `just up` first.
lint:
    docker compose exec -T frontend npm run format:check
    docker compose exec -T frontend npm run lint
    docker compose exec -T frontend npm run check
    docker compose exec -T backend ruff check .
    docker compose exec -T backend ruff format --check .

test:
    docker compose exec -T backend pytest

# Formatting writes to the host tree, so it needs the host toolchain.
# Use format-on-save in the editor instead if Node.js/uv are not installed.
format:
    npm run format
    uv run --project backend ruff format backend

# Playwright image with source baked in; no bind mount and no host browsers required.
# Extra args go to Playwright: `just e2e --project=chromium`.
e2e *args:
    docker compose run --rm --build e2e npm run test:e2e --workspace @adify/web -- {{args}}

# Demo data: 3 customers, 3 providers, 13 listings (1 expired) across all categories, 1 order.
# Safe to re-run; `just seed --reset` recreates the demo rows.
seed *args:
    docker compose exec -T -e ADIFY_ALLOW_SEED=true backend python -m adify_api.seed {{args}}
