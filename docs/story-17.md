# Story #17 — Start a chat from a listing

## Source and scope

Epic: Contact and chat. Backlog priority Must, estimate 5 (ADY-017).
Primary requirements: FR-026, FR-027, FR-087, SRS §3.2.3.5, §3.4.3.

> As a verified user, I want to start a chat from a listing page, so I can discuss the
> listing with its owner.

A verified user starts a chat with the owner of an active, paused, or expired listing.
Sending messages and files (FR-028–FR-030) is ADY-018; creating an order from a chat
(FR-031) is ADY-019; moderator access (FR-032) belongs to moderation.

## Rules

| Situation                                               | Result                              |
| ------------------------------------------------------- | ----------------------------------- |
| Verified customer on an offer, or provider on a request | `201`, a new chat                   |
| The same user starts the same chat again                | `200`, the existing chat            |
| Active, paused, or expired listing                      | Allowed (a pause only stops orders) |
| The owner on their own listing                          | `403 own_listing`                   |
| Customer with customer, or provider with provider       | `403 same_role_chat`                |
| Email or phone not verified                             | `403 verification_required`         |
| Not signed in                                           | `401`                               |
| Unknown or permanently deleted listing                  | `404 listing_not_found`             |

Soft deletion is ADY-014. Once it exists, a soft-deleted listing must still be found by
the chat endpoint so the chat can start.

## API

| Endpoint                           | Result                                                                              |
| ---------------------------------- | ----------------------------------------------------------------------------------- |
| `POST /api/v1/listings/{id}/chats` | `201`/`200` chat, see the rules above                                               |
| `GET /api/v1/chats`                | The signed-in user's chats, newest first                                            |
| `GET /api/v1/chats/{id}`           | One chat; `403 not_chat_participant` for anyone else (FR-027), `404 chat_not_found` |

A chat response holds the listing summary (id, title, type, status, or `null` once the
listing is permanently deleted) and the other participant's public profile: id, display
name, and role. Email addresses and phone numbers are never included (FR-087).

## Persistence

Migration `0008` adds `chats`: listing, customer, provider, and creation time, unique per
listing and pair of participants. Deleting a listing sets `listing_id` to `NULL`, so the
conversation stays with both participants (SRS §3.4.3 "related listing, if applicable").
`just seed --reset` removes chats of the demo accounts.

## Web

**Start chat** on a listing page opens `/chats/{id}`; it stays available on paused and
expired listings, whose note now says the owner can still be contacted. `/chats` lists the
user's conversations and is linked as **Chats** in the header. The chat page shows the
other participant, links back to the listing with its state, and an empty history until
ADY-018 adds sending.

## Change to ADY-013

ADY-013 blocked starting a chat on paused and expired listings (`409`). FR-026 and the
ADY-017 acceptance allow it, so the chat endpoint no longer calls `ensure_accepts_orders`;
order creation keeps that guard.

## Automated acceptance

`backend/tests/test_chats.py` covers starting chats on offers and requests, reusing a
chat, paused and expired listings, own-listing and same-role refusals, unknown listings,
both participants' chat lists, participant-only access, and chats whose listing was
deleted. Playwright covers starting a chat from active and paused listings, the chat
list, a deleted listing's chat, refused access, and guests, with axe on the chat list.
