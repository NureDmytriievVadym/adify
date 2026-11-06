# Reset a forgotten password

## Source and scope

Backlog: **Accounts and verification**, priority Must, estimate 5.
Primary requirement: FR-081.

A user who has lost access asks for a reset link at **Forgot password?**, opens
the email, and sets a new password. Afterwards the new password signs in, the old
one does not, and opening the same link again says it has expired or has already
been used.

## API

| Endpoint                                   | Result                                        |
| ------------------------------------------ | --------------------------------------------- |
| `POST /api/v1/auth/password-reset`         | `202` always; body `{"email": ...}`           |
| `POST /api/v1/auth/password-reset/confirm` | `204`; body `{"token": ..., "password": ...}` |

The request endpoint answers `202` whether or not the email is registered,
verified, or has just received a link, so it cannot be used to find accounts.
The email is sent after the response, so its delivery time and any SMTP failure
are not visible either; failures are logged.

| Status | `type`                                 | Cause                                       |
| ------ | -------------------------------------- | ------------------------------------------- |
| 400    | `reset_link_invalid`                   | Unknown, expired, already used, or replaced |
| 422    | `password_policy`, `password_too_long` | Same rules as registration (FR-080)         |

A rejected password does not use up the link.

## Links

A link is sent only to an account whose email is verified. It carries a random
32-byte token; only its SHA-256 is stored in `password_reset_tokens`. A link works
once and expires after 30 minutes (`ADIFY_PASSWORD_RESET_MINUTES`). A new request
within 60 seconds (`ADIFY_PASSWORD_RESET_RESEND_SECONDS`) sends nothing; a later
one replaces the previous link. The link is claimed with a conditional update, so
two simultaneous uses cannot both succeed.

Setting a new password revokes every refresh token of the account. Access tokens
already issued stay valid until they expire (at most 15 minutes).

Locally the email lands in Mailpit (http://localhost:8025); for the Gmail demo set
the `ADIFY_SMTP_*` variables as described in [story #5](story-05.md#delivery).

## Web

`/sign-in` links to `/forgot-password`, which takes the email and then shows the
same "check your email" message for any address. The email links to
`/reset-password?token=…`, which asks for the new password, checks the policy in
the browser, and on success points to sign-in. An expired or used link shows the
API message with a link to request a new one.

## Open TBDs

- Link validity and lockout/rate-limit rules (to be closed in the Sprint 1 SRS
  refinement); 30 minutes and a 60-second wait per account are the working
  defaults. No per-IP limit yet.
- Accounts with an unverified email cannot reset their password; confirm with the SRS.
- Changing email is not implemented; when it is, outstanding links should be
  invalidated.

## Automated acceptance

`backend/tests/test_password_reset.py` covers the full reset, the old password
failing, single use, sign-out of every session, unknown and unverified emails
getting the same answer with no mail, expiry, unknown tokens, the resend wait,
replacement by a newer link, the password policy, and hashed storage. The
Playwright suite covers the sign-in link, the request form, browser validation,
a successful reset followed by the reused link failing, a missing token, and runs
axe on `/reset-password`.
