"""The development Mono mock must speak the same API the real client and webhook expect."""

from decimal import Decimal

import httpx
import pytest

from adify_api.dev.mono_mock import create_app, luhn_valid
from adify_api.payments import mono as mono_module
from adify_api.payments.mono import MonoClient, MonoError, verify_signature

pytestmark = pytest.mark.anyio

REDIRECT = "http://localhost:5173/orders/order-1?payment=return"
WEBHOOK = "http://backend:8000/api/v1/payments/mono/webhook"


@pytest.fixture
def webhooks() -> list[httpx.Request]:
    return []


@pytest.fixture
def mock(webhooks):
    def deliver(request: httpx.Request) -> httpx.Response:
        webhooks.append(request)
        return httpx.Response(200)

    return create_app("http://localhost:8095", webhook_transport=httpx.MockTransport(deliver))


@pytest.fixture
def client(mock, monkeypatch) -> MonoClient:
    monkeypatch.setattr(mono_module, "_pubkey_cache", {})
    return MonoClient("mono-mock", "http://mono-mock", httpx.ASGITransport(app=mock))


@pytest.fixture
def browser(mock) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=mock), base_url="http://mono-mock")


async def hold_invoice(client: MonoClient) -> str:
    created = await client.create_hold_invoice(
        amount=Decimal("1500.00"),
        reference="order-1",
        destination="Adify order: banner",
        redirect_url=REDIRECT,
        webhook_url=WEBHOOK,
    )
    assert created["pageUrl"] == f"http://localhost:8095/pay/{created['invoiceId']}"
    return created["invoiceId"]


async def test_paying_on_the_mock_page_holds_and_signs_the_webhook(client, browser, webhooks):
    invoice_id = await hold_invoice(client)
    page = await browser.get(f"/pay/{invoice_id}")

    paid = await browser.post(f"/pay/{invoice_id}", content="action=pay&card=4111+1111+1111+1111")

    assert "1 500.00 UAH" in page.text
    assert paid.status_code == 303
    assert paid.headers["location"] == REDIRECT
    status = await client.invoice_status(invoice_id)
    assert status["status"] == "hold"
    assert status["amount"] == 150000
    assert status["reference"] == "order-1"
    [webhook] = webhooks
    assert str(webhook.url) == WEBHOOK
    assert verify_signature(webhook.content, webhook.headers["X-Sign"], await client.pubkey())


async def test_declining_reports_a_failure(client, browser, webhooks):
    invoice_id = await hold_invoice(client)

    await browser.post(f"/pay/{invoice_id}", content="action=decline")

    status = await client.invoice_status(invoice_id)
    assert status["status"] == "failure"
    assert status["failureReason"] == "Declined on the mock page"
    assert len(webhooks) == 1


async def test_a_card_failing_the_luhn_check_is_refused(client, browser, webhooks):
    invoice_id = await hold_invoice(client)

    response = await browser.post(f"/pay/{invoice_id}", content="action=pay&card=4111111111111112")

    assert response.status_code == 422
    assert "Luhn" in response.text
    assert (await client.invoice_status(invoice_id))["status"] == "created"
    assert webhooks == []


async def test_finalize_and_cancel_follow_the_hold(client, browser):
    """For ADY-021 (finalize on Start work) and ADY-025/026 (cancel the hold)."""
    finalized, canceled = await hold_invoice(client), await hold_invoice(client)
    for invoice_id in (finalized, canceled):
        await browser.post(f"/pay/{invoice_id}", content="action=pay&card=4242424242424242")

    done = await client.finalize_hold(finalized, Decimal("1500.00"))
    reversed_ = await client.cancel_invoice(canceled)

    assert done == {"status": "success"}
    finalized_status = await client.invoice_status(finalized)
    assert finalized_status["status"] == "success"
    assert finalized_status["finalAmount"] == 150000
    assert reversed_["status"] == "success"
    assert (await client.invoice_status(canceled))["status"] == "reversed"
    with pytest.raises(MonoError):
        await client.finalize_hold(canceled, Decimal("1500.00"))


async def test_requests_without_a_token_are_refused(mock):
    client = MonoClient("", "http://mono-mock", httpx.ASGITransport(app=mock))

    with pytest.raises(MonoError):
        await client.invoice_status("mock_missing")


async def test_luhn_check():
    assert luhn_valid("4111 1111 1111 1111")
    assert luhn_valid("4242424242424242")
    assert not luhn_valid("4111 1111 1111 1112")
    assert not luhn_valid("4111-1111-1111-1111")
    assert not luhn_valid("")


async def test_a_removed_invoice_can_no_longer_be_paid(client, browser, webhooks):
    """ADY-025/026: ending an order invalidates its unpaid invoice."""
    invoice_id = await hold_invoice(client)

    assert await client.remove_invoice(invoice_id) == {}
    paid = await browser.post(f"/pay/{invoice_id}", content="action=pay&card=4111111111111111")

    assert paid.status_code == 303
    assert (await client.invoice_status(invoice_id))["status"] == "expired"
    assert [w.headers["X-Sign"] != "" for w in webhooks] == [True]
    with pytest.raises(MonoError):
        await client.remove_invoice(invoice_id)
