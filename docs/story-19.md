# Story #19 — Create an order in chat

## Source and scope

Epic: Order workflow. Backlog priority Must, estimate 8 (ADY-019).
Primary requirements: FR-031, FR-033–FR-037, FR-118, FR-008 (verified users), SRS §3.4.4.

> As a listing owner, I want to create an order in a chat, so the parties can formalize
> their agreement.

The listing owner, customer or provider, records an order in a chat with the other
participant: details, agreed price in UAH, an optional deadline, and optional work stages
with their own deadlines. The order starts **awaiting payment**. Paying (ADY-020),
starting work (ADY-021), stages in progress and evidence (ADY-022), review (ADY-023),
cancelling (ADY-025), and rejecting (ADY-026) build on it.

## Rules

| Situation                                                                                                                        | Result                                   |
| -------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| Verified listing owner, active listing                                                                                           | `201`, state `awaiting_payment`          |
| The other participant                                                                                                            | `403 not_listing_owner`                  |
| Anyone outside the chat                                                                                                          | `403 not_chat_participant`               |
| Paused or expired listing (FR-018, FR-019)                                                                                       | `409 listing_paused` / `listing_expired` |
| The chat's listing was permanently deleted                                                                                       | `409 listing_deleted`                    |
| Email or phone not verified                                                                                                      | `403 verification_required`              |
| Empty details, price not above 0, past deadlines, a stage deadline after the order deadline, more than 10 stages, unknown fields | `422`                                    |

A chat may hold several orders; each needs the owner's action. The customer and provider
come from the chat, which already guarantees one of each (FR-036).

## Technical-requirements snapshot (FR-118)

At creation the order stores `requirements`: the listing type and category, its
specification lines, and `has_requirements`. For an ad request without requirements that
flag is `false` and `specs` is empty — the explicit record FR-118 asks for. Later edits to
the listing never change an existing order's snapshot.

## API

| Endpoint                         | Result                                              |
| -------------------------------- | --------------------------------------------------- |
| `POST /api/v1/chats/{id}/orders` | `201` order, see the rules above                    |
| `GET /api/v1/chats/{id}/orders`  | The chat's orders for its two participants          |
| `GET /api/v1/orders`             | The signed-in user's orders as customer or provider |
| `GET /api/v1/orders/{id}`        | One order; `403 not_order_participant` for others   |

An order response holds the state, details, `price_uah`, deadline, stages, the snapshot,
the listing summary, the chat id, `is_listing_owner` for the viewer, and the public
profiles of the customer and provider. Contacts are never included (FR-087).

## Persistence

Migration `0010` renames the order states to the SRS names (`pending` → `awaiting_payment`,
`completed` → `done`, `cancelled` → `canceled`; adds `paid`, `in_review`, `rejected`), adds
`chat_id`, `owner_id`, `details`, `price`, `deadline`, and `requirements` to `orders`, and
creates `order_stages`. Orders that existed before (the demo order) take their listing's
owner, price, and specification. An active order is one in any state other than canceled,
rejected, or done (FR-017), so an order awaiting payment already locks the listing category.

## Web

The chat page has an **Orders** section for both participants. The listing owner sees
**Create order** while the listing is active and a short explanation when it is paused or
expired; the other participant sees no button. The form takes details, price, an optional
deadline, and up to ten stages, checks the same rules before sending, and opens the new
order. `/orders/{id}` shows the state, participants, details, stages, and the snapshot,
including “No technical requirements” for an ad request without any.

## Automated acceptance

`backend/tests/test_orders.py` covers creation with two stages, both participants' views,
the offer snapshot, the explicit empty snapshot of an ad request, an unchanged snapshot
after a listing edit, refusals for the other party, outsiders, paused, expired, and deleted
listings, unverified owners, validation, optional stages, and the category lock. The
Playwright suite creates an order with two stages, checks validation, the other party's
view, a paused listing, and an ad request without requirements, with axe on the form and
the order page.
