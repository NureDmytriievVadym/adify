# Foundation verification — 2026-10-28

## Executed checks

- `make check`: Prettier, ESLint, Svelte/TypeScript, Ruff, pytest, production build.
- Playwright: 27 tests across Chromium, Firefox, and WebKit. Responsive checks
  cover six pages at 320, 360, 768, and 1440 px; axe checks use the `wcag2a` and
  `wcag21a` tags. Mobile navigation, keyboard skip link, single-column cards,
  disabled protected actions, and 404 navigation are covered.
- `docker compose up --build --wait`: web, backend, PostgreSQL 18, and Redis
  started and passed container health checks.
- The running API returns `{"status":"ok"}` at `/api/v1/health` and publishes
  `/docs` and `/openapi.json`.
- Home and example-order screenshots were reviewed at desktop and 360 px.

The Linux host did not have all WebKit system libraries and could not install
them without sudo, so the browser suite ran in the official Playwright image:

```sh
docker run --rm --ipc=host \
  --user "$(id -u):$(id -g)" \
  -v "$PWD:/work" -w /work \
  mcr.microsoft.com/playwright:v1.64.1-noble npm run test:e2e
```

This uses the dependencies already installed by `npm ci` in the repository and
starts a separate built preview server inside the test container. It does not
require stopping the Compose website.

## Acceptance still requiring manual verification

Current and previous branded Chrome, Firefox, Edge, and Safari releases, plus
manual screen-reader checks, are listed in `story-01.md`. Playwright engines and
axe do not establish full browser or accessibility conformance by themselves.

## Dependency note

At initialization, `npm audit` reports four low-severity entries arising from
the same transitive `deepmerge` advisory (GHSA-gcqx-w48m-w2h4) through the Svelte
build toolchain. No patched upstream release is currently available. Keep this
visible during dependency maintenance; the suggested automatic downgrade to
pre-1.0 SvelteKit is not appropriate for this baseline.
