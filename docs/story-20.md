# Story #20 — Pay for an order by card in UAH

## Source and scope

Epic: Payments and escrow. Backlog priority Must, estimate 13 (ADY-020).
Primary requirements: FR-038, FR-055, FR-092, FR-133, SW-001.

> As a customer, I want to pay for an order by bank card in UAH through Mono, so the funds
> are held until the provider starts work.

The customer of an order **awaiting payment** pays on Mono's payment page. Mono holds the
funds (`paymentType = hold`, valid 9 days, canceled by Mono if not finalized) and the order
becomes **paid**. Finalizing the hold on Start work and the 7-day start timeout are ADY-021;
canceling the hold on cancel or reject is ADY-025 and ADY-026. Payment failure handling is
still TBD in the SRS: a failed or expired invoice leaves the order awaiting payment and the
customer can pay again.

## Rules

| Situation                                     | Result                                           |
| --------------------------------------------- | ------------------------------------------------ |
| Verified customer, order awaiting payment     | `201`, a Mono hold invoice and its `page_url`    |
| Paying again while that invoice is still open | `201`, the same invoice                          |
| The provider                                  | `403 not_order_customer`                         |
| Anyone outside the order                      | `403 not_order_participant`                      |
| The order is not awaiting payment             | `409 order_not_awaiting_payment`                 |
| No Mono token configured                      | `503 payments_unavailable`                       |
| Mono refuses or cannot be reached             | `502 payment_provider_error`                     |
| Signed webhook with status `hold`             | The order becomes `paid` and records `paid_at`   |
| Webhook with a missing or invalid `X-Sign`    | `400 invalid_signature`, logged, nothing changes |
| Webhook older than the last applied update    | Ignored (Mono does not guarantee webhook order)  |
| `failure` or `expired`                        | Recorded; the order stays awaiting payment       |

## API

| Endpoint                             | Result                                                       |
| ------------------------------------ | ------------------------------------------------------------ |
| `POST /api/v1/orders/{id}/payment`   | `201` payment with `page_url`, see the rules above           |
| `GET /api/v1/orders/{id}/payment`    | The latest payment, synced from Mono's status API while open |
| `POST /api/v1/payments/mono/webhook` | Mono's status callback, verified before anything is read     |

The invoice amount is the order price in kopiyky, currency 980 (UAH), with the order id as
`reference` and `redirectUrl` back to `/orders/{id}?payment=return`. Webhooks are verified
with ECDSA-SHA256 over the raw body against Mono's public key (`/api/merchant/pubkey`); the
key is cached and fetched again once when a signature does not verify, in case it rotated.

## Configuration

| Variable               | Meaning                                                              |
| ---------------------- | -------------------------------------------------------------------- |
| `ADIFY_MONO_TOKEN`     | Merchant or test token from api.monobank.ua; empty disables payments |
| `ADIFY_MONO_API_URL`   | Mono API base URL; `https://api.monobank.ua` unless overridden       |
| `ADIFY_API_PUBLIC_URL` | URL of this API that Mono can reach for webhooks; empty sends none   |

Without a webhook URL, when Mono redirects the customer back, the order page reads the
payment, which asks Mono's status API and applies the result, so the order still reaches
**paid**. Never commit a token.

## Local development: the Mono mock

Docker Compose runs `mono-mock` (`backend/src/adify_api/dev/mono_mock.py`) and points the
backend at it, so payments work for everyone after `docker compose up` with no token. It
implements invoice create, status, finalize, cancel, and the public key. Its page at
`http://localhost:8095/pay/{invoice}` has **Pay** (any card number that passes the Luhn
check, prefilled with `4111 1111 1111 1111`) and **Decline**. The result is sent as a signed
webhook to the backend on the Compose network, so the real signature check runs; no money
moves. Invoices and the signing key live in memory and reset when the mock restarts.

A test token from api.monobank.ua is a personal token that can read its owner's statement.
Use one only on your own machine, in `.env` (see `.env.example`), never shared or committed.

## Persistence

Migration `0012` creates `payments` (order, Mono invoice id, page URL, amount, Mono status,
failure reason, Mono's `modifiedDate` of the last applied update) and adds `paid_at` to
`orders`. A new invoice is created for each payment attempt; earlier ones stay as history.

## Web

On `/orders/{id}` the customer of an order awaiting payment sees **Pay** with the price and
goes to Mono's page; the provider sees that the order waits for the customer's payment. A
paid order shows when it was paid and that Mono holds the funds until work starts. After
Mono's redirect the page explains a payment that is still processing, failed, or expired.

## Automated acceptance

`backend/tests/test_payments.py` covers starting a hold invoice, the webhook URL from the
public API URL, reusing an open invoice, customer-only payment, a missing token, a Mono
failure, a signed `hold` webhook marking the order paid, no second payment, invalid and
missing signatures (ignored and logged), out-of-order webhooks, a failed payment and a new
attempt, syncing through the status API, the request body sent to Mono, and signature
verification. The Playwright suite stubs the API and Mono's page: the customer pays, the
provider waits, and the return after a hold or a failure, with axe on the order page.

`backend/tests/test_mono_mock.py` runs the real Mono client and signature check against the
mock: a hold with a signed webhook, a decline, a card failing the Luhn check, finalize and
cancel, and a missing token.

## Manual demo

1. `docker compose up`, then `just seed`. Sign in as a provider and create an order in a
   chat with a customer; sign in as that customer, open the order, and click **Pay**.
2. The mock payment page opens; click **Pay**. It redirects back and the order shows
   **Paid**; the backend log shows the webhook call.
3. Invoice status: `curl -H "X-Token: mono-mock" "http://localhost:8095/api/merchant/invoice/status?invoiceId=…"`
   reports `hold`.
4. Post any body to `/api/v1/payments/mono/webhook` with a wrong `X-Sign`: `400`, and the
   backend log shows the ignored webhook.

With real Mono (a test token in your own `.env`), step 2 is Mono's page and a test card.
