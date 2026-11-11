import base64
import json
import logging
from decimal import Decimal

import httpx
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from httpx import AsyncClient
from test_orders import OFFER, order_body, sign_up

from adify_api.core.config import get_settings
from adify_api.payments import mono as mono_module
from adify_api.payments.mono import MonoClient, MonoError, get_mono, verify_signature

pytestmark = pytest.mark.anyio

WEBHOOK = "/api/v1/payments/mono/webhook"


class FakeMono:
    """Stands in for Mono: records invoices, answers statuses, and signs webhooks."""

    def __init__(self) -> None:
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.invoices: list[dict] = []
        self.statuses: dict[str, dict] = {}
        self.down = False

    async def create_hold_invoice(self, **invoice) -> dict:
        if self.down:
            raise MonoError("Mono answered 500")
        self.invoices.append(invoice)
        invoice_id = f"inv{len(self.invoices)}"
        return {"invoiceId": invoice_id, "pageUrl": f"https://pay.mbnk.biz/{invoice_id}"}

    async def invoice_status(self, invoice_id: str) -> dict:
        if self.down:
            raise MonoError("Mono answered 500")
        return self.statuses[invoice_id]

    async def pubkey(self, refresh: bool = False) -> str:
        pem = self.key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return base64.b64encode(pem).decode()

    def sign(self, body: bytes) -> str:
        return base64.b64encode(self.key.sign(body, ec.ECDSA(hashes.SHA256()))).decode()


def invoice(invoice_id: str, status: str, modified: str = "2026-11-10T12:00:00Z", **extra):
    return {
        "invoiceId": invoice_id,
        "status": status,
        "amount": 300000,
        "ccy": 980,
        "createdDate": "2026-11-10T11:59:00Z",
        "modifiedDate": modified,
    } | extra


@pytest.fixture(autouse=True)
def no_mono_settings(monkeypatch):
    """The Compose stack points the backend at its Mono mock; tests start from no Mono."""
    settings = get_settings()
    monkeypatch.setattr(settings, "mono_token", "")
    monkeypatch.setattr(settings, "api_public_url", "")


@pytest.fixture
def mono(app) -> FakeMono:
    fake = FakeMono()
    app.dependency_overrides[get_mono] = lambda: fake
    return fake


@pytest.fixture
async def customer(client, sessionmaker):
    return await sign_up(client, sessionmaker, "customer", "customer@example.com", "+380671111111")


@pytest.fixture
async def provider(client, sessionmaker):
    return await sign_up(client, sessionmaker, "provider", "provider@example.com", "+380672222222")


@pytest.fixture
async def order(client, customer, provider) -> str:
    listing = await client.post("/api/v1/listings/offers", json=OFFER, headers=provider)
    chat = await client.post(f"/api/v1/listings/{listing.json()['id']}/chats", headers=customer)
    created = await client.post(
        f"/api/v1/chats/{chat.json()['id']}/orders", json=order_body(), headers=provider
    )
    assert created.status_code == 201
    return created.json()["id"]


async def send_webhook(client: AsyncClient, mono: FakeMono, data: dict, signature=None):
    body = json.dumps(data).encode()
    sign = mono.sign(body) if signature is None else signature
    return await client.post(WEBHOOK, content=body, headers={"X-Sign": sign})


def error_type(response) -> str:
    return response.json()["detail"][0]["type"]


async def test_customer_starts_a_hold_payment(client: AsyncClient, mono, customer, order):
    response = await client.post(f"/api/v1/orders/{order}/payment", headers=customer)

    assert response.status_code == 201
    assert response.json()["status"] == "created"
    assert response.json()["amount_uah"] == "3000.00"
    assert response.json()["page_url"] == "https://pay.mbnk.biz/inv1"
    [sent] = mono.invoices
    assert sent["amount"] == Decimal("3000.00")
    assert sent["reference"] == order
    assert sent["redirect_url"] == f"http://localhost:5173/orders/{order}?payment=return"
    # Locally no public API URL is set, so Mono is not asked to call a webhook.
    assert sent["webhook_url"] is None


async def test_the_webhook_url_uses_the_public_api_url(
    client: AsyncClient, mono, customer, order, monkeypatch
):
    monkeypatch.setattr(get_settings(), "api_public_url", "https://api.adify.example/")

    await client.post(f"/api/v1/orders/{order}/payment", headers=customer)

    assert mono.invoices[0]["webhook_url"] == (
        "https://api.adify.example/api/v1/payments/mono/webhook"
    )


async def test_paying_again_reuses_the_open_invoice(client: AsyncClient, mono, customer, order):
    first = await client.post(f"/api/v1/orders/{order}/payment", headers=customer)
    second = await client.post(f"/api/v1/orders/{order}/payment", headers=customer)

    assert second.status_code == 201
    assert second.json()["page_url"] == first.json()["page_url"]
    assert len(mono.invoices) == 1


async def test_only_the_customer_pays(client: AsyncClient, mono, provider, order, sessionmaker):
    as_provider = await client.post(f"/api/v1/orders/{order}/payment", headers=provider)
    outsider = await sign_up(client, sessionmaker, "customer", "other@example.com", "+380673333333")
    as_outsider = await client.post(f"/api/v1/orders/{order}/payment", headers=outsider)

    assert as_provider.status_code == 403
    assert error_type(as_provider) == "not_order_customer"
    assert as_outsider.status_code == 403
    assert error_type(as_outsider) == "not_order_participant"
    assert mono.invoices == []


async def test_without_a_mono_token_payments_are_unavailable(client: AsyncClient, customer, order):
    response = await client.post(f"/api/v1/orders/{order}/payment", headers=customer)

    assert response.status_code == 503
    assert error_type(response) == "payments_unavailable"


async def test_a_mono_failure_is_reported(client: AsyncClient, mono, customer, order):
    mono.down = True

    response = await client.post(f"/api/v1/orders/{order}/payment", headers=customer)

    assert response.status_code == 502
    assert error_type(response) == "payment_provider_error"


async def test_a_signed_hold_webhook_marks_the_order_paid(
    client: AsyncClient, mono, customer, provider, order
):
    await client.post(f"/api/v1/orders/{order}/payment", headers=customer)

    response = await send_webhook(client, mono, invoice("inv1", "hold"))

    assert response.status_code == 200
    for headers in (customer, provider):
        opened = (await client.get(f"/api/v1/orders/{order}", headers=headers)).json()
        assert opened["status"] == "paid"
        assert opened["paid_at"] is not None
    payment = (await client.get(f"/api/v1/orders/{order}/payment", headers=customer)).json()
    assert payment["status"] == "hold"
    assert payment["page_url"] is None


async def test_a_paid_order_cannot_be_paid_again(client: AsyncClient, mono, customer, order):
    await client.post(f"/api/v1/orders/{order}/payment", headers=customer)
    await send_webhook(client, mono, invoice("inv1", "hold"))

    response = await client.post(f"/api/v1/orders/{order}/payment", headers=customer)

    assert response.status_code == 409
    assert error_type(response) == "order_not_awaiting_payment"


async def test_a_webhook_with_an_invalid_signature_is_ignored_and_logged(
    client: AsyncClient, mono, customer, order, caplog
):
    await client.post(f"/api/v1/orders/{order}/payment", headers=customer)
    forged = base64.b64encode(
        ec.generate_private_key(ec.SECP256R1()).sign(b"other", ec.ECDSA(hashes.SHA256()))
    ).decode()

    with caplog.at_level(logging.WARNING):
        wrong = await send_webhook(client, mono, invoice("inv1", "hold"), signature=forged)
        missing = await client.post(WEBHOOK, content=json.dumps(invoice("inv1", "hold")))

    assert wrong.status_code == 400
    assert error_type(wrong) == "invalid_signature"
    assert missing.status_code == 400
    assert "invalid signature" in caplog.text
    opened = (await client.get(f"/api/v1/orders/{order}", headers=customer)).json()
    assert opened["status"] == "awaiting_payment"


async def test_an_older_webhook_does_not_undo_a_newer_one(
    client: AsyncClient, mono, customer, order
):
    await client.post(f"/api/v1/orders/{order}/payment", headers=customer)

    await send_webhook(client, mono, invoice("inv1", "hold", "2026-11-10T12:05:00Z"))
    await send_webhook(client, mono, invoice("inv1", "processing", "2026-11-10T12:01:00Z"))

    payment = (await client.get(f"/api/v1/orders/{order}/payment", headers=customer)).json()
    assert payment["status"] == "hold"


async def test_a_failed_payment_keeps_the_order_payable(client: AsyncClient, mono, customer, order):
    await client.post(f"/api/v1/orders/{order}/payment", headers=customer)
    await send_webhook(client, mono, invoice("inv1", "failure", failureReason="Insufficient funds"))

    payment = (await client.get(f"/api/v1/orders/{order}/payment", headers=customer)).json()
    retry = await client.post(f"/api/v1/orders/{order}/payment", headers=customer)

    assert payment["status"] == "failure"
    assert payment["failure_reason"] == "Insufficient funds"
    assert retry.status_code == 201
    assert retry.json()["page_url"] == "https://pay.mbnk.biz/inv2"


async def test_reading_the_payment_syncs_it_from_mono(client: AsyncClient, mono, customer, order):
    await client.post(f"/api/v1/orders/{order}/payment", headers=customer)
    mono.statuses["inv1"] = invoice("inv1", "hold")

    payment = (await client.get(f"/api/v1/orders/{order}/payment", headers=customer)).json()

    assert payment["status"] == "hold"
    opened = (await client.get(f"/api/v1/orders/{order}", headers=customer)).json()
    assert opened["status"] == "paid"


async def test_an_order_without_a_payment_has_none(client: AsyncClient, mono, provider, order):
    response = await client.get(f"/api/v1/orders/{order}/payment", headers=provider)

    assert response.status_code == 404
    assert error_type(response) == "payment_not_found"


async def test_signature_verification_needs_the_exact_body():
    key = ec.generate_private_key(ec.SECP256R1())
    pubkey = base64.b64encode(
        key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    ).decode()
    body = b'{"invoiceId":"inv1","status":"hold"}'
    signature = base64.b64encode(key.sign(body, ec.ECDSA(hashes.SHA256()))).decode()

    assert verify_signature(body, signature, pubkey)
    assert not verify_signature(body + b" ", signature, pubkey)
    assert not verify_signature(body, None, pubkey)
    assert not verify_signature(body, "not base64!", pubkey)


async def test_the_mono_client_creates_a_hold_invoice_in_kopiyky():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"invoiceId": "p2_x", "pageUrl": "https://pay/p2_x"})

    client = MonoClient("test-token", "https://mono.test", httpx.MockTransport(handler))
    created = await client.create_hold_invoice(
        amount=Decimal("3000.50"),
        reference="order-1",
        destination="Adify order: banner",
        redirect_url="http://localhost:5173/orders/order-1?payment=return",
        webhook_url=None,
    )

    assert created == {"invoiceId": "p2_x", "pageUrl": "https://pay/p2_x"}
    [request] = requests
    assert request.url.path == "/api/merchant/invoice/create"
    assert request.headers["X-Token"] == "test-token"
    assert json.loads(request.content) == {
        "amount": 300050,
        "ccy": 980,
        "paymentType": "hold",
        "merchantPaymInfo": {"reference": "order-1", "destination": "Adify order: banner"},
        "redirectUrl": "http://localhost:5173/orders/order-1?payment=return",
    }


async def test_the_mono_client_raises_on_an_error_answer(monkeypatch):
    monkeypatch.setattr(mono_module, "_pubkey_cache", {})
    client = MonoClient(
        "bad-token",
        "https://mono.test",
        httpx.MockTransport(lambda request: httpx.Response(403, json={"errText": "forbidden"})),
    )

    with pytest.raises(MonoError):
        await client.invoice_status("p2_x")
    with pytest.raises(MonoError):
        await client.pubkey()
