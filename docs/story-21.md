# Story #21 — Provider starts work after payment

## Source and scope

Epic: Order workflow. Backlog priority Must, estimate 3 (ADY-021).
Primary requirements: FR-039, FR-056, FR-124, FR-132.

> As a provider, I want to start work explicitly after payment, so I can confirm I received
> and understood the order requirements.

The provider of a **paid** order clicks **Start work**. Mono finalizes the hold from ADY-020,
so the held funds are charged, and the order becomes **in progress**. A paid order the
provider does not start within 7 days is canceled and its hold released, because Mono
cancels an unfinalized hold after 9 days. Canceling a hold on the participants' own
request is ADY-025 and ADY-026; the other order timeouts are ADY-027.

## Rules

| Situation                                       | Result                                                       |
| ----------------------------------------------- | ------------------------------------------------------------ |
| Provider, paid order                            | `200`, Mono finalizes the hold, the order is `in_progress`   |
| The customer                                    | `403 not_order_provider`                                     |
| Anyone outside the order                        | `403 not_order_participant`                                  |
| The order is not paid (also: started already)   | `409 order_not_paid`; Mono is not asked again                |
| The order needs a creative and has no valid one | `409 no_validated_creative`, see Creatives below             |
| No Mono token configured                        | `503 payments_unavailable`                                   |
| Mono refuses or cannot be reached               | `502 payment_provider_error`, logged; the order stays `paid` |
| Paid, not started 7 days after `paid_at`        | The job releases the hold; the order is `canceled`           |
| The job cannot release a hold                   | Logged; the order stays `paid` and the next run retries      |

The order moves to in progress only after Mono finalizes the hold, so the money and the
state cannot disagree. The order row is locked while starting, so two clicks charge once.

## API

| Endpoint                            | Result                                                |
| ----------------------------------- | ----------------------------------------------------- |
| `POST /api/v1/orders/{id}/start`    | `200` with the order in progress, see the rules above |
| `GET /api/v1/orders/{id}` and lists | New fields below                                      |

New order fields: `start_deadline` (paid orders only: `paid_at` + 7 days), `work_started_at`,
`work_start_blocker` (paid orders only: why Start work is unavailable, today only
`No validated creative`), `canceled_at`, `cancel_reason` (`start_timeout`), and
`requirements.requires_creatives`.

## Start timeout job

`python -m adify_api.jobs` runs once and cancels every paid order whose `paid_at` is more than
`ADIFY_PAID_ORDER_START_TIMEOUT_DAYS` (default 7) days ago: Mono cancels the invoice
(`reversed`), and the order records `canceled_at` and `cancel_reason = start_timeout`. A
deployment schedules it at least daily with cron. Locally:

```sh
just order-timeouts                         # as of now
just order-timeouts --now 2026-12-01        # as of a later date (UTC), for demos and checks
```

The timeout becomes an administrator setting with ADY-053 (at most 8 days because of the Mono
hold limit).

## Creatives (FR-124, ADY-056)

The rule is in place: when the order's requirements snapshot says it needs customer creatives
and the order has no creative that passed validation, the API refuses Start work and the page
disables the button with the hint “No validated creative”. Its data is not there yet:
uploading and validating creatives is ADY-055. Until then `requires_creatives` is false for
every snapshot and `has_validated_creative` in `orders/creatives.py` is a stub, so no order is
blocked. ADY-055 sets the flag when it builds the snapshot and replaces the stub with a check
of the order's creatives; the API, the page, and the tests already cover the blocked case.

## Persistence

Migration `0013` adds `work_started_at`, `canceled_at`, and `cancel_reason` to `orders`.

## Web

On `/orders/{id}` the provider of a paid order sees **Start work** with the date by which work
must start; the button is disabled with the reason when a validated creative is missing. The
customer sees that the order waits for the provider until that date. An order in progress
shows when work started; an order canceled by the timeout explains that the provider did not
start in time and that Mono released the funds.

## Automated acceptance

`backend/tests/test_start_work.py`: the provider starts work and Mono finalizes the hold for
the order amount; the start deadline; the customer and outsiders are refused; no start before
payment; a second start charges nothing; a required creative blocks the start; a Mono failure
keeps the order paid and is logged; no Mono token; the job cancels an order paid 7 days ago
and releases its hold while a newer one stays paid; a started order never times out; a hold
Mono does not release is retried. `backend/tests/test_mono_mock.py` finalizes and cancels
through the real client against the mock. The Playwright suite `start-work.spec.ts` covers
the provider starting work (with axe), the customer's view, the disabled button with the
creative hint, a Mono failure, and the timeout explanation.

## Manual demo

1. `just up`, then `just seed`. Create an order in a chat, sign in as the customer and pay it
   on the Mono mock page (see story #20).
2. Sign in as the provider, open the order, and click **Start work**: the order is **In
   progress**. Invoice status
   `curl -H "X-Token: mono-mock" "http://localhost:8095/api/merchant/invoice/status?invoiceId=…"`
   reports `success`.
3. Sign in as the customer: no **Start work** button. Calling
   `POST /api/v1/orders/{id}/start` with the customer's token answers `403`.
4. Pay a second order and leave it. Run `just order-timeouts --now <a date 8 days ahead>`:
   the order is **Canceled** and its invoice status is `reversed`.
5. Creatives: see the section above; the blocked case runs in the automated tests.
