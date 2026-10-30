default:
    @just --list

up *args:
    docker compose up --build {{args}}

down *args:
    docker compose down {{args}}

logs *service:
    docker compose logs -f {{service}}

lint:
    docker compose run --rm frontend npm run format:check
    docker compose run --rm frontend npm run lint
    docker compose run --rm frontend npm run check
    docker compose run --rm --no-deps backend ruff check .
    docker compose run --rm --no-deps backend ruff format --check .

format:
    docker compose run --rm frontend npm run format
    docker compose run --rm --no-deps backend ruff format .

test:
    docker compose run --rm --no-deps backend pytest

# Playwright in Chromium, Firefox, WebKit; extra args go to Playwright: `just e2e --project=chromium`
e2e *args:
    docker run --rm --ipc=host -v {{quote(justfile_directory() + ":/work")}} -v /work/node_modules -v /work/frontend/node_modules -w /work mcr.microsoft.com/playwright:v1.64.1-noble sh -c "npm ci --ignore-scripts && npm run test:e2e -- {{args}}"
