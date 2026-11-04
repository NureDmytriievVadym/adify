# Story — Pause and resume a listing

## Source and scope

Epic: Marketplace listings. Backlog priority Must, estimate 3.

Primary requirements: **FR-018** (the owner pauses and resumes a listing) and
**FR-019** (a listing expires; an expired listing cannot be resumed).

> As a listing owner, I want to pause and resume my listing, so I can control whether
> it is available for new orders.

## Listing status

Every listing has a status derived from two columns added by migration `0007`:

| Status    | Condition                      | Marketplace and search | New orders |
| --------- | ------------------------------ | ---------------------- | ---------- |
| `active`  | Not paused and not expired     | Listed                 | Accepted   |
| `paused`  | `paused_at` is set             | Hidden                 | Refused    |
| `expired` | `expires_at` has passed (wins) | Hidden                 | Refused    |

A listing expires **30 days** after it is published (`ADIFY_LISTING_LIFETIME_DAYS`,
default `30`). Migration `0007` sets `expires_at = created_at + 30 days` for existing
listings. Pausing does not stop the clock. Paused and expired listings stay reachable
by their link, where they are clearly marked, and their owner still sees them in
**My listings**. A paused or expired listing can still be edited.

## New orders

Chat and order creation do not exist yet (the chat endpoint answers `501`, and the
`orders` table from FR-017 has no API). Both stories share one guard,
`ensure_accepts_orders`:

- **Now:** `POST /api/v1/listings/{id}/chats` is where a conversation, and from it an
  order, begins. It returns `409 listing_paused` or `409 listing_expired` for a
  listing that is not active, after the existing FR-026 checks.
- **Later:** order creation, including from an existing chat, must call the same guard.

Existing orders are not affected by a pause.

## API

| Endpoint                            | Result                                                        |
| ----------------------------------- | ------------------------------------------------------------- |
| `POST /api/v1/listings/{id}/pause`  | `200` owner view with `status: "paused"`; any signed-in owner |
| `POST /api/v1/listings/{id}/resume` | `200` owner view with `status: "active"`; verified owner      |
| `GET /api/v1/listings`              | Active listings only                                          |
| `GET /api/v1/listings/mine`         | All of the owner's listings, with their status                |

Every listing response now includes `status` and `expires_at`. Pausing a paused
listing or resuming an active one changes nothing and returns `200`. Pausing is open
to any signed-in owner, so a listing can always be withdrawn. Resuming puts the
listing back in front of other users, so it needs verified contacts, like publishing
it (FR-008).

| Status | `type`                  | Cause                                               |
| ------ | ----------------------- | --------------------------------------------------- |
| 401    | `not_authenticated`     | No valid access token                               |
| 403    | `not_listing_owner`     | Someone else's listing                              |
| 403    | `verification_required` | Resuming without a verified email address and phone |
| 404    | `listing_not_found`     | Unknown id                                          |
| 409    | `listing_expired`       | Resuming or pausing an expired listing (FR-019)     |
| 409    | `listing_paused`        | Starting a chat about a paused listing (FR-018)     |

## Web

- The listing page shows a **Paused** or **Expired** badge next to the category.
- The owner sees **Pause listing** or **Resume listing** next to **Edit listing**, with
  the state explained: “Active until …”, “Paused: hidden from the marketplace and not
  accepting new orders. You can resume it until …”, or “Expired on …. An expired
  listing cannot be resumed.” For an expired listing the button is disabled. If the
  listing expires while the page is open, the API's message is shown and the page
  reloads the listing to show it as expired.
- Other users and guests see **Start chat** disabled on a paused or expired listing,
  with the reason. Revealing the phone number is unaffected.
- **My listings** marks paused and expired cards.

## Demo (acceptance)

1. `just seed`, sign in as `digital.daily@demo.adify.app` / `AdifyDemo123`.
2. Open “A little screen space for your next big idea” → **Pause listing**: it shows
   **Paused** and leaves the marketplace. Signed in as `olena.marchenko@demo.adify.app`,
   **Start chat** is disabled; the API returns `409 listing_paused`.
3. **Resume listing**: it is listed again and a chat can be started (the API answers
   `501 chat_not_available`, which means every order check passed).
4. Open “A sponsored story in our weekly design newsletter”, seeded as paused and then
   expired: **Resume listing** is disabled, and the API returns `409 listing_expired`.

## Open TBDs

- The SRS lifetime of a listing (30 days is the interim default) and whether an owner
  can renew an expired listing.
- Whether a pause should stop the expiry clock.
- Notifying the other party of an existing order when a listing is paused.
- Expiry is computed when a listing is read; a scheduled job is not needed until
  expiry must trigger notifications.

## Automated acceptance

- `backend/tests/test_listings.py` (FR-018/FR-019 section): the configured lifetime,
  pause and resume with marketplace visibility and the chat guard, repeated pause and
  resume, editing while paused, expired listings refusing resume, pause, and chats,
  and who may pause or resume.
- `backend/tests/test_seed.py`: one expired demo listing, all others active.
- `frontend/tests/e2e/listing-state.spec.ts`: pausing and resuming from the listing
  page, the disabled chat for other users and guests, an active listing still taking
  chats, the disabled resume of an expired listing, a listing that expired while the
  page was open, **My listings** badges, and axe Level A at 360 px without horizontal
  overflow.
