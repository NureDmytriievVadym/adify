# Story #16 — Reveal a listing owner's phone number

## Source and scope

Epic: Contact and chat. Backlog priority Must, estimate 3 (ADY-016).
Primary requirements: FR-024, FR-025, FR-087, UI-004, FR-008.

> As a verified user, I want to reveal a listing owner's phone number only when I request
> it, so I can contact them by phone if needed.

The endpoint and the button arrived with email and phone verification (story #5, PR #10).
This story completes the guest path and covers every acceptance step with tests.

## Rules

| Who                                  | Result                                                        |
| ------------------------------------ | ------------------------------------------------------------- |
| Guest                                | Button links to sign-in and returns to the listing; API `401` |
| Signed in, email or phone unverified | `403 verification_required`, shown with **Verify now**        |
| Verified                             | `200 {"phone": "+380…"}`: the phone number and nothing else   |

The phone number is never part of listing pages, the marketplace, or listing API
responses; it appears only after the explicit **Reveal phone number** action (FR-025).
Email addresses are never shown to other users anywhere (FR-087). There is no limit on
reveals per user or per listing in the MVP. Paused and expired listings still reveal, as
FR-024 sets no listing-state condition.

## API

`POST /api/v1/listings/{id}/phone-reveal` → `200 {"phone": …}`, `401`, `403
verification_required`, or `404 listing_not_found`.

## Web

Guests follow `/sign-in?next=/listings/{id}` from **Reveal phone number** and **Start chat**
and land back on the listing after signing in. Sign-in accepts only same-site paths in
`next`; anything else goes to the account page, so the parameter cannot redirect to another
site.

## Automated acceptance

`backend/tests/test_phone_reveal.py` covers guests, unverified and verified users, the
response holding only the phone number, listing and marketplace responses without contacts,
unlimited reveals, paused and expired listings, and unknown listings. Playwright covers the
guest sign-in round trip, the unverified block, the reveal on request without any email on
the page, and a refused off-site `next` address.
