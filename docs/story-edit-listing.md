# Story — Edit listing details

## Source and scope

Epic: Marketplace listings. Backlog priority Must, estimate 5.

Primary requirement: **FR-017** (the owner edits a listing; the category cannot change
while an order is active, every other field stays editable). Listing fields follow
ADY-008–ADY-010 and the audience of ADY-011 (FR-082).

> As a listing owner, I want to edit my listing, so I can keep its information current.

## Orders foundation

FR-017 depends on whether a listing has an **active order**, but orders could not be
created before this story. Migration `0006` adds a minimal `orders` table (listing,
customer, provider, status, created time) and nothing else: there is no order API yet.
The order stories will add the remaining columns, transitions, and endpoints.

| Status        | Active | Reason                                   |
| ------------- | ------ | ---------------------------------------- |
| `pending`     | yes    | Agreed, work not started                 |
| `in_progress` | yes    | Work under way                           |
| `disputed`    | yes    | Not closed until the dispute is resolved |
| `completed`   | no     | Closed                                   |
| `cancelled`   | no     | Closed                                   |

`just seed` creates one `in_progress` order (Olena Marchenko ↔ Digital Daily) on the
offering “Your brand, front and centre on a design journal”, so the rule can be
demonstrated without database access. `just seed --reset` removes it with the other
demo rows.

## API

| Endpoint                         | Result                                                         |
| -------------------------------- | -------------------------------------------------------------- |
| `PATCH /api/v1/listings/{id}`    | `200` owner view; verified owner only                          |
| `GET /api/v1/listings/mine/{id}` | `200` owner view: the listing plus `locked_fields`; owner only |

The owner view is a regular listing with `locked_fields`, currently `[]` or
`["category"]`. Public listing responses are unchanged and never expose order data.

`PATCH` is a partial update: omitted fields keep their value. Field rules match
creation (ADY-008/009). `specs` and `audience` replace the stored value as a whole;
`audience: null` or `{}` clears it. An ad request's amount is `budget_uah` and its
optional `delivery_days` can be cleared with `null`; an offering's amount is
`price_uah` and its delivery time is required. Sending the unchanged category is not a
change, so a form can always send every field. A failed rule saves nothing.

| Status | `type`                                  | Cause                                             |
| ------ | --------------------------------------- | ------------------------------------------------- |
| 401    | `not_authenticated`                     | No valid access token                             |
| 403    | `verification_required`                 | Email or phone not verified (FR-008, as creation) |
| 403    | `not_listing_owner`                     | Someone else's listing                            |
| 404    | `listing_not_found`                     | Unknown id                                        |
| 409    | `category_locked`                       | Category change while an order is active (FR-017) |
| 422    | `amount_field_mismatch`                 | `price_uah` on a request or `budget_uah` on offer |
| 422    | `delivery_required`                     | `delivery_days: null` on an offering              |
| 422    | `null_not_allowed` and validation types | `null` for a required field, or invalid values    |

Field errors carry `loc: ["body", "<field>"]`, so clients can show them next to the
field.

## Web

- `/listings/<id>/edit` loads the owner view and pre-fills the same fields as the
  create form (category, title, description, price or budget, delivery time, target
  audience, specification). Both forms share `ListingFields.svelte`.
- With an active order the category select is disabled and explained: “This listing
  has an active order, so it stays in …”. If an order becomes active after the form
  opened, the `409` message is shown at the top, the stored category is restored, and
  the other edits stay in the form to save again.
- Existing attachments can be marked for removal (and kept again) and new files
  added, with the five-file limit counted across both. Fields are saved first; file
  failures are listed afterwards without losing the saved fields.
- After saving, the owner returns to the listing page with a “Your changes are saved.”
  status. The listing page shows **Edit listing** to its owner instead of the contact
  actions, and **My listings** has an **Edit** link on every card.
- Guests are asked to sign in, unverified accounts to verify, other users see “This is
  not your listing”; sample listings under readable slugs return 404.

## Demo (acceptance)

1. `just seed`, sign in as `digital.daily@demo.adify.app` / `AdifyDemo123`.
2. **My listings → Edit** on “A little screen space for your next big idea”: change the
   title and price, save; the listing page shows them.
3. **Edit** on “Your brand, front and centre on a design journal” (seeded active
   order): the category is locked with a message. The API returns `409
category_locked` for a direct change.
4. Change its description and save: allowed.

## Open TBDs

- The order lifecycle and which states count as active are provisional until the
  order stories; `ACTIVE_ORDER_STATUSES` is the single place to change them.
- Whether other fields (for example price) should notify the order counterparty when
  edited during an active order; FR-017 only restricts the category.
- Edit history, moderation of edits, and an “edited” marker on listings.
- The listing row is not locked while an order is created; the order story should
  check the category rule in the same transaction.

## Automated acceptance

- `backend/tests/test_listings.py` (FR-017 section): title and price edits visible
  publicly, request budget and clearing delivery, offering delivery required, amount
  field per type, category change without an order, category locked for every active
  status with nothing saved, other fields editable with an active order, closed orders
  not locking, spec and audience replacement and clearing, empty edit, invalid values
  and `null`s, owner/verified/guest access, unknown listing, and the owner view's
  `locked_fields`.
- `backend/tests/test_seed.py`: the demo order is idempotent, locks only its listing,
  and is removed by `--reset`.
- `frontend/tests/e2e/edit-listing.spec.ts`: edit and see changes, locked category
  with editable description, a `409` after the form opened, validation, attachment
  removal and upload, edit entry points, other users, guests, sample listings, and axe
  Level A at 360 and 1440 px without horizontal overflow.
