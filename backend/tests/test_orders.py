from datetime import UTC, datetime, timedelta

import pytest
from conftest import verify_contacts
from httpx import AsyncClient
from sqlalchemy import update

from adify_api.accounts.models import Account
from adify_api.chats.models import Chat
from adify_api.listings.models import Listing

pytestmark = pytest.mark.anyio

OFFER = {
    "category": "website-banners",
    "title": "Your brand on a design journal",
    "description": "A display banner placement on an independent design journal.",
    "price_uah": "3500.00",
    "delivery_days": 5,
    "specs": [{"label": "Dimensions", "value": "728 x 90 px"}],
}
REQUEST = {
    "category": "sponsored-articles",
    "title": "Looking for a home for our story",
    "description": "We want a website to publish a sponsored article about our brand.",
    "budget_uah": "4500",
    "specs": [],
}


def days(n: int) -> str:
    return (datetime.now(UTC).date() + timedelta(days=n)).isoformat()


def order_body(**overrides):
    return {
        "details": "Homepage banner for two weeks with a report at the end.",
        "price_uah": "3000",
        "deadline": days(20),
        "stages": [
            {"title": "Banner goes live", "deadline": days(5)},
            {"title": "Placement report", "deadline": days(19)},
        ],
    } | overrides


async def sign_up(client: AsyncClient, sessionmaker, role: str, email: str, phone: str):
    body = {
        "display_name": f"Test {role} {phone[-2:]}",
        "email": email,
        "phone": phone,
        "role": role,
        "password": "secret123",
    }
    assert (await client.post("/api/v1/accounts", json=body)).status_code == 201
    await verify_contacts(sessionmaker, email)
    tokens = await client.post(
        "/api/v1/auth/sign-in", json={"email": email, "password": "secret123"}
    )
    return {"Authorization": f"Bearer {tokens.json()['access_token']}"}


@pytest.fixture
async def customer(client, sessionmaker):
    return await sign_up(client, sessionmaker, "customer", "customer@example.com", "+380671111111")


@pytest.fixture
async def provider(client, sessionmaker):
    return await sign_up(client, sessionmaker, "provider", "provider@example.com", "+380672222222")


@pytest.fixture
async def offer(client, provider) -> str:
    response = await client.post("/api/v1/listings/offers", json=OFFER, headers=provider)
    assert response.status_code == 201
    return response.json()["id"]


@pytest.fixture
async def offer_chat(client, customer, offer) -> str:
    response = await client.post(f"/api/v1/listings/{offer}/chats", headers=customer)
    assert response.status_code == 201
    return response.json()["id"]


def error_type(response) -> str:
    return response.json()["detail"][0]["type"]


async def test_owner_creates_an_order_awaiting_payment(client: AsyncClient, provider, offer_chat):
    response = await client.post(
        f"/api/v1/chats/{offer_chat}/orders", json=order_body(), headers=provider
    )

    assert response.status_code == 201
    order = response.json()
    assert order["status"] == "awaiting_payment"
    assert order["price_uah"] == "3000.00"
    assert order["deadline"] == days(20)
    assert order["stages"] == [
        {"title": "Banner goes live", "deadline": days(5)},
        {"title": "Placement report", "deadline": days(19)},
    ]
    assert order["is_listing_owner"] is True
    assert order["customer"]["role"] == "customer"
    assert order["provider"]["role"] == "provider"
    assert order["chat_id"] == offer_chat
    assert "customer@example.com" not in response.text
    assert "+380671111111" not in response.text


async def test_both_participants_see_the_order(client: AsyncClient, customer, provider, offer_chat):
    created = (
        await client.post(f"/api/v1/chats/{offer_chat}/orders", json=order_body(), headers=provider)
    ).json()

    for headers, is_owner in ((customer, False), (provider, True)):
        in_chat = await client.get(f"/api/v1/chats/{offer_chat}/orders", headers=headers)
        opened = await client.get(f"/api/v1/orders/{created['id']}", headers=headers)
        mine = await client.get("/api/v1/orders", headers=headers)
        assert [order["id"] for order in in_chat.json()] == [created["id"]]
        assert opened.json()["status"] == "awaiting_payment"
        assert opened.json()["is_listing_owner"] is is_owner
        assert [order["id"] for order in mine.json()] == [created["id"]]


async def test_snapshot_copies_the_offer_requirements(client: AsyncClient, provider, offer_chat):
    order = (
        await client.post(f"/api/v1/chats/{offer_chat}/orders", json=order_body(), headers=provider)
    ).json()

    assert order["requirements"] == {
        "listing_type": "offer",
        "category": "website-banners",
        "has_requirements": True,
        "specs": [{"label": "Dimensions", "value": "728 x 90 px"}],
    }


async def test_snapshot_records_an_ad_request_without_requirements(
    client: AsyncClient, customer, provider
):
    request = await client.post("/api/v1/listings/requests", json=REQUEST, headers=customer)
    chat = await client.post(f"/api/v1/listings/{request.json()['id']}/chats", headers=provider)

    order = await client.post(
        f"/api/v1/chats/{chat.json()['id']}/orders", json=order_body(), headers=customer
    )

    assert order.status_code == 201
    assert order.json()["is_listing_owner"] is True
    assert order.json()["requirements"] == {
        "listing_type": "request",
        "category": "sponsored-articles",
        "has_requirements": False,
        "specs": [],
    }


async def test_listing_edits_leave_the_snapshot_unchanged(
    client: AsyncClient, customer, provider, offer, offer_chat
):
    created = (
        await client.post(f"/api/v1/chats/{offer_chat}/orders", json=order_body(), headers=provider)
    ).json()

    edited = await client.patch(
        f"/api/v1/listings/{offer}",
        json={"specs": [{"label": "Dimensions", "value": "300 x 250 px"}]},
        headers=provider,
    )
    reopened = await client.get(f"/api/v1/orders/{created['id']}", headers=customer)

    assert edited.status_code == 200
    assert edited.json()["specs"] == [{"label": "Dimensions", "value": "300 x 250 px"}]
    assert reopened.json()["requirements"]["specs"] == [
        {"label": "Dimensions", "value": "728 x 90 px"}
    ]


async def test_the_other_party_cannot_create_an_order(client: AsyncClient, customer, offer_chat):
    response = await client.post(
        f"/api/v1/chats/{offer_chat}/orders", json=order_body(), headers=customer
    )

    assert (response.status_code, error_type(response)) == (403, "not_listing_owner")


async def test_outsiders_cannot_create_or_see_orders(
    client: AsyncClient, sessionmaker, provider, offer_chat
):
    created = (
        await client.post(f"/api/v1/chats/{offer_chat}/orders", json=order_body(), headers=provider)
    ).json()
    outsider = await sign_up(client, sessionmaker, "customer", "third@example.com", "+380673333333")

    create = await client.post(
        f"/api/v1/chats/{offer_chat}/orders", json=order_body(), headers=outsider
    )
    listing = await client.get(f"/api/v1/chats/{offer_chat}/orders", headers=outsider)
    opened = await client.get(f"/api/v1/orders/{created['id']}", headers=outsider)

    assert (create.status_code, error_type(create)) == (403, "not_chat_participant")
    assert listing.status_code == 403
    assert (opened.status_code, error_type(opened)) == (403, "not_order_participant")
    assert (await client.get("/api/v1/orders", headers=outsider)).json() == []


@pytest.mark.parametrize("state", ["paused", "expired"])
async def test_paused_and_expired_listings_take_no_new_orders(
    client: AsyncClient, provider, offer, offer_chat, sessionmaker, state
):
    if state == "paused":
        await client.post(f"/api/v1/listings/{offer}/pause", headers=provider)
    else:
        async with sessionmaker() as session:
            await session.execute(
                update(Listing).values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
            )
            await session.commit()

    response = await client.post(
        f"/api/v1/chats/{offer_chat}/orders", json=order_body(), headers=provider
    )

    assert (response.status_code, error_type(response)) == (409, f"listing_{state}")


async def test_a_deleted_listing_takes_no_new_orders(
    client: AsyncClient, provider, offer_chat, sessionmaker
):
    async with sessionmaker() as session:
        await session.execute(update(Chat).values(listing_id=None))
        await session.commit()

    response = await client.post(
        f"/api/v1/chats/{offer_chat}/orders", json=order_body(), headers=provider
    )

    assert (response.status_code, error_type(response)) == (409, "listing_deleted")


async def test_unverified_owners_must_verify_first(
    client: AsyncClient, provider, offer_chat, sessionmaker
):
    async with sessionmaker() as session:
        await session.execute(
            update(Account)
            .where(Account.email == "provider@example.com")
            .values(phone_verified=False)
        )
        await session.commit()

    response = await client.post(
        f"/api/v1/chats/{offer_chat}/orders", json=order_body(), headers=provider
    )

    assert (response.status_code, error_type(response)) == (403, "verification_required")


@pytest.mark.parametrize(
    "overrides",
    [
        {"details": ""},
        {"price_uah": "0"},
        {"deadline": days(-1)},
        {"stages": [{"title": "Too late", "deadline": days(25)}]},
        {"stages": [{"title": "In the past", "deadline": days(-2)}]},
        {"stages": [{"title": f"Stage {n}"} for n in range(11)]},
        {"status": "paid"},
    ],
)
async def test_rejects_invalid_orders(client: AsyncClient, provider, offer_chat, overrides):
    response = await client.post(
        f"/api/v1/chats/{offer_chat}/orders", json=order_body(**overrides), headers=provider
    )

    assert response.status_code == 422


async def test_stages_and_deadline_are_optional(client: AsyncClient, provider, offer_chat):
    response = await client.post(
        f"/api/v1/chats/{offer_chat}/orders",
        json={"details": "A single banner week.", "price_uah": "1200"},
        headers=provider,
    )

    assert response.status_code == 201
    assert response.json()["stages"] == []
    assert response.json()["deadline"] is None


async def test_an_order_awaiting_payment_locks_the_listing_category(
    client: AsyncClient, provider, offer, offer_chat
):
    await client.post(f"/api/v1/chats/{offer_chat}/orders", json=order_body(), headers=provider)

    response = await client.patch(
        f"/api/v1/listings/{offer}", json={"category": "stream-ads"}, headers=provider
    )

    assert (response.status_code, error_type(response)) == (409, "category_locked")
