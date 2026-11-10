# Story — Delete a listing with history-aware retention

## Source and scope

Epic: Marketplace listings. Backlog priority Must, estimate 3.

Primary requirement: **FR-020** (a listing owner deletes their listing; one with order
history is soft-deleted, one without is removed permanently). Use case step 3.6 and the
data requirements describe the same rule.

> As a listing owner, I want to delete my listing, so I can remove it from the
> marketplace.

## What happens on delete

| Listing                             | Result         | Database                    | Search and My listings |
| ----------------------------------- | -------------- | --------------------------- | ---------------------- |
| No orders                           | `removed`      | Row and attachments deleted | Gone                   |
| Any order, in any state (even done) | `soft_deleted` | Kept; `deleted_at` is set   | Hidden                 |

"Order history" means at least one order on the listing, whatever its state. A chat is
not order history: a listing with chats but no orders is removed, and its chats stay
with no listing reference (`ON DELETE SET NULL`, see [story #17](story-17.md)).

Paused and expired listings can be deleted too. Deleting a soft-deleted listing again
changes nothing and returns `soft_deleted`.

## Listing status

Migration `0011` adds `listings.deleted_at`. The derived status gains a fourth value,
which wins over the other three:

| Status         | Condition           | Reachable by link | New orders | Chats   |
| -------------- | ------------------- | ----------------- | ---------- | ------- |
| `soft_deleted` | `deleted_at` is set | Yes               | Refused    | Allowed |

A soft-deleted listing is a record only. Editing, pausing, resuming, and changing its
attachments return `409 listing_deleted`, and so does creating an order on it, from a
chat or otherwise. FR-026 still allows starting a chat from it, and its owner's phone
number can still be revealed. Orders keep their link to it, so opening an old order
still reaches the listing page.

## API

| Endpoint                       | Result                                                          |
| ------------------------------ | --------------------------------------------------------------- |
| `DELETE /api/v1/listings/{id}` | `200 {"result": "removed"}` or `200 {"result": "soft_deleted"}` |
| `GET /api/v1/listings`         | Leaves out soft-deleted listings                                |
| `GET /api/v1/listings/mine`    | Leaves out soft-deleted listings                                |
| `GET /api/v1/listings/{id}`    | `200` with `status: "soft_deleted"`; `404` once removed         |

Like pausing, deleting is open to any signed-in owner, so a listing can always be
withdrawn.

| Status | `type`              | Cause                                            |
| ------ | ------------------- | ------------------------------------------------ |
| 401    | `not_authenticated` | No valid access token                            |
| 403    | `not_listing_owner` | Someone else's listing                           |
| 404    | `listing_not_found` | Unknown or already removed listing               |
| 409    | `listing_deleted`   | Changing, or ordering on, a soft-deleted listing |

## Frontend

- The owner's listing page has a quiet **Delete listing** button below the other
  controls. It asks for confirmation in place, explaining both outcomes, before
  anything is sent.
- After deleting, the owner lands on **My listings** with a notice that says which of
  the two outcomes happened.
- A soft-deleted listing shows a **Deleted** badge. Its owner sees a note instead of
  the edit, pause, and delete controls; other users see that it takes no new orders
  but can still start a chat. Chats show the same badge.

## How to demo

1. Sign in as a demo account (`just seed`), create a listing, and delete it from its
   page: it disappears from search and from the `listings` table.
2. Create an order on another listing (from a chat), then delete that listing: it is
   hidden from search and My listings, and its row stays with `deleted_at` set.
3. Open the old order: the listing link still opens the listing, marked **Deleted**.

## Tests

- `backend/tests/test_listing_delete.py`: removal with attachments, removal with a
  chat, soft delete with an awaiting-payment or done order, the blocked actions,
  deleting twice, paused and expired listings, and ownership.
- `frontend/tests/e2e/listing-delete.spec.ts`: confirmation and cancel, both outcomes,
  the owner's and others' view of a soft-deleted listing, and an axe check.
