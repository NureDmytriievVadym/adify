# Adify

An internet advertising marketplace for customers and providers in Ukraine.
The product language is English and the currency is UAH.

## Quick start

Install Docker with Compose, then run from this directory:

```sh
docker compose up --build
```

- Website: http://localhost:5173
- FastAPI Swagger: http://localhost:8000/docs
- API health: http://localhost:8000/api/v1/health

Compose uses local development defaults; optional overrides are documented in
`.env.example`. PostgreSQL 18 and Redis run on the internal Compose network.
The website currently uses explicitly labeled, local presentation fixtures.

## Native development

Prerequisites: Node.js 24 LTS, npm 12, Python 3.13, [uv](https://docs.astral.sh/uv/),
and [just](https://just.systems/). Run `just` to list recipes.

```sh
just install
just web       # terminal 1: http://localhost:5173
just backend   # terminal 2: http://localhost:8000/docs
```

The UI and health endpoint can run without a database. Start the development
database and cache when needed with `just infra`.

## Checks

```sh
just check     # formatting, lint, Svelte/TypeScript, backend tests, production build
npm run test:e2e:install
just e2e       # Chromium, Firefox, WebKit: responsive layout, navigation, axe
```

`npm run format` formats the web workspace and root JavaScript/Markdown files;
`uv run --project backend ruff format .` formats Python.
Dependency versions are recorded in `package-lock.json` and `backend/uv.lock`.

## Repository

```text
frontend/        Svelte 5 + SvelteKit, TypeScript, adapter-node
  docker/        Dockerfile and Compose service for the website
backend/         FastAPI, versioned REST API, uv-managed Python package
  docker/        Dockerfile and Compose services for API, PostgreSQL 18, Redis
docs/            Architecture, contribution guide, story #1 scope and acceptance
.github/         Pull request checks
compose.yaml     Includes frontend/ and backend/ Compose files
```

Start with [architecture](docs/architecture.md), [contributing](CONTRIBUTING.md),
and [story #1](docs/story-01.md). The supplied **Adify – SRS v1.2.md** is the
source of truth and takes precedence over the product backlog. The source
documents are supplied alongside this repository and are not modified here.

Executed checks and the Docker-based browser-test command are recorded in
[verification](docs/verification.md).
