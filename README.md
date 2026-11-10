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
- Mailpit (verification emails and development SMS): http://localhost:8025

Source is copied into the images, and Compose Watch mirrors edits into the running
containers. No host directory is bind-mounted, so host and container UIDs do not
need to match. Changes under `frontend/` and `backend/` reload automatically;
changes to `package.json`, `package-lock.json`, `pyproject.toml`, or `uv.lock`
trigger a rebuild. Generated files (`node_modules`, `.svelte-kit`, `.venv`) stay
inside the containers. Compose uses local development defaults; optional overrides
are documented in `.env.example`. PostgreSQL 18 and Redis run on the internal
Compose network; the backend applies database migrations on start.

## Demo data

With the development stack running, fill PostgreSQL with six verified demo accounts
(three customers, three providers), thirteen listings covering all six categories, and
one active order that locks the category of Digital Daily's banner offering (FR-017).
Digital Daily's newsletter offering is expired, so it cannot be resumed (FR-019):

```sh
just seed          # safe to re-run; existing demo rows are kept
just seed --reset  # remove the demo accounts and listings, then recreate them
```

The password for every demo account is **`AdifyDemo123`**. Sign in at
http://localhost:5173/sign-in.

| Role     | Email                               | Name               |
| -------- | ----------------------------------- | ------------------ |
| customer | `olena.marchenko@demo.adify.app`    | Olena Marchenko    |
| customer | `andrii.bondar@demo.adify.app`      | Andrii Bondar      |
| customer | `tetiana.shevchenko@demo.adify.app` | Tetiana Shevchenko |
| provider | `digital.daily@demo.adify.app`      | Digital Daily      |
| provider | `sofiia.k@demo.adify.app`           | Sofiia K.          |
| provider | `pocket.studio@demo.adify.app`      | Pocket Studio      |

Demo data is development-only. The CLI refuses to run unless
`ADIFY_ALLOW_SEED=true`; the `just seed` recipe sets it only for the local backend
container. `--reset` deletes only accounts whose email ends in `@demo.adify.app`,
their listings, and their orders.

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
[story #4](docs/story-04.md), [story #7](docs/story-07.md),
[story #11](docs/story-11.md), [story #5](docs/story-05.md), [story #17](docs/story-17.md), [story #19](docs/story-19.md),
[listings ADY-008–010](docs/story-08-10.md),
[editing listings](docs/story-edit-listing.md),
[password reset](docs/story-password-reset.md),
[pausing and resuming listings](docs/story-pause-resume-listing.md), and
[deleting listings](docs/story-delete-listing.md). The source
documents are supplied alongside this repository and are not modified here.

Executed checks and the Docker-based browser-test command are recorded in
[verification](docs/verification.md).
