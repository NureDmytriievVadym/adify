# Story #3 — Register a customer or provider account

## Source and scope

Backlog: **Accounts and verification**, priority Must, estimate 8.
Primary requirements: FR-001, FR-002, FR-003, FR-068 (ban keys), FR-078,
FR-079, FR-080, SRS §3.2.1.5, §3.3.2 steps 3.1–3.3, §3.4.1, §3.7.

A prospective user registers with a display name, email address, Ukrainian phone
number, password, and exactly one marketplace role. The account is created with
`active` status and unverified email and phone. Sign-in (FR-007), JWT sessions
(NFR-SEC-001), email/phone verification (FR-004–FR-006), account recovery
(FR-081), and moderator bans (FR-068 actions) belong to their own stories.

## API

`POST /api/v1/accounts` returns `201` with the profile fields (FR-009), role,
status, and both verification flags. Every error uses FastAPI's validation shape,
`{"detail": [{"loc": ["body", field], "msg": ..., "type": ...}]}`:

| Status | `type`                             | Cause                                       |
| ------ | ---------------------------------- | ------------------------------------------- |
| 422    | `phone_not_ukrainian`              | Not `+380` followed by nine digits (FR-078) |
| 422    | `password_policy`                  | Under 8 characters, no letter, or no digit  |
| 422    | `password_too_long`                | Over 72 bytes, the bcrypt input limit       |
| 422    | `role_not_single`, `literal_error` | A list of roles, or a staff/unknown role    |
| 422    | `extra_forbidden`                  | Unknown fields, e.g. `roles`                |
| 403    | `email_banned`, `phone_banned`     | Contact of a banned account (FR-079)        |
| 409    | `email_taken`, `phone_taken`       | Contact already registered                  |

Emails are stored lower-case; spaces, hyphens, and parentheses are removed from
phone numbers before validation. Passwords are stored only as salted bcrypt hashes.

## Persistence

PostgreSQL schema is managed by Alembic (`backend/migrations`); the Docker backend
runs `alembic upgrade head` before starting. `accounts` holds the §3.4.1 attributes;
`account_bans` stores the email and phone an account had when banned, so a ban
keeps blocking those values even if the account's contacts later change (FR-068).
Until moderation exists, bans are inserted directly in the database.

## Web

`/register` collects the five fields with the role as a radio group, validates the
same rules in the browser, and maps API errors to their fields. The header's
**Get started** action links to it. The browser calls the API at
`PUBLIC_API_BASE_URL` (default `http://localhost:8000`); the API allows the origins
in `ADIFY_CORS_ORIGINS`.

## Open TBDs

- Duplicate-account handling and detailed messages (§3.2.1.5). Registration
  currently reports a taken email or phone, which reveals that it is registered.
- Rate limits and lockout (§3.2.1.5).
- Shared contact details for bans (FR-068).
- Display-name length: not specified; limited to 100 characters here.

## Automated acceptance

`backend/tests/test_registration.py` covers both roles, normalization, phone and
password rejection, both-role and staff-role attempts, banned email/phone, bans
outliving contact changes, duplicates, and the OpenAPI contract. The Playwright
suite registers both roles against a mocked API, checks browser validation, a
banned-contact error, and runs axe on `/register` at all layout widths.
