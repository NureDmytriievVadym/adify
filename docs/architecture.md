# Architecture baseline

## Decisions

The supplied **Adify – SRS v1.2.md**, especially §2.6 and §3.7, is authoritative.
The provided diagram references have not been reconstructed or assumed.

| Area        | Baseline                                                             | Reason                                                                                     |
| ----------- | -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| Repository  | `frontend`, `backend`; npm workspace + independent uv package        | One repository, independently buildable clients and API; no heavy orchestration dependency |
| Web         | Svelte 5, SvelteKit 3, strict TypeScript, Node adapter               | SRS-prescribed stack; SSR, file-based routing, straightforward Node deployment             |
| Backend     | Python 3.13, FastAPI, versioned `/api/v1` routes                     | One OpenAPI contract for the web and future Flutter Android client                         |
| Persistence | PostgreSQL 18 via async SQLAlchemy 2 and Alembic; Redis in Compose   | Selected by the SRS; each story adds its tables as a reviewed migration                    |
| Interface   | Shared semantic components and CSS variables                         | Small initial UI, mobile-first constraints, straightforward extension by designers         |
| Tooling     | npm + uv lockfiles, ESLint, Prettier, Ruff, pytest, Playwright + axe | Reproducible installation and executable acceptance checks                                 |

Node.js 24 LTS and Python 3.13 are pinned at the major/minor level in runtime
files. Docker builds use `npm ci` and `uv sync --frozen`. Versions of third-party
actions and base images should be maintained by the infrastructure owner.

## Runtime boundaries

SvelteKit renders the preview pages from explicitly labeled presentation fixtures.
Registration, sign-in, and the account page call the API from the browser at
`PUBLIC_API_BASE_URL`; the API allows the web origins listed in `ADIFY_CORS_ORIGINS`
with credentials. The backend exposes a process-liveness endpoint, accounts,
authentication, and Swagger/OpenAPI documentation.

Authentication follows NFR-SEC-001: a 15-minute HS256 JWT access token sent as
`Authorization: Bearer`, and a 30-day refresh token rotated on every use and
stored only as a SHA-256 hash. The web keeps the access token in memory and the
refresh token in an HttpOnly `adify_refresh` cookie scoped to `/api/v1/auth`;
native clients request it in the response body. `ADIFY_JWT_SECRET` must be set
outside local development.

Future web and Android data flows must use the shared FastAPI REST API over HTTPS
and Socket.IO over WSS. Both clients must stay independent of PostgreSQL, Redis,
Mono, and storage credentials. Future contracts should be derived from FastAPI's
OpenAPI schema rather than maintaining duplicate handwritten schema definitions.
Do not add a second business API in SvelteKit route handlers.

Further domain packages, JWT/session management, Socket.IO, and integrations will
be introduced with their stories. Time-based listing expiry is already in
`adify_api.jobs` and runs once per cron invocation (see [story #15](story-015.md)).
The current `/api/v1/health` route reports liveness, not dependency readiness.
Introduce a separate readiness check when the application acquires mandatory
dependencies.

## Local services

`just up` (`docker-compose.yml`) builds development images containing the source
and starts PostgreSQL 18 and Redis under Compose Watch. Watch rules sync `frontend`
and `backend` edits into the containers, use `sync+restart` for Alembic migrations
and configuration, and rebuild on dependency manifests. No host source directory
is bind-mounted, so host and container UIDs/GIDs do not need to match; generated
files stay inside the containers. The web runs Vite HMR and the backend uses
uvicorn reload plus an Alembic upgrade on start.

Only web and API ports are published, bound to loopback. PostgreSQL 18 stores its
volume at `/var/lib/postgresql` using the version-specific internal layout; uploads,
PostgreSQL, and Redis use named volumes, not host paths. `just e2e` builds a
separate Playwright image with source baked in, so tests need neither host
browsers nor a bind mount. CI starts the same stack without watch. Production
images are not defined yet; they belong to deployment work. Local Compose traffic
is HTTP; production TLS termination, deployment secrets, backup automation,
runtime monitoring, and deployment workflows belong to infrastructure and
operational work. No external services are needed for the preview.

## UI extension

`+layout.svelte` owns the header, footer, and skip link. Routes own page composition.
Reusable components provide icons, cards, preview notices, and self-contained
CSS artwork. The mobile header uses an actual button with `aria-expanded` and
`aria-controls`; Escape closes it and navigation resets it. The UI supports
reduced-motion preferences. User-facing prices always show UAH.

SvelteKit 3 configuration lives in `vite.config.ts`. Local module imports use
the package's `#lib/*` mapping with explicit file extensions. Fonts are served
locally through Fontsource; preview pages do not depend on third-party requests.

The visual direction is an initial implementation choice: detailed design-system
requirements remain TBD in UI-005. The six categories follow FR-014. There is no
campaign analytics or profile-setup UI. Example order content is read-only and
does not implement transitions, payment handling, authorization, or persistence.
