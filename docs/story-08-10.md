# Stories ADY-008, ADY-009, ADY-010 — Listings

## Source and scope

Sprint 1 board items, priority High:

- **ADY-008** Create customer ad-request listing
- **ADY-009** Create provider ad-offering listing
- **ADY-010** Add listing details and attachments

The SRS and the acceptance notes of these tickets were not available while this was
written, so the behavior below is an interpretation of the ticket titles, FR-014
(the six categories) and the existing preview listings. Every assumption is listed
under **Open TBDs** and should be confirmed against SRS v1.2.

A signed-in customer publishes an **ad request** (what they want to buy, with a
budget); a signed-in provider publishes an **ad offering** (a placement, with a
price and delivery time). Both can describe the placement with specification lines
and attach files, and anyone can open the result at `/listings/<id>`.
Search and browsing live listings stay with story #7; editing, closing and
moderating listings are not part of these tickets.

## API

| Endpoint                                                | Result                                                         |
| ------------------------------------------------------- | -------------------------------------------------------------- |
| `POST /api/v1/listings/requests`                        | `201` listing; customers only (ADY-008)                        |
| `POST /api/v1/listings/offers`                          | `201` listing; providers only (ADY-009)                        |
| `GET /api/v1/listings?type=&category=&limit=&offset=`   | `200` `{items, total}`, newest first, public; `limit` 1–50     |
| `GET /api/v1/listings/mine`                             | `200` `{items, total}` of the signed-in account's listings     |
| `GET /api/v1/listings/{id}`                             | `200` public details with specification and attachments        |
| `POST /api/v1/listings/{id}/attachments?filename=…`     | `201` attachment; owner only; the body is the raw file         |
| `GET /api/v1/listings/{id}/attachments/{attachment}`    | The file, served inline with `X-Content-Type-Options: nosniff` |
| `DELETE /api/v1/listings/{id}/attachments/{attachment}` | `204`; owner only                                              |

Request body (`budget_uah` and `price_uah` are decimal strings or numbers with at
most two decimals, up to 99,999,999.99; amounts are returned as `price_uah` strings):

| Field           | Request (customer)                     | Offer (provider)     |
| --------------- | -------------------------------------- | -------------------- |
| `category`      | one of the six slugs                   | one of the six slugs |
| `title`         | 5–120 characters                       | 5–120 characters     |
| `description`   | 20–5,000 characters                    | 20–5,000 characters  |
| `budget_uah`    | required, > 0                          | —                    |
| `price_uah`     | —                                      | required, > 0        |
| `delivery_days` | optional, 1–365                        | required, 1–365      |
| `specs`         | up to 10 `{label (≤60), value (≤300)}` | same                 |

Errors use the shared `{"detail": [{"loc", "msg", "type"}]}` shape:

| Status | `type`                                      | Cause                                          |
| ------ | ------------------------------------------- | ---------------------------------------------- |
| 401    | `not_authenticated`                         | No valid access token                          |
| 403    | `role_not_allowed`                          | A provider creating a request, or the reverse  |
| 403    | `not_listing_owner`                         | Changing attachments of someone else's listing |
| 404    | `listing_not_found`, `attachment_not_found` | Unknown id                                     |
| 409    | `too_many_attachments`                      | More than 5 files on one listing               |
| 413    | `attachment_too_large`                      | A file over 10 MB                              |
| 415    | `attachment_type_not_allowed`               | Not JPG, PNG, GIF, WebP, MP4, or PDF           |
| 422    | `attachment_empty` and validation types     | Empty file, or invalid fields                  |

The file type is detected from the first bytes of the upload; the client's
`Content-Type` and the file name are not trusted. The original name is stored only
as a label (path parts are stripped); files are stored under a random id. Listing
details never include the owner's email address or phone number.

## Persistence

Migration `0003` adds `listings` (owner, type, category, title, description,
`price`, `delivery_days`, `specs` JSON) and `listing_attachments` (metadata). The
bytes are written to `ADIFY_STORAGE_DIR` (default `storage`, a Docker volume
mounted at `/app/storage`), limited by `ADIFY_MAX_ATTACHMENT_BYTES` and
`ADIFY_MAX_ATTACHMENTS`.

## Web

- `/listings/new` shows a customer a request form (budget, optional desired delivery
  time) and a provider an offering form (price, delivery time). Both have a category
  select, title, description, a specification editor and a file picker. Errors are
  shown per field and the first one receives focus. The listing is created first, then
  the files are uploaded one by one; if an upload fails the listing stays published
  and the failed files are listed. The header and the account page link to the form.
- `/listings` shows the latest published listings above the six labeled examples, with
  an All / Offers / Ad requests filter; `/listings/mine` (header and account page) shows
  the signed-in user's own listings. Search, category filters and sorting remain story #7,
  which should also remove the example fixtures.
- `/listings/<id>` loads the listing from the API in the browser and shows the
  category, description, specification, price or budget in UAH, delivery time, owner
  display name and attachments (images inline, PDF/MP4 as links). The six example
  listings under readable slugs are unchanged. Chat and phone actions stay disabled.

## Open TBDs

- Acceptance criteria and field lists of ADY-008/009/010 against SRS v1.2: field
  names, limits, whether a request needs a delivery time, per-category fields.
- Email/phone verification is not implemented, so it is not required to create a
  listing yet (the account page says it will be).
- Moderation, a draft/published status, editing, closing and deleting listings.
- Attachment rules: allowed types, sizes (the preview examples mention up to 500 MB
  videos), malware scanning, and storage outside the API's local disk.
- Whether listing details of a suspended or banned owner stay public.

## Automated acceptance

`backend/tests/test_listings.py` covers both creation flows and their role checks,
authentication, field validation, public details without contacts, upload and
download, type detection, rejected and oversized files, the attachment limit, owner-only
changes, deletion, and unknown ids. `frontend/tests/e2e/listings.spec.ts` creates a
request and an offering against a mocked API, checks browser validation and attachment
rules, the guest prompt, the listing page and a missing listing, with axe checks.
