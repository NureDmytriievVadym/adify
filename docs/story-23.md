# Story #23 — Submit work for customer review

## Source and scope

Epic: Order workflow. Backlog priority Must, estimate 5 (ADY-023).
Primary requirements: FR-040, FR-042–FR-044.

> As a provider, I want to submit work for customer review, so the customer can accept it or
> request changes.

The provider submits an order **in progress** for review and it moves to **in review**. The
customer accepts the work, and the order is **done**, or requests changes. The provider
agrees to make them, and the order is back **in progress**, or declines, and it stays **in
review**. The parties agree how many rounds there are; the system keeps every request but
does not limit them. Evidence and stages are ADY-022, automatic completion after 14 days in
review is ADY-027, disputes are ADY-030. Paying the provider out when an order is done waits
for the Mono payout mechanism, which the SRS has not confirmed yet.

## Rules

| Situation                                         | Result                                              |
| ------------------------------------------------- | --------------------------------------------------- |
| Provider submits an order in progress             | `in_review`, `review_started_at` set                |
| Customer accepts an order in review               | `done`, `completed_at` set                          |
| Customer requests changes with a message (1–2000) | `201`, a pending request; the order stays in review |
| Provider agrees to a pending request              | `in_progress`, `review_started_at` cleared          |
| Provider declines a pending request               | The order stays `in_review`                         |
| Customer accepts while a request is pending       | `done`; the request is closed as `withdrawn`        |
| A second request while one is pending             | `409 change_request_pending`                        |
| Answering a request that is already closed        | `409 change_request_answered`                       |
| An unknown request                                | `404 change_request_not_found`                      |
| The wrong participant                             | `403 not_order_provider` / `not_order_customer`     |
| Anyone outside the order                          | `403 not_order_participant`                         |
| The order is not in the required state            | `409 order_not_in_progress` / `order_not_in_review` |

After a decline the customer can accept, ask again, or, with ADY-030, open a dispute. The
order row is locked during each step, so two simultaneous clicks cannot both apply.

## API

| Endpoint                                                 | Who      | Result                     |
| -------------------------------------------------------- | -------- | -------------------------- |
| `POST /api/v1/orders/{id}/review`                        | Provider | Submits for review         |
| `POST /api/v1/orders/{id}/accept`                        | Customer | Accepts; the order is done |
| `POST /api/v1/orders/{id}/change-requests` `{message}`   | Customer | `201`, requests changes    |
| `POST /api/v1/orders/{id}/change-requests/{rid}/agree`   | Provider | Back in progress           |
| `POST /api/v1/orders/{id}/change-requests/{rid}/decline` | Provider | Stays in review            |

Each answers with the order. Orders gain `review_started_at`, `completed_at`, and
`change_requests` (oldest first: `id`, `message`, `status` = `pending`, `agreed`,
`declined`, or `withdrawn`, `created_at`, `answered_at`).

## Persistence

Migration `0014` adds `review_started_at` and `completed_at` to `orders` and creates
`order_change_requests` (order, message, status, created and answered times).
`review_started_at` is what the 14-day auto-completion of ADY-027 will count from; it is
cleared when the provider agrees to changes and set again on the next submission.

## Web

The **Work** section of `/orders/{id}` (`OrderReview.svelte`) shows, by state and role:
**Submit for review** for the provider of an order in progress; **Accept work** and
**Request changes** with a message for the customer of an order in review; the quoted
request with **Agree to make changes** and **Decline** for the provider; and when the order
was completed. Every change request is listed with its outcome.

Every step that changes the order's state, and **Start work** from story #21, first opens a
confirmation dialog in the middle of the screen (`ConfirmDialog.svelte`, a native modal
`<dialog>`) that says what will happen. Focus starts on **Cancel**; Cancel, Escape, or a
click beside the dialog closes it without sending anything.

## Automated acceptance

`backend/tests/test_review.py`: submitting for review; a request the provider agrees to; a
request the provider declines (the order stays in review, the customer may ask again);
submitting again and accepting (done); accepting withdraws an unanswered request; each step
by the wrong participant or an outsider; each step in the wrong state; one pending request at
a time; a request is answered once, and an unknown one is not found; a blank or overlong
message. The Playwright suite `review.spec.ts` covers the provider submitting (with axe), the
customer requesting changes (with validation and axe), the provider agreeing and declining,
and the customer accepting.

## Manual demo

1. Take an order in progress (story #21: pay, then **Start work** as the provider).
2. As the provider click **Submit for review**: **In review**.
3. As the customer click **Request changes**, describe them, and send.
4. As the provider click **Agree to make changes**: **In progress**. Submit again, let the
   customer request changes once more, and this time click **Decline**: still **In review**.
5. As the customer click **Accept work**: **Done**. The change requests are listed with their
   outcomes.
