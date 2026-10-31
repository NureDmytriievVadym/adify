# Story ADY-007 — Browse and search public listings

## Source and scope

Sprint 1 board item, priority High, estimate 8.

Primary requirements: **FR-015** (view listings), **FR-016** (search listings),
**UI-003** (guest browsing), with listing details and placement specifications
per FR-015 / FR-118. Filters by price, target audience, owner order history, and
sorting remain **ADY-011** (FR-084–FR-086); category and type are treated here as
basic browse navigation, not the Sprint 2 filter set.

Guests and signed-in users can open the marketplace, browse the newest public
listings, search by a word, narrow by type or category, and open any listing
without signing in. Listing details never include the owner's email address or
phone number.

## API

`GET /api/v1/listings` now accepts:

| Parameter  | Behavior                                                       |
| ---------- | -------------------------------------------------------------- |
| `q`        | 1–100 characters; case-insensitive; surrounding spaces ignored |
| `type`     | `request` or `offer`                                           |
| `category` | one of the six FR-014 slugs                                    |
| `limit`    | 1–50, default 20                                               |
| `offset`   | 0 or more; combined with `total` for paging                    |

Search matches the listing **title, description, or category slug**. It is a
literal substring match: `%`, `_`, and `\` are escaped and are not SQL wildcards.
Results stay newest-first and are not relevance-ranked. An empty page returns
`{"items": [], "total": 0}`.

This is the provisional interpretation of FR-016, whose exact matching and ranking
behavior is still TBD in SRS v1.2. It is intentionally simple and deterministic;
relevance ranking can be added in a later refinement without changing the endpoint.

## Web

- `/listings` is driven by URL parameters `q`, `type`, and `category`, so a search
  result is shareable and survives reloads. Search runs 300 ms after typing and
  immediately on submit; the field and result count are announced accessibly.
- The page handles loading, request failure, empty marketplace, and no-match
  states. Clearing the search or category returns to the full feed.
- The home page shows the three newest public listings; when the marketplace is
  empty it links to the marketplace instead of presenting invented listings.
- A real listing opens by UUID at `/listings/<id>` with description, placement
  specification, attachments, owner display name, and price/budget in UAH.
- A guest who selects **Reveal phone number** is sent to `/sign-in`. The actual
  phone reveal, verification gate, and chat remain ADY-016/ADY-017.
- Design fixtures remain only for the read-only sample order and its linked sample
  listing; they are no longer mixed into the public marketplace feed.

## Open TBDs

- Precise FR-016 matching, ranking, pagination UI size, and search-result freshness
  are not finalized in SRS v1.2.
- Filters by price/budget, audience, owner completed/disputed orders, and sorting
  are ADY-011.
- Search is currently client-side; server-rendering public results depends on the
  future internal API URL configuration and is not required by this story.

## Automated acceptance

- `backend/tests/test_listings.py`: new cases cover title, description, and category
  matching; case folding and whitespace; literal `%`/`_`/`\`; empty results; paging
  with `total`; type combination; invalid length; and guests remaining anonymous.
- `frontend/tests/e2e/listings.spec.ts`: guest search through the URL, debounced
  input, clearing, empty state, category navigation, live single-column cards at
  360 px, detail navigation, placement specification, guest phone prompt, and axe
  Level A checks.
- `foundation.spec.ts`: the public pages remain English, responsive at 320/360/768/
  1440 px, and accessible with the live feed unavailable.
