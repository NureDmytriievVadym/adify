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
Registration (`/register`) calls the API from the browser at `PUBLIC_API_BASE_URL`;
the API allows the web origins listed in `ADIFY_CORS_ORIGINS`. The backend exposes
a process-liveness endpoint, account registration, and Swagger/OpenAPI documentation.

Future web and Android data flows must use the shared FastAPI REST API over HTTPS
and Socket.IO over WSS. Both clients must stay independent of PostgreSQL, Redis,
Mono, and storage credentials. Future contracts should be derived from FastAPI's
OpenAPI schema rather than maintaining duplicate handwritten schema definitions.
Do not add a second business API in SvelteKit route handlers.

Further domain packages, JWT/session management, Socket.IO, scheduled
jobs, and integrations will be introduced with their stories. The current
`/api/v1/health` route reports liveness, not dependency readiness. Introduce a
separate readiness check when the application acquires mandatory dependencies.

## Local services

`docker compose up --build` builds Node and Python services and starts PostgreSQL
18 and Redis. Only web and API ports are published, bound to loopback. PostgreSQL
18 stores its volume at `/var/lib/postgresql` using the version-specific internal
layout. Redis has append-only persistence. Containers run web/API as non-root.

Native web development uses Vite HMR; backend development uses uvicorn reload.
Compose runs built applications and can be used for reproducibility checks. Local
Compose traffic is HTTP; production TLS termination, deployment secrets, backup
automation, runtime monitoring, and deployment workflows belong to infrastructure
and operational work. No external services are needed for the preview.

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
