"""ADY-021: the provider starts work on a paid order; unstarted orders time out after 7 days."""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from test_orders import OFFER, order_body, sign_up
from test_payments import FakeMono, error_type, invoice, send_webhook

from adify_api.core.config import get_settings
from adify_api.orders.models import Order
from adify_api.orders.workflow import cancel_unstarted_orders
from adify_api.payments.mono import get_mono

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def no_mono_settings(monkeypatch):
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


async def create_order(client: AsyncClient, customer, provider) -> str:
    listing = await client.post("/api/v1/listings/offers", json=OFFER, headers=provider)
    chat = await client.post(f"/api/v1/listings/{listing.json()['id']}/chats", headers=customer)
    created = await client.post(
        f"/api/v1/chats/{chat.json()['id']}/orders", json=order_body(), headers=provider
    )
    return created.json()["id"]


async def pay(client: AsyncClient, mono: FakeMono, customer, order: str) -> str:
    """Pays the order through the hold flow of ADY-020; returns the invoice id."""
    started = await client.post(f"/api/v1/orders/{order}/payment", headers=customer)
    invoice_id = started.json()["page_url"].rsplit("/", 1)[1]
    await send_webhook(client, mono, invoice(invoice_id, "hold"))
    return invoice_id


@pytest.fixture
async def paid(client, mono, customer, provider) -> str:
    order = await create_order(client, customer, provider)
    await pay(client, mono, customer, order)
    return order


async def set_order(sessionmaker, order: str, **values) -> None:
    async with sessionmaker() as session:
        await session.execute(update(Order).where(Order.id == uuid.UUID(order)).values(**values))
        await session.commit()


async def get_order(client: AsyncClient, order: str, headers) -> dict:
    return (await client.get(f"/api/v1/orders/{order}", headers=headers)).json()


async def test_the_provider_starts_work_and_mono_charges_the_hold(
    client: AsyncClient, mono, customer, provider, paid
):
    response = await client.post(f"/api/v1/orders/{paid}/start", headers=provider)

    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"
    assert response.json()["work_started_at"] is not None
    assert response.json()["start_deadline"] is None
    assert mono.finalized == [("inv1", Decimal("3000.00"))]
    seen = await get_order(client, paid, customer)
    assert seen["status"] == "in_progress"
    payment = (await client.get(f"/api/v1/orders/{paid}/payment", headers=customer)).json()
    assert payment["status"] == "success"


async def test_a_paid_order_shows_when_it_must_start(client: AsyncClient, provider, paid):
    seen = await get_order(client, paid, provider)

    paid_at = datetime.fromisoformat(seen["paid_at"]).replace(tzinfo=UTC)
    deadline = datetime.fromisoformat(seen["start_deadline"]).replace(tzinfo=UTC)
    assert deadline - paid_at == timedelta(days=7)
    assert seen["work_start_blocker"] is None


async def test_only_the_provider_starts_work(
    client: AsyncClient, mono, customer, sessionmaker, paid
):
    as_customer = await client.post(f"/api/v1/orders/{paid}/start", headers=customer)
    outsider = await sign_up(client, sessionmaker, "provider", "other@example.com", "+380673333333")
    as_outsider = await client.post(f"/api/v1/orders/{paid}/start", headers=outsider)

    assert as_customer.status_code == 403
    assert error_type(as_customer) == "not_order_provider"
    assert as_outsider.status_code == 403
    assert error_type(as_outsider) == "not_order_participant"
    assert mono.finalized == []
    assert (await get_order(client, paid, customer))["status"] == "paid"


async def test_work_cannot_start_before_payment(client: AsyncClient, mono, customer, provider):
    order = await create_order(client, customer, provider)

    response = await client.post(f"/api/v1/orders/{order}/start", headers=provider)

    assert response.status_code == 409
    assert error_type(response) == "order_not_paid"


async def test_starting_twice_charges_once(client: AsyncClient, mono, provider, paid):
    await client.post(f"/api/v1/orders/{paid}/start", headers=provider)

    again = await client.post(f"/api/v1/orders/{paid}/start", headers=provider)

    assert again.status_code == 409
    assert error_type(again) == "order_not_paid"
    assert len(mono.finalized) == 1


async def test_a_required_creative_blocks_the_start(
    client: AsyncClient, mono, provider, sessionmaker, paid
):
    """FR-124: the rule is live; ADY-055 will set the flag and store creatives."""
    seen = await get_order(client, paid, provider)
    await set_order(
        sessionmaker, paid, requirements=seen["requirements"] | {"requires_creatives": True}
    )

    blocked = await get_order(client, paid, provider)
    response = await client.post(f"/api/v1/orders/{paid}/start", headers=provider)

    assert blocked["work_start_blocker"] == "No validated creative"
    assert blocked["requirements"]["requires_creatives"] is True
    assert response.status_code == 409
    assert error_type(response) == "no_validated_creative"
    assert mono.finalized == []


async def test_a_mono_failure_leaves_the_order_paid(
    client: AsyncClient, mono, customer, provider, paid, caplog
):
    mono.down = True

    with caplog.at_level(logging.ERROR):
        response = await client.post(f"/api/v1/orders/{paid}/start", headers=provider)

    assert response.status_code == 502
    assert error_type(response) == "payment_provider_error"
    assert (await get_order(client, paid, customer))["status"] == "paid"
    assert "Finalizing invoice inv1 failed" in caplog.text


async def test_without_mono_work_cannot_start(client: AsyncClient, mono, provider, paid, app):
    app.dependency_overrides[get_mono] = lambda: None

    response = await client.post(f"/api/v1/orders/{paid}/start", headers=provider)

    assert response.status_code == 503
    assert error_type(response) == "payments_unavailable"


async def test_an_unstarted_order_is_canceled_after_seven_days(
    client: AsyncClient, mono, customer, provider, sessionmaker, paid
):
    fresh = await create_order(client, customer, provider)
    await pay(client, mono, customer, fresh)
    paid_at = datetime(2026, 11, 1, 12, tzinfo=UTC)
    await set_order(sessionmaker, paid, paid_at=paid_at)
    await set_order(sessionmaker, fresh, paid_at=paid_at + timedelta(days=2))

    async with sessionmaker() as session:
        canceled = await cancel_unstarted_orders(session, mono, paid_at + timedelta(days=7))

    assert [str(order.id) for order in canceled] == [paid]
    assert mono.canceled == ["inv1"]
    old = await get_order(client, paid, customer)
    assert old["status"] == "canceled"
    assert old["cancel_reason"] == "start_timeout"
    assert old["canceled_at"] is not None
    payment = (await client.get(f"/api/v1/orders/{paid}/payment", headers=customer)).json()
    assert payment["status"] == "reversed"
    assert (await get_order(client, fresh, customer))["status"] == "paid"


async def test_a_started_order_never_times_out(
    client: AsyncClient, mono, provider, sessionmaker, paid
):
    await client.post(f"/api/v1/orders/{paid}/start", headers=provider)
    await set_order(sessionmaker, paid, paid_at=datetime(2026, 11, 1, tzinfo=UTC))

    async with sessionmaker() as session:
        canceled = await cancel_unstarted_orders(session, mono, datetime(2026, 12, 1, tzinfo=UTC))

    assert canceled == []
    assert mono.canceled == []
    assert (await get_order(client, paid, provider))["status"] == "in_progress"


async def test_a_hold_mono_does_not_release_is_retried_later(
    client: AsyncClient, mono, provider, sessionmaker, paid, caplog
):
    await set_order(sessionmaker, paid, paid_at=datetime(2026, 11, 1, tzinfo=UTC))
    mono.down = True

    async with sessionmaker() as session:
        with caplog.at_level(logging.ERROR):
            canceled = await cancel_unstarted_orders(
                session, mono, datetime(2026, 11, 9, tzinfo=UTC)
            )

    assert canceled == []
    assert (await get_order(client, paid, provider))["status"] == "paid"
    assert "Releasing the hold" in caplog.text
