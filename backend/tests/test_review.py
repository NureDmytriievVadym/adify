"""ADY-023: the provider submits work for review; the customer accepts or requests changes."""

import uuid

import pytest
from httpx import AsyncClient
from test_orders import sign_up
from test_payments import FakeMono, error_type
from test_start_work import create_order, get_order, pay

from adify_api.core.config import get_settings
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
async def started(client, mono, customer, provider) -> str:
    """An order in progress: created, paid, and started (ADY-019–ADY-021)."""
    order = await create_order(client, customer, provider)
    await pay(client, mono, customer, order)
    assert (await client.post(f"/api/v1/orders/{order}/start", headers=provider)).is_success
    return order


def url(order: str, action: str) -> str:
    return f"/api/v1/orders/{order}/{action}"


async def submit(client: AsyncClient, order: str, provider):
    return await client.post(url(order, "review"), headers=provider)


async def request_changes(client: AsyncClient, order: str, customer, message="Bigger logo."):
    return await client.post(
        url(order, "change-requests"), json={"message": message}, headers=customer
    )


async def answer(client: AsyncClient, order: str, provider, request_id: str, verb: str):
    return await client.post(url(order, f"change-requests/{request_id}/{verb}"), headers=provider)


async def test_the_provider_submits_work_for_review(
    client: AsyncClient, customer, provider, started
):
    response = await submit(client, started, provider)

    assert response.status_code == 200
    assert response.json()["status"] == "in_review"
    assert response.json()["review_started_at"] is not None
    assert (await get_order(client, started, customer))["status"] == "in_review"


async def test_the_customer_requests_changes_and_the_provider_agrees(
    client: AsyncClient, customer, provider, started
):
    await submit(client, started, provider)

    requested = await request_changes(client, started, customer, "  Use the new logo.  ")
    [change] = requested.json()["change_requests"]
    agreed = await answer(client, started, provider, change["id"], "agree")

    assert requested.status_code == 201
    assert requested.json()["status"] == "in_review"
    assert change["message"] == "Use the new logo."
    assert change["status"] == "pending"
    assert agreed.status_code == 200
    assert agreed.json()["status"] == "in_progress"
    assert agreed.json()["review_started_at"] is None
    assert agreed.json()["change_requests"][0]["status"] == "agreed"
    assert agreed.json()["change_requests"][0]["answered_at"] is not None


async def test_the_provider_declines_and_the_order_stays_in_review(
    client: AsyncClient, customer, provider, started
):
    await submit(client, started, provider)
    change = (await request_changes(client, started, customer)).json()["change_requests"][0]

    declined = await answer(client, started, provider, change["id"], "decline")

    assert declined.status_code == 200
    assert declined.json()["status"] == "in_review"
    assert declined.json()["change_requests"][0]["status"] == "declined"
    # After a decline the customer may ask again; the parties decide how many rounds.
    again = await request_changes(client, started, customer, "Please reconsider.")
    assert again.status_code == 201
    assert [r["status"] for r in again.json()["change_requests"]] == ["declined", "pending"]


async def test_submitting_again_and_accepting_completes_the_order(
    client: AsyncClient, customer, provider, started
):
    await submit(client, started, provider)
    change = (await request_changes(client, started, customer)).json()["change_requests"][0]
    await answer(client, started, provider, change["id"], "agree")
    await submit(client, started, provider)

    accepted = await client.post(url(started, "accept"), headers=customer)

    assert accepted.status_code == 200
    assert accepted.json()["status"] == "done"
    assert accepted.json()["completed_at"] is not None
    assert (await get_order(client, started, provider))["status"] == "done"


async def test_accepting_withdraws_an_unanswered_request(
    client: AsyncClient, customer, provider, started
):
    await submit(client, started, provider)
    change = (await request_changes(client, started, customer)).json()["change_requests"][0]

    accepted = await client.post(url(started, "accept"), headers=customer)
    late = await answer(client, started, provider, change["id"], "agree")

    assert accepted.json()["status"] == "done"
    assert accepted.json()["change_requests"][0]["status"] == "withdrawn"
    assert late.status_code == 409
    assert error_type(late) == "order_not_in_review"


async def test_each_step_belongs_to_one_participant(
    client: AsyncClient, customer, provider, started, sessionmaker
):
    outsider = await sign_up(client, sessionmaker, "customer", "other@example.com", "+380673333333")

    by_customer = await submit(client, started, customer)
    by_outsider = await submit(client, started, outsider)
    await submit(client, started, provider)
    accepted_by_provider = await client.post(url(started, "accept"), headers=provider)
    requested_by_provider = await request_changes(client, started, provider)
    change = (await request_changes(client, started, customer)).json()["change_requests"][0]
    answered_by_customer = await answer(client, started, customer, change["id"], "agree")

    assert [by_customer.status_code, error_type(by_customer)] == [403, "not_order_provider"]
    assert [by_outsider.status_code, error_type(by_outsider)] == [403, "not_order_participant"]
    assert error_type(accepted_by_provider) == "not_order_customer"
    assert error_type(requested_by_provider) == "not_order_customer"
    assert error_type(answered_by_customer) == "not_order_provider"
    assert (await get_order(client, started, customer))["status"] == "in_review"


async def test_steps_need_the_right_state(client: AsyncClient, mono, customer, provider, started):
    paid = await create_order(client, customer, provider)
    await pay(client, mono, customer, paid)

    submit_paid = await submit(client, paid, provider)
    accept_in_progress = await client.post(url(started, "accept"), headers=customer)
    request_in_progress = await request_changes(client, started, customer)

    assert [submit_paid.status_code, error_type(submit_paid)] == [409, "order_not_in_progress"]
    assert error_type(accept_in_progress) == "order_not_in_review"
    assert error_type(request_in_progress) == "order_not_in_review"


async def test_one_request_waits_for_an_answer_at_a_time(
    client: AsyncClient, customer, provider, started
):
    await submit(client, started, provider)
    await request_changes(client, started, customer)

    second = await request_changes(client, started, customer, "And a new colour.")

    assert second.status_code == 409
    assert error_type(second) == "change_request_pending"


async def test_a_request_is_answered_once(client: AsyncClient, customer, provider, started):
    await submit(client, started, provider)
    change = (await request_changes(client, started, customer)).json()["change_requests"][0]
    await answer(client, started, provider, change["id"], "decline")

    twice = await answer(client, started, provider, change["id"], "agree")
    unknown = await answer(client, started, provider, str(uuid.uuid4()), "agree")

    assert [twice.status_code, error_type(twice)] == [409, "change_request_answered"]
    assert [unknown.status_code, error_type(unknown)] == [404, "change_request_not_found"]


async def test_a_change_request_needs_a_message(client: AsyncClient, customer, provider, started):
    await submit(client, started, provider)

    blank = await request_changes(client, started, customer, "   ")
    too_long = await request_changes(client, started, customer, "x" * 2001)

    assert blank.status_code == 422
    assert too_long.status_code == 422
