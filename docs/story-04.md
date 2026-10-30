# Story #4 — Sign in with email and password

## Source and scope

Backlog: **Accounts and verification**, priority Must, estimate 5.
Primary requirements: FR-007, NFR-SEC-001, SRS §2.3 (unverified users may
authenticate), §3.2.1.4–§3.2.1.5, §3.3.2 postconditions, §3.4.1 (account status).

A registered user signs in with their email address and password and reaches
their account page. MFA is out of scope for the MVP. Email/phone verification,
account recovery (FR-081), and moderator suspensions/bans belong to their own stories.

## API

| Endpoint                     | Result                                                               |
| ---------------------------- | -------------------------------------------------------------------- |
| `POST /api/v1/auth/sign-in`  | `200` access token, `expires_in`, account; refresh token (see below) |
| `POST /api/v1/auth/refresh`  | `200` new access token; the refresh token is rotated                 |
| `POST /api/v1/auth/sign-out` | `204`; the refresh token is revoked and its cookie cleared           |
| `GET /api/v1/accounts/me`    | `200` own profile with `Authorization: Bearer <access token>`        |

`token_delivery` selects how the refresh token is returned: `cookie` (default, web)
sets an HttpOnly, `SameSite=Lax` cookie on `/api/v1/auth`; `body` (native clients)
returns it as `refresh_token`, and `/refresh` and `/sign-out` then accept it in
the body. Errors use the registration error shape:

| Status | `type`                                      | Cause                                         |
| ------ | ------------------------------------------- | --------------------------------------------- |
| 401    | `invalid_credentials`                       | Unknown email or wrong password (one message) |
| 403    | `account_suspended`, `account_banned`       | Correct password, but the account is blocked  |
| 401    | `invalid_refresh_token`                     | Missing, expired, revoked, or rotated token   |
| 401    | `not_authenticated`, `invalid_access_token` | `/me` without a valid access token            |
| 422    | validation types                            | Malformed email or unknown fields             |

Unknown emails are checked against a dummy bcrypt hash so the response time does
not reveal which emails are registered. Account status is reported only after the
password matches. Unverified accounts sign in normally.

## Persistence

Migration `0002` adds `refresh_tokens`: account, SHA-256 of the token, expiry, and
revocation time. Access tokens are stateless and expire after 15 minutes.

## Web

`/sign-in` shows one clear message for invalid credentials and focuses it. After
sign-in the user lands on `/account` (role, email, phone, verification status,
**Sign out**). On every page load the layout restores the session from the refresh
cookie, and the access token is renewed a minute before it expires. The header shows
**Sign in** and **Get started** to guests and **My account** when signed in.

## Open TBDs (session controls, NFR-SEC-001 and §3.2.1.5)

- Rate limits and lockout after failed sign-ins.
- Access/refresh lifetimes (15 minutes / 30 days chosen here), idle timeout, and
  signing out other devices.
- Reuse detection for rotated refresh tokens; two tabs refreshing at the same moment
  can sign one of them out.
- Suspension end: there is no suspension end date yet, so a suspended account stays
  blocked until its status changes (FR-067).

## Automated acceptance

`backend/tests/test_sign_in.py` covers valid sign-in and `/me`, case-insensitive
email, unverified accounts, one error for wrong password/unknown email, suspended
and banned accounts, cookie and body refresh with rotation, expiry, sign-out
revocation, hashed storage, and missing/forged/expired access tokens. The Playwright
suite signs in against a mocked API, reloads, signs out, checks the invalid-credentials
and empty-form errors, the guest account page, and runs axe on `/sign-in` and `/account`.
