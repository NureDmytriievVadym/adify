# Adify

An internet advertising marketplace for customers and providers in Ukraine.
The product language is English and the currency is UAH.

## Quick start

Install Docker with Compose and [just](https://just.systems/), then run from
this directory:

```sh
just up        # dev stack with hot-reload; `just` lists all recipes
```

- Website: http://localhost:5173
- FastAPI Swagger: http://localhost:8000/docs
- API health: http://localhost:8000/api/v1/health

Source is bind-mounted: edits in `frontend/` and `backend/` reload without a
rebuild. Rebuild (`just up` again) after changing dependencies. Compose uses
local development defaults; optional overrides are documented in `.env.example`.
PostgreSQL 18 and Redis run on the internal Compose network. The website
currently uses explicitly labeled, local presentation fixtures.

## Checks

Everything runs in containers; only Docker and just are needed on the host.

```sh
just lint      # Prettier, ESLint, Svelte/TypeScript, Ruff
just format    # Prettier and Ruff formatting
just test      # backend tests
just e2e       # Playwright: Chromium, Firefox, WebKit; `just e2e --project=chromium`
```

Dependency versions are recorded in `package-lock.json` and `backend/uv.lock`.

## Repository

```text
frontend/        Svelte 5 + SvelteKit, TypeScript, adapter-node
  docker/        Dockerfile and Compose service for the website
backend/         FastAPI, versioned REST API, uv-managed Python package
  docker/        Dockerfile and Compose services for API, PostgreSQL 18, Redis
docs/            Architecture, contribution guide, story #1 scope and acceptance
.github/         Pull request checks
docker-compose.yml  Local development stack (includes app Compose files)
justfile         Developer commands
```

Start with [architecture](docs/architecture.md), [contributing](CONTRIBUTING.md),
[story #1](docs/story-01.md), and [story #3](docs/story-03.md). The supplied **Adify – SRS v1.2.md** is the
source of truth and takes precedence over the product backlog. The source
documents are supplied alongside this repository and are not modified here.

Executed checks and the Docker-based browser-test command are recorded in
[verification](docs/verification.md).
