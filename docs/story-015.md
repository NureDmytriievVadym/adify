# Story #15 — Expire listings by date or inactivity

## Source and scope

Epic: Marketplace listings. Backlog priority Must, estimate 5 (ADY-015).

Primary requirements: **FR-021** (owner-selected listing expiry at 23:59 Kyiv time),
**FR-022** (inactivity expiry after three consecutive months), **FR-023** (notify the
owner when a listing expires because of inactivity), with **FR-012** (the expiry date is
a required listing field).

> As a listing owner, I want listings to expire on my selected date or after three
> months of account inactivity, so outdated listings are not available.

## Owner-selected expiry date (FR-012, FR-021)

Creating a listing now requires an `expiry_date` (`YYYY-MM-DD`). The API stores the UTC
instant of **23:59 `Europe/Kyiv`** on that date in `expires_at` and returns both the date
(`expiry_date`) and the instant (`expires_at`). The create form starts at today + 30 days
(the old interim lifetime), validates the field, and lets the owner change it.

- Today is allowed. The listing remains active until 23:59 Kyiv time today.
- A past date is rejected with `422 expiry_date_passed`.
- The owner may move the date while the listing is not expired.
- Once a listing is expired, it cannot be extended: `PATCH` with a different
  `expiry_date` returns `409 listing_expired`. This is how FR-019's “an expired listing
  cannot be resumed” is kept true even though the edit form is still available. Other
  fields of an expired listing remain editable, and sending the unchanged date back is
  accepted.

Status precedence is soft-deleted → expired → paused → active. A paused listing still
expires on its date; pausing does not stop the clock. `GET /api/v1/listings` additionally
excludes `expired_at` listings that were expired early by the inactivity job.

## Inactivity expiry (FR-022)

A successful password sign-in records `accounts.last_login_at`. Token refresh does not
count as a new login. An account with no recorded sign-in is measured from `created_at`.

The inactivity job treats the account as idle when its last activity is older than **three
calendar months** (month subtraction clamps the day to the target month's length). It
expires the owner's listings whose status is `active`; paused, soft-deleted, and already
expired listings are left untouched. The listing records `expired_at` and
`expired_reason = inactivity`.

## Notification (FR-023, COM-003)

COM-003 leaves the expiry-notification channel TBD. The interim implementation sends an
**email** through the existing Gmail/Mailpit service used for verification and password
reset. One email lists all of that owner's listings expired in the run and links to them.
The `expiry_notified_at` timestamp prevents a second notice. If delivery fails, the job
logs the error and leaves the timestamp empty, so the next run retries it. Retry timing is
otherwise TBD, as the SRS says.

## Jobs

`backend/src/adify_api/jobs.py` runs once per invocation, like a cron entry, and is
independent of the API process:

```sh
python -m adify_api.jobs --job listings      # both listing rules at the current time
python -m adify_api.jobs --job date           # only the owner-date rule
python -m adify_api.jobs --job inactivity     # only inactivity and notices
python -m adify_api.jobs --now 2026-11-14T23:59+02:00
```

The default `--job all` also runs the order start-timeout job, which needs Mono.

The `--job date` invocation is intended for **23:59 Europe/Kyiv** every day; the
inactivity rule can run once a day after it. Example crontab:

```cron
CRON_TZ=Europe/Kyiv
59 23 * * * cd /app && python -m adify_api.jobs --job date
5 0 * * *  cd /app && python -m adify_api.jobs --job inactivity
```

Locally, `just jobs` runs the CLI inside the backend container. `--now` lets a demo run
the 23:59 rule without waiting for the clock, and lets a demo move the three-month cut-off
forward.

## Persistence

Migration `0015` adds:

- `accounts.last_login_at` — the last successful password sign-in. Existing accounts are
  backfilled with the migration time so the first job run does not surprise them;
  accounts created afterwards fall back to `created_at` until their first sign-in;
- `listings.expired_at` — when an expiry job materialized the status;
- `listings.expired_reason` — `date` or `inactivity`;
- `listings.expiry_notified_at` — when the inactivity notice was delivered.

The status is still derived on read, so a listing is never shown as active after
`expires_at` even if cron is late. The columns make the transition and its reason explicit
and make notifications idempotent.

## Web

- The create and edit forms have an **Expiry date** field with a Kyiv-time hint. The create
  form defaults to 30 days ahead; the edit form shows the stored date.
- Expired listings show the existing **Expired** badge and cannot be extended. Other
  fields stay editable, and the expiry input is disabled for an expired listing with an
  explanation.
- The owner's state note uses the owner-selected date, so it still reads correctly in any
  browser time zone.

## Demo (acceptance)

1. `just seed`; sign in as a provider. Create a listing with **Expiry date = today**.
   Run `just jobs --now "$(date -d tomorrow +%Y-%m-%d)T00:00:00+02:00"` (or any time after
   today's 23:59 Kyiv): the listing is reported as expired and disappears from the
   marketplace.
2. Set the owner's last login to 3 months + 1 day ago:
   ```sh
   docker compose exec -T postgres psql -U adify -d adify -c \
     "UPDATE accounts SET last_login_at = now() - interval '3 months 1 day' WHERE email = 'sofiia.k@demo.adify.app';"
   ```
   Run `just jobs --job inactivity`: all of that owner's active listings expire. Paused
   listings stay paused.
3. Open Mailpit at http://localhost:8025: the owner has one **Your Adify listings have
   expired** email listing the affected listings. Re-running the job does not send it
   again.

## Open TBDs

- COM-003 channel and retry policy: email and retry-on-next-run are interim.
- Whether a token refresh should count as activity; the current rule is sign-in only.
- Whether paused listings should also be expired by the inactivity rule. The SRS says
  “active listings”, so paused listings are left paused.
- Renewing an expired listing: blocked by interpreting an expiry-date change as a resume.

## Automated acceptance

- `backend/tests/test_expiry.py` covers the required date, rejection of past dates, the
  23:59 Kyiv instant, moving a future date, refusing to extend an expired listing while
  keeping other fields editable, the date job (due, future, idempotent), the inactivity
  job (active only, paused/deleted untouched, fallback to account creation), email
  contents and once-only delivery, retry after an SMTP failure, and `last_login_at` on
  sign-in.
- Existing listing tests use the required `expiry_date` in their fixtures and still cover
  creation, search, editing, pausing, resuming, and soft deletion.
- The web tests cover the date field's default/validation and the edit form for an expired
  listing; the existing Playwright suite includes the listing state and expiry badges.
