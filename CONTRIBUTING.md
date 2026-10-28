# Contributing

## Start a task

1. Read the relevant SRS v1.2 sections and backlog acceptance notes. The SRS takes
   precedence. Keep unresolved TBDs explicit; agree on them before implementation.
2. Create a short-lived branch such as `feat/07-public-listings`.
3. Run `make install`; use `make web` and `make backend`, or Docker Compose.

## Where code belongs

- Page routing and page composition: `apps/web/src/routes`.
- Reusable UI primitives and layouts: `apps/web/src/lib/components`.
- Story #1 example content: `apps/web/src/lib/demo`. It is deliberately separate
  from future API-backed domain models. Remove fixtures from a feature when its
  live implementation is introduced; do not silently fall back to fixtures on errors.
- Versioned API routers: `apps/backend/src/adify_api/api/v1`.
- Configuration and cross-cutting services: `apps/backend/src/adify_api/core`.
- Add backend feature packages (accounts, listings, orders, etc.) with their
  implementation stories; keep HTTP, business rules, and persistence separate.
- Add database models and reviewed migrations with the first persistence story.

Use Svelte 5 runes, strict TypeScript, semantic HTML, and English UI copy. Reuse
existing CSS tokens and components. Maintain keyboard navigation, visible focus,
labels, descriptive links, and the mobile navigation disclosure pattern.

## Review and checks

Run `make check` and `make e2e`. Add meaningful tests for behavior and regression
risks. Browser coverage includes all six preview pages, 320/360/768/1440 px layouts,
and axe WCAG 2.1 Level A checks on Chromium, Firefox, and WebKit. Manually verify
the current and previous stable Chrome, Firefox, Edge, and Safari before marking
the browser-support requirement accepted (see `docs/story-01.md`).

Include the backlog item and SRS requirement IDs in each PR, with screenshots for
UI changes and commands/results for checks. Do not commit secrets, generated
builds, virtual environments, or dependencies. Commit lockfiles with dependency
changes. Keep unrelated edits out of the PR.

GitHub Actions runs web, backend, and container checks. A repository administrator
must configure branch protection to require `web`, `backend`, and `containers`
before merging; a workflow file alone cannot enforce branch protection.
