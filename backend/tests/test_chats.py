from datetime import UTC, datetime, timedelta

import pytest
from conftest import verify_contacts
from httpx import AsyncClient
from sqlalchemy import update

from adify_api.chats.models import Chat
from adify_api.listings.models import Listing

pytestmark = pytest.mark.anyio

OFFER = {
    "category": "website-banners",
    "title": "Your brand on a design journal",
    "description": "A display banner placement on an independent design journal.",
    "price_uah": "3500.50",
    "delivery_days": 5,
    "expiry_date": (datetime.now(UTC).date() + timedelta(days=30)).isoformat(),
    "specs": [{"label": "Dimensions", "value": "728 x 90 px"}],
}
REQUEST = {
    "category": "sponsored-articles",
    "title": "Looking for a home for our story",
    "description": "We want a website to publish a sponsored article about our brand.",
    "budget_uah": "4500",
    "expiry_date": (datetime.now(UTC).date() + timedelta(days=30)).isoformat(),
    "specs": [],
}


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


def error_type(response) -> str:
    return response.json()["detail"][0]["type"]


async def test_customer_starts_a_chat_on_an_offer(client: AsyncClient, customer, offer):
    response = await client.post(f"/api/v1/listings/{offer}/chats", headers=customer)

    assert response.status_code == 201
    chat = response.json()
    owner_id = (await client.get(f"/api/v1/listings/{offer}")).json()["owner"]["id"]
    assert chat["listing"] == {
        "id": offer,
        "owner_id": owner_id,
        "title": OFFER["title"],
        "type": "offer",
        "status": "active",
    }
    assert chat["counterpart"]["display_name"] == "Test provider 22"
    assert chat["counterpart"]["role"] == "provider"
    assert "provider@example.com" not in response.text
    assert "+380672222222" not in response.text


async def test_starting_again_returns_the_same_chat(client: AsyncClient, customer, offer):
    first = await client.post(f"/api/v1/listings/{offer}/chats", headers=customer)
    second = await client.post(f"/api/v1/listings/{offer}/chats", headers=customer)

    assert (first.status_code, second.status_code) == (201, 200)
    assert first.json()["id"] == second.json()["id"]


async def test_provider_starts_a_chat_on_a_request(client: AsyncClient, customer, provider):
    created = await client.post("/api/v1/listings/requests", json=REQUEST, headers=customer)
    response = await client.post(f"/api/v1/listings/{created.json()['id']}/chats", headers=provider)

    assert response.status_code == 201
    assert response.json()["counterpart"]["role"] == "customer"


@pytest.mark.parametrize("state", ["paused", "expired"])
async def test_chats_start_on_paused_and_expired_listings(
    client: AsyncClient, customer, provider, offer, sessionmaker, state
):
    if state == "paused":
        await client.post(f"/api/v1/listings/{offer}/pause", headers=provider)
    else:
        async with sessionmaker() as session:
            await session.execute(
                update(Listing).values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
            )
            await session.commit()

    response = await client.post(f"/api/v1/listings/{offer}/chats", headers=customer)

    assert response.status_code == 201
    assert response.json()["listing"]["status"] == state


async def test_owner_cannot_chat_about_own_listing(client: AsyncClient, provider, offer):
    response = await client.post(f"/api/v1/listings/{offer}/chats", headers=provider)

    assert (response.status_code, error_type(response)) == (403, "own_listing")


async def test_same_role_chats_are_blocked(client: AsyncClient, sessionmaker, customer, offer):
    other_provider = await sign_up(
        client, sessionmaker, "provider", "other@example.com", "+380673333333"
    )
    request = await client.post("/api/v1/listings/requests", json=REQUEST, headers=customer)
    other_customer = await sign_up(
        client, sessionmaker, "customer", "second@example.com", "+380674444444"
    )

    provider_pair = await client.post(f"/api/v1/listings/{offer}/chats", headers=other_provider)
    customer_pair = await client.post(
        f"/api/v1/listings/{request.json()['id']}/chats", headers=other_customer
    )

    assert (provider_pair.status_code, error_type(provider_pair)) == (403, "same_role_chat")
    assert (customer_pair.status_code, error_type(customer_pair)) == (403, "same_role_chat")


async def test_unknown_listing_is_not_found(client: AsyncClient, customer):
    response = await client.post(
        "/api/v1/listings/00000000-0000-0000-0000-000000000000/chats", headers=customer
    )

    assert response.status_code == 404


async def test_both_participants_see_the_chat(client: AsyncClient, customer, provider, offer):
    started = (await client.post(f"/api/v1/listings/{offer}/chats", headers=customer)).json()

    mine = await client.get("/api/v1/chats", headers=customer)
    theirs = await client.get("/api/v1/chats", headers=provider)
    opened = await client.get(f"/api/v1/chats/{started['id']}", headers=provider)

    assert [chat["id"] for chat in mine.json()] == [started["id"]]
    assert [chat["id"] for chat in theirs.json()] == [started["id"]]
    assert theirs.json()[0]["counterpart"]["role"] == "customer"
    assert opened.status_code == 200
    assert opened.json()["counterpart"]["display_name"] == "Test customer 11"


async def test_only_participants_open_a_chat(client: AsyncClient, sessionmaker, customer, offer):
    started = (await client.post(f"/api/v1/listings/{offer}/chats", headers=customer)).json()
    outsider = await sign_up(client, sessionmaker, "customer", "third@example.com", "+380675555555")

    forbidden = await client.get(f"/api/v1/chats/{started['id']}", headers=outsider)
    anonymous = await client.get(f"/api/v1/chats/{started['id']}")
    missing = await client.get(
        "/api/v1/chats/00000000-0000-0000-0000-000000000000", headers=customer
    )
    outsider_list = await client.get("/api/v1/chats", headers=outsider)

    assert (forbidden.status_code, error_type(forbidden)) == (403, "not_chat_participant")
    assert anonymous.status_code == 401
    assert (missing.status_code, error_type(missing)) == (404, "chat_not_found")
    assert outsider_list.json() == []


async def test_chat_survives_when_the_listing_reference_is_gone(
    client: AsyncClient, customer, offer, sessionmaker
):
    started = (await client.post(f"/api/v1/listings/{offer}/chats", headers=customer)).json()
    # What ON DELETE SET NULL does in PostgreSQL when a listing is permanently deleted.
    async with sessionmaker() as session:
        await session.execute(update(Chat).values(listing_id=None))
        await session.commit()

    opened = await client.get(f"/api/v1/chats/{started['id']}", headers=customer)

    assert opened.status_code == 200
    assert opened.json()["listing"] is None
