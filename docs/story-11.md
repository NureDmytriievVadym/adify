# Story ADY-011 — Filter and sort listings

## Source and scope

Sprint 2 board item, priority High.

Primary requirements: **FR-084** (price or budget, ad category, target audience),
**FR-085** (the listing owner's completed and currently disputed orders), **FR-086**
(sort by date created or price), **FR-082** (listing target audience), **FR-013**
(optional target audience on a listing).

The marketplace gains a filter sidebar for guests and signed-in users. Filters live
in the URL, so a filtered view can be linked, reloaded, and navigated with browser
back/forward.

## API

`GET /api/v1/listings` adds:

| Parameter             | Meaning                                                             |
| --------------------- | ------------------------------------------------------------------- |
| `price_min`           | Minimum price or budget in UAH, inclusive, up to 99,999,999.99      |
| `price_max`           | Maximum price or budget in UAH, inclusive                           |
| `delivery_max`        | Maximum estimated delivery time in days (1–365)                     |
| `age_min`             | Audience age overlap lower bound (0–120)                            |
| `age_max`             | Audience age overlap upper bound                                    |
| `country`             | Case-insensitive substring of the audience country                  |
| `socioeconomic`       | Case-insensitive substring of the socioeconomic background          |
| `traits`              | Repeatable trait values; matches listings declaring **any** of them |
| `owner_completed_min` | Owners with at least this many completed orders, 0 or more (FR-085) |
| `owner_disputed_max`  | Owners with at most this many currently disputed orders, 0 or more  |
| `sort`                | `newest` (default), `oldest`, `price_asc`, or `price_desc`          |

Audience values on a listing are optional. A missing minimum or maximum is treated
as open-ended: a listing targeted at “18+” matches a filter of 30–35, while a
listing limited to 18–24 does not. A listing with no audience is open to everyone,
so it matches any audience filter; a listing that declares an audience must match
the requested country, background, or trait.

`age_min > age_max`, `price_min > price_max`, negative owner counts, unknown sort
values, and malformed traits return `422`.

### Owner order history (FR-085)

The SRS names the two counts but not the comparison operators. The backlog's demo
scenario ("owners with ≥ 1 completed order and 0 disputed orders") fixes the
interpretation used here:

- `owner_completed_min` — an owner has at least this many orders in the `done`
  state. The default is no lower bound.
- `owner_disputed_max` — an owner has at most this many orders in the `disputed`
  state. `0` means “no current disputes”. The default is no upper bound.

A count includes every order where the listing's owner is either the customer or
the provider, because an owner can sell on an offering and buy through an ad
request. Only `done` counts as completed and only `disputed` counts as currently
disputed; canceled, rejected, and in-flight orders are excluded. The counts are
computed in the database per listing owner, so they always reflect current order
data and need no denormalized columns.

Listings now accept and return an optional `audience` object:

```json
{
  "age_min": 18,
  "age_max": 34,
  "country": "Ukraine",
  "socioeconomic": "Middle income",
  "traits": ["gamers", "students"]
}
```

Country, socioeconomic background, and traits are free text because FR-082 leaves
the permitted value lists TBD. The audience editor on `/listings/new` stores them.
Migration `0004` adds the nullable audience columns; `audience_traits` defaults to
an empty JSON array.

## Web

- A sticky desktop sidebar contains listing type, category, price range, delivery
  time, age range, country, socioeconomic background, traits, and the owner's
  completed and disputed order counts.
- Below 960 px the sidebar becomes a disclosure opened by **Filters**, with a
  visible count; it closes on **Apply**, the close button, or a successful apply.
- Applied filters appear as removable chips and a **Clear all** action; search text
  is preserved. The sort selector is separate from the filter form.
- The owner track-record chips read “Owner: 1+ completed orders” and “Owner: no
  disputed orders” (or “Owner: up to N disputed orders”).
- Invalid price or age ranges are caught in the browser before a request.
- Every state (loading, error, empty marketplace, no matches) has an explicit
  message and a way out.
- The listing page shows the target audience when one is declared.

The design is responsive and accessible: labelled controls, fieldset/legend groups,
visible focus, `aria-live` result counts, a disclosure button with `aria-expanded`
and `aria-controls`, and axe checks at 320 and 360 px.

## Open TBDs

- FR-082 permitted values for age bands, socioeconomic background, country, and
  traits (SRS v1.2 marks them TBD). Free text is the deliberate interim behavior.
- FR-085 does not define the comparison operators or whether counts should be
  displayed on cards. The minimum/maximum form above follows the backlog demo; the
  counts are not exposed in listing responses.
- Relevance ranking and search-result freshness (FR-016) remain TBD; filters and
  sorting are deterministic.
- Search and filtering run in the browser against the public API; server-rendered
  results await the internal API URL configuration.

## Automated acceptance

- `backend/tests/test_listings.py` covers audience persistence and validation,
  inclusive price bounds, inverted ranges, delivery limits, overlapping and
  open-ended age ranges, country/socioeconomic/trait matching, all four sort orders,
  combined search + filter queries, invalid traits, invalid sort values, and the
  FR-085 filters: minimum completed orders, maximum disputed orders, both together
  for the “≥ 1 completed and 0 disputed” scenario, counts from orders where the
  owner is the customer, and invalid negative or non-numeric counts.
- `frontend/tests/e2e/listings.spec.ts` covers applying price and delivery filters,
  validation, audience filters, owner completed/disputed filters with their chips,
  owner filter URL state after a reload, sort persistence across reloads, clearing
  filters while keeping the search, the mobile disclosure, URL state, empty states,
  and axe Level A on the filtered marketplace.
