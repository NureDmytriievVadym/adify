# Stories #25 and #26 — Cancel or reject an order before work starts

## Source and scope

Epic: Order workflow. Backlog priority Must, estimate 2 each (ADY-025, ADY-026).
Primary requirements: FR-046, FR-047, FR-096.

> ADY-025: As a customer, I want to cancel an order before work starts, so I can stop an
> order that is awaiting payment or paid.
>
> ADY-026: As a provider, I want to reject an order before work starts, so I can decline an
> order I cannot fulfill.

Until the provider clicks **Start work** (story #21), the customer can **cancel** an order
and the provider can **reject** it, whether it is awaiting payment or paid. A paid order's
Mono hold is canceled, so the customer's funds are released in full. After Start work
neither is possible, also when a price change (ADY-024) later brings the order back to
awaiting payment; a dispute (ADY-030) is the way out then. Showing refund status in detail
is ADY-029.

## Rules

| Situation                                                 | Result                                                |
| --------------------------------------------------------- | ----------------------------------------------------- |
| Customer cancels, awaiting payment or paid                | `canceled`, `cancel_reason = customer_canceled`       |
| Provider rejects, awaiting payment or paid                | `rejected`, `cancel_reason = provider_rejected`       |
| The order is paid                                         | Mono cancels the hold first (`reversed`)              |
| A Mono payment page is still open                         | Mono invalidates the invoice first (`expired`)        |
| The provider cancels, or the customer rejects             | `403 not_order_customer` / `not_order_provider`       |
| Anyone outside the order                                  | `403 not_order_participant`                           |
| Work has started (`work_started_at` set)                  | `409 work_started`: “… Open a dispute instead.”       |
| The order already ended, or is in review or done          | `409 order_not_endable`                               |
| Money is at Mono but no token is configured               | `503 payments_unavailable`                            |
| Mono refuses or cannot be reached                         | `502 payment_provider_error`, logged; nothing changes |
| A `hold` webhook arrives for a canceled or rejected order | The hold is released at once and logged               |

The order changes only after Mono has released everything, so money and state cannot
disagree. Invalidating the invoice stops a payment page that is still open in the
customer's browser; a payment Mono reports just before that is released when its webhook
arrives (or when the order page syncs the payment). The 7-day start timeout of story #21
releases funds the same way.

## API

| Endpoint                          | Who      | Result                    |
| --------------------------------- | -------- | ------------------------- |
| `POST /api/v1/orders/{id}/cancel` | Customer | `200`, the order canceled |
| `POST /api/v1/orders/{id}/reject` | Provider | `200`, the order rejected |

Both answer with the order; `canceled_at` records when it ended. The Mono client gains
`remove_invoice` (`POST /api/merchant/invoice/remove`), and the Mono mock implements it.

## Web

On `/orders/{id}` an order awaiting payment or paid shows **Cancel order** to the customer
and **Reject order** to the provider (`OrderEnd.svelte`). Each opens a confirmation that
says whether Mono will release held funds, with a red confirm button. Once work has started
the customer sees that the order can no longer be canceled and that a dispute will be the
way to raise a problem. An ended order says who ended it and when; for a paid one it adds
that Mono released the funds (“Funds released” after a rejection).

## Automated acceptance

`backend/tests/test_cancel_reject.py`: canceling an order awaiting payment, with an open
invoice (invalidated, and it cannot be paid again), and paid (hold released); the provider
cannot cancel; canceling after Start work points to a dispute; a started order back in
awaiting payment can be neither canceled nor rejected; a Mono failure leaves the order paid;
an ended order cannot end again; rejecting an order awaiting payment and paid (hold
released, the customer still sees it was paid); the customer cannot reject; no rejection
after Start work; no Mono token; a payment arriving after cancel is released; the start
timeout still releases holds. `test_mono_mock.py` removes an invoice through the real
client. The Playwright suite `cancel-reject.spec.ts` covers canceling paid (with axe) and
unpaid orders, rejecting with “Funds released”, the customer's view of a rejection, no
cancel or reject after work starts, and closing the confirmation with Escape.

## Manual demo

1. Create an order in a chat (story #19). As the customer click **Cancel order** and confirm:
   **Canceled**, nothing charged.
2. Create another order and pay it on the Mono mock. As the customer cancel it: **Canceled**,
   and the invoice status
   `curl -H "X-Token: mono-mock" "http://localhost:8095/api/merchant/invoice/status?invoiceId=…"`
   is `reversed`.
3. Repeat 1 and 2 as the provider with **Reject order**: **Rejected**; the customer sees
   “Funds released”.
4. Pay a third order and click **Start work** as the provider: the customer has no **Cancel
   order** and sees the dispute hint; the provider has no **Reject order**.
