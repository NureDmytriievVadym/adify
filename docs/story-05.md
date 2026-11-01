# Story #5 — Verify email and phone

## Source and scope

Backlog: **Accounts and verification**, priority Must, estimate 8.
Primary requirements: FR-004, FR-005, FR-006, FR-008, SW-002, SW-003, FR-024–FR-026
(the gated actions), SRS §3.3.2 steps 3.4–3.5.

A registered user verifies their email address and phone number with six-digit
codes. Until both are verified, revealing a phone number, starting a chat, and
creating a listing are refused with an explanation; afterwards they are allowed.
Orders, also gated by FR-008, do not exist yet and will use the same check.

## API

| Endpoint                                                  | Result                                                             |
| --------------------------------------------------------- | ------------------------------------------------------------------ |
| `GET /api/v1/accounts/me/verification`                    | `200` per channel: verified, destination, `code_sent`, `resend_in` |
| `POST /api/v1/accounts/me/verification/{channel}/code`    | `202`; sends a code by email or SMS                                |
| `POST /api/v1/accounts/me/verification/{channel}/confirm` | `200` updated account; body `{"code": "123456"}`                   |
| `POST /api/v1/listings/{id}/phone-reveal`                 | `200` `{"phone": ...}`, the owner's only shown detail              |
| `POST /api/v1/listings/{id}/chats`                        | FR-026 checks; `501 chat_not_available` until chat                 |

`{channel}` is `email` or `phone`. Registration emails the first code
automatically; a mail outage does not fail registration. Creating requests and
offerings, revealing phones, and starting chats return `403 verification_required`
with a message naming what is still unverified.

| Status | `type`                          | Cause                                            |
| ------ | ------------------------------- | ------------------------------------------------ |
| 400    | `code_incorrect`                | Wrong code; the message says how many tries left |
| 400    | `code_attempts_exceeded`        | Fifth wrong code; the code is invalidated        |
| 400    | `code_expired`, `code_used`     | Older than 15 minutes, or already replaced       |
| 400    | `code_not_requested`            | No code yet, or the address/number has changed   |
| 409    | `already_verified`              | Nothing to verify                                |
| 429    | `resend_too_soon`               | A new code within 60 s (`Retry-After` header)    |
| 503    | `delivery_failed`               | The SMTP server refused or is unreachable        |
| 403    | `verification_required`         | A gated action before both verifications         |
| 403    | `same_role_chat`, `own_listing` | Chat rules from FR-026                           |

## Codes

Codes are six random digits, valid for 15 minutes, with five attempts and a new
code allowed after 60 seconds; a new code replaces the previous one. Only an
HMAC-SHA256 of the code is stored, keyed with the server secret, because six digits
are trivial to brute-force from a plain hash. Each code records the address or
number it was sent to and stops counting when that changes (FR-006). The account's
`email_verified` and `phone_verified` flags persist until then.

## Delivery

Email uses SMTP. Locally every message goes to Mailpit (http://localhost:8025), so
nothing reaches real inboxes. For the Gmail demo (SW-002), set the `ADIFY_SMTP_*`
variables listed in `.env.example` to `smtp.gmail.com:587` with STARTTLS and a
Google Workspace app password; no code changes are needed.

The SMS vendor is TBD (SW-003). Until it is chosen, a development outbox logs each
SMS and mails it to Mailpit as "SMS to +380…". A real vendor replaces
`adify_api.core.sms.send_sms`.

## Web

`/account#verification` shows each contact with its status. A contact without a
usable code offers one button ("Email me a code" / "Text me a code"); once a code
is out, the page shows a code field with **Verify** and a "Send a new code" link
that counts down the 60-second wait. Both states come from the status endpoint,
so they survive reloads, and the email link opens the page with the code filled in.

Listing pages enable **Reveal phone number** and **Start chat** for signed-in users and show
the API's explanation with a **Verify now** link when refused. `/listings/new`
explains that verification is needed instead of showing the form. Demo accounts
from `just seed` are created already verified.

## Open TBDs

- SMS vendor, sender name, and cost limits (SW-003).
- Rate limits per account, phone number, and IP beyond the 60-second resend wait
  and five attempts per code (§3.2.1.5).
- Re-verification after account-security events (FR-006).
- Changing email or phone: not implemented yet; codes already stop counting when
  the stored address or number changes.

## Automated acceptance

`backend/tests/test_verification.py` covers the registration email and link,
email and SMS confirmation, wrong-code countdown and lockout, malformed, expired,
replaced, and unrequested codes, contact changes, the resend wait, keyed hashing,
sign-in requirement, delivery failures, the three gated actions before, halfway,
and after verification, and FR-026 chat rules. The Playwright suite blocks and
then allows the actions in the browser, shows the wrong-code error, fills the code
from the email link, and runs axe on the verification section.

## Manual acceptance (local)

Run on the local stack with Mailpit; all five steps passed:

1. Registered a customer; the code email appeared in Mailpit and was entered.
2. Requested an SMS code; it appeared in Mailpit as "SMS to +380…" and was entered.
3. Before verification, Reveal phone number, Start chat, and New listing were
   blocked with "Verify your email address and phone number to continue."
4. After both verifications, the phone number was revealed, Start chat passed all
   checks ("Chat opens in a later release"), and a listing was published.
5. A wrong code showed "This code is incorrect. 4 attempts left."

The Gmail delivery itself needs Workspace credentials and was not run here.
