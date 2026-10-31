# Adify

An internet advertising marketplace for customers and providers in Ukraine.
The product language is English and the currency is UAH.

## Quick start

Install Docker with Compose and [just](https://just.systems/), then run from
this directory:

```sh
just up        # dev stack with Compose Watch; Ctrl+C stops it
just up-detached --wait  # background stack for checks, without live sync
```

- Website: http://localhost:5173
- FastAPI Swagger: http://localhost:8000/docs
- API health: http://localhost:8000/api/v1/health

Source is copied into the images, and Compose Watch mirrors edits into the running
containers. No host directory is bind-mounted, so host and container UIDs do not
need to match. Changes under `frontend/` and `backend/` reload automatically;
changes to `package.json`, `package-lock.json`, `pyproject.toml`, or `uv.lock`
trigger a rebuild. Generated files (`node_modules`, `.svelte-kit`, `.venv`) stay
inside the containers. Compose uses local development defaults; optional overrides
are documented in `.env.example`. PostgreSQL 18 and Redis run on the internal
Compose network; the backend applies database migrations on start.

## Checks

Runtime, lint, backend tests, and browser tests run in containers. Formatting writes
to the host tree and therefore needs Node.js 24 and uv on the host (or use your
editor's format-on-save).

```sh
just up        # keep the watcher running in another terminal
just lint      # Prettier, ESLint, Svelte/TypeScript, Ruff, inside the containers
just test      # backend tests, inside the backend container
just e2e       # Playwright image: Chromium, Firefox, WebKit; no host browsers
just e2e --project=chromium
just format    # host-side Prettier and Ruff; needs Node.js 24 and uv
```

`just lint` and `just test` operate on the synced container state. `just format`
edits the host tree directly. The e2e image is rebuilt from the current source,
so it needs neither the frontend container nor a bind mount. Dependency versions
are recorded in `package-lock.json` and `backend/uv.lock`.

## Repository

```text
frontend/        Svelte 5 + SvelteKit, TypeScript, adapter-node
  docker/        Dockerfile, Playwright Dockerfile, and Compose service
backend/         FastAPI, versioned REST API, uv-managed Python package
  docker/        Dockerfile and Compose services for API, PostgreSQL 18, Redis
docs/            Architecture, contribution guide, story #1 scope and acceptance
.github/         Pull request checks
docker-compose.yml  Local development stack (includes app Compose files)
justfile         Developer commands
```

Start with [architecture](docs/architecture.md), [contributing](CONTRIBUTING.md),
[story #1](docs/story-01.md), [story #3](docs/story-03.md),
[story #4](docs/story-04.md), [story #7](docs/story-07.md), and
[listings ADY-008–010](docs/story-08-10.md). The supplied **Adify – SRS v1.2.md** is
the source of truth and takes precedence over the product backlog. The source
documents are supplied alongside this repository and are not modified here.

Executed checks and the Docker-based browser-test command are recorded in
[verification](docs/verification.md).
