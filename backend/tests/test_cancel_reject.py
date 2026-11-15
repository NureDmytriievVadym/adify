"""ADY-025 and ADY-026: the customer cancels, or the provider rejects, before work starts."""

import logging
import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from test_orders import sign_up
from test_payments import FakeMono, error_type, invoice, send_webhook
from test_start_work import create_order, get_order, pay

from adify_api.core.config import get_settings
from adify_api.orders.models import Order, OrderStatus
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


@pytest.fixture
async def awaiting(client, mono, customer, provider) -> str:
    return await create_order(client, customer, provider)


@pytest.fixture
async def paid(client, mono, customer, awaiting) -> str:
    await pay(client, mono, customer, awaiting)
    return awaiting


async def cancel(client: AsyncClient, order: str, headers):
    return await client.post(f"/api/v1/orders/{order}/cancel", headers=headers)


async def reject(client: AsyncClient, order: str, headers):
    return await client.post(f"/api/v1/orders/{order}/reject", headers=headers)


async def payment(client: AsyncClient, order: str, headers) -> dict:
    return (await client.get(f"/api/v1/orders/{order}/payment", headers=headers)).json()


# ADY-025: the customer cancels


async def test_the_customer_cancels_an_order_awaiting_payment(
    client: AsyncClient, mono, customer, provider, awaiting
):
    response = await cancel(client, awaiting, customer)

    assert response.status_code == 200
    assert response.json()["status"] == "canceled"
    assert response.json()["cancel_reason"] == "customer_canceled"
    assert response.json()["canceled_at"] is not None
    assert (await get_order(client, awaiting, provider))["status"] == "canceled"
    assert mono.removed == mono.canceled == []


async def test_canceling_closes_an_unpaid_mono_invoice(
    client: AsyncClient, mono, customer, awaiting
):
    await client.post(f"/api/v1/orders/{awaiting}/payment", headers=customer)

    response = await cancel(client, awaiting, customer)

    assert response.json()["status"] == "canceled"
    assert mono.removed == ["inv1"]
    assert (await payment(client, awaiting, customer))["status"] == "expired"
    again = await client.post(f"/api/v1/orders/{awaiting}/payment", headers=customer)
    assert error_type(again) == "order_not_awaiting_payment"


async def test_the_customer_cancels_a_paid_order_and_the_hold_is_released(
    client: AsyncClient, mono, customer, paid
):
    response = await cancel(client, paid, customer)

    assert response.status_code == 200
    assert response.json()["status"] == "canceled"
    assert mono.canceled == ["inv1"]
    assert (await payment(client, paid, customer))["status"] == "reversed"


async def test_the_provider_cannot_cancel(client: AsyncClient, mono, customer, provider, paid):
    response = await cancel(client, paid, provider)

    assert [response.status_code, error_type(response)] == [403, "not_order_customer"]
    assert (await get_order(client, paid, customer))["status"] == "paid"


async def test_canceling_after_work_started_points_to_a_dispute(
    client: AsyncClient, mono, customer, provider, paid
):
    await client.post(f"/api/v1/orders/{paid}/start", headers=provider)

    response = await cancel(client, paid, customer)

    assert [response.status_code, error_type(response)] == [409, "work_started"]
    assert "Open a dispute" in response.json()["detail"][0]["msg"]
    assert (await get_order(client, paid, customer))["status"] == "in_progress"
    assert mono.canceled == []


async def test_awaiting_an_additional_payment_after_work_started_cannot_be_ended(
    client: AsyncClient, mono, customer, provider, paid, sessionmaker
):
    """A price change (ADY-024) can bring a started order back to awaiting payment."""
    await client.post(f"/api/v1/orders/{paid}/start", headers=provider)
    async with sessionmaker() as session:
        await session.execute(
            update(Order)
            .where(Order.id == uuid.UUID(paid))
            .values(status=OrderStatus.AWAITING_PAYMENT)
        )
        await session.commit()

    canceled = await cancel(client, paid, customer)
    rejected = await reject(client, paid, provider)

    assert error_type(canceled) == error_type(rejected) == "work_started"


async def test_a_mono_failure_leaves_the_order_paid(
    client: AsyncClient, mono, customer, paid, caplog
):
    mono.down = True

    with caplog.at_level(logging.ERROR):
        response = await cancel(client, paid, customer)

    assert [response.status_code, error_type(response)] == [502, "payment_provider_error"]
    assert (await get_order(client, paid, customer))["status"] == "paid"
    assert "Releasing the funds of order" in caplog.text


async def test_an_ended_order_cannot_be_ended_again(
    client: AsyncClient, mono, customer, provider, awaiting
):
    await cancel(client, awaiting, customer)

    again = await cancel(client, awaiting, customer)
    rejected = await reject(client, awaiting, provider)

    assert [again.status_code, error_type(again)] == [409, "order_not_endable"]
    assert error_type(rejected) == "order_not_endable"


# ADY-026: the provider rejects


async def test_the_provider_rejects_an_order_awaiting_payment(
    client: AsyncClient, mono, customer, provider, awaiting
):
    response = await reject(client, awaiting, provider)

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    assert response.json()["cancel_reason"] == "provider_rejected"
    assert (await get_order(client, awaiting, customer))["status"] == "rejected"


async def test_the_provider_rejects_a_paid_order_and_the_hold_is_released(
    client: AsyncClient, mono, customer, provider, paid
):
    response = await reject(client, paid, provider)

    assert response.json()["status"] == "rejected"
    assert mono.canceled == ["inv1"]
    seen = await get_order(client, paid, customer)
    assert seen["status"] == "rejected"
    # The customer's page says the funds were released because the order had been paid.
    assert seen["paid_at"] is not None
    assert (await payment(client, paid, customer))["status"] == "reversed"


async def test_the_customer_cannot_reject(client: AsyncClient, mono, customer, awaiting):
    response = await reject(client, awaiting, customer)

    assert [response.status_code, error_type(response)] == [403, "not_order_provider"]


async def test_rejecting_after_start_work_is_refused(client: AsyncClient, mono, provider, paid):
    await client.post(f"/api/v1/orders/{paid}/start", headers=provider)

    response = await reject(client, paid, provider)

    assert [response.status_code, error_type(response)] == [409, "work_started"]


async def test_without_mono_a_paid_order_cannot_be_ended(
    client: AsyncClient, mono, provider, paid, app
):
    app.dependency_overrides[get_mono] = lambda: None

    response = await reject(client, paid, provider)

    assert [response.status_code, error_type(response)] == [503, "payments_unavailable"]


async def test_a_payment_arriving_after_cancel_is_released(
    client: AsyncClient, mono, customer, awaiting, caplog
):
    """Mono may report a payment made just before the invoice was removed."""
    await client.post(f"/api/v1/orders/{awaiting}/payment", headers=customer)
    await cancel(client, awaiting, customer)

    with caplog.at_level(logging.WARNING):
        await send_webhook(client, mono, invoice("inv1", "hold", "2026-11-14T12:00:00Z"))

    assert mono.canceled == ["inv1"]
    assert (await payment(client, awaiting, customer))["status"] == "reversed"
    assert (await get_order(client, awaiting, customer))["status"] == "canceled"
    assert "ended before its payment arrived" in caplog.text


async def test_the_start_timeout_still_releases_holds(
    client: AsyncClient, mono, customer, paid, sessionmaker
):
    from adify_api.orders.workflow import cancel_unstarted_orders

    async with sessionmaker() as session:
        await session.execute(
            update(Order)
            .where(Order.id == uuid.UUID(paid))
            .values(paid_at=datetime(2026, 11, 1, tzinfo=UTC))
        )
        await session.commit()
        canceled = await cancel_unstarted_orders(session, mono, datetime(2026, 11, 9, tzinfo=UTC))

    assert len(canceled) == 1
    assert mono.canceled == ["inv1"]
    assert (await get_order(client, paid, customer))["cancel_reason"] == "start_timeout"
