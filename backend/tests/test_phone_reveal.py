from datetime import UTC, datetime, timedelta

import pytest
from conftest import verify_contacts
from httpx import AsyncClient
from sqlalchemy import update

from adify_api.accounts.models import Account
from adify_api.listings.models import Listing

pytestmark = pytest.mark.anyio

OFFER = {
    "category": "website-banners",
    "title": "Your brand on a design journal",
    "description": "A display banner placement on an independent design journal.",
    "price_uah": "3500.00",
    "delivery_days": 5,
    "specs": [],
}
OWNER_EMAIL = "provider@example.com"
OWNER_PHONE = "+380672222222"


async def sign_up(client: AsyncClient, sessionmaker, role: str, email: str, phone: str):
    body = {
        "display_name": f"Test {role}",
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
async def offer(client, sessionmaker) -> str:
    owner = await sign_up(client, sessionmaker, "provider", OWNER_EMAIL, OWNER_PHONE)
    response = await client.post("/api/v1/listings/offers", json=OFFER, headers=owner)
    assert response.status_code == 201
    return response.json()["id"]


@pytest.fixture
async def customer(client, sessionmaker):
    return await sign_up(client, sessionmaker, "customer", "customer@example.com", "+380671111111")


def reveal(client: AsyncClient, listing_id: str, headers=None):
    return client.post(f"/api/v1/listings/{listing_id}/phone-reveal", headers=headers)


async def test_guests_must_sign_in(client: AsyncClient, offer):
    response = await reveal(client, offer)

    assert response.status_code == 401
    assert response.json()["detail"][0]["type"] == "not_authenticated"


async def test_unverified_users_are_blocked(client: AsyncClient, offer, customer, sessionmaker):
    async with sessionmaker() as session:
        await session.execute(
            update(Account)
            .where(Account.email == "customer@example.com")
            .values(email_verified=False)
        )
        await session.commit()

    response = await reveal(client, offer, customer)

    assert response.status_code == 403
    assert response.json()["detail"][0]["type"] == "verification_required"
    assert OWNER_PHONE not in response.text


async def test_verified_users_get_only_the_phone_number(client: AsyncClient, offer, customer):
    response = await reveal(client, offer, customer)

    assert response.status_code == 200
    assert response.json() == {"phone": OWNER_PHONE}
    assert OWNER_EMAIL not in response.text


async def test_the_phone_number_is_shown_only_on_request(client: AsyncClient, offer, customer):
    for headers in (None, customer):
        details = await client.get(f"/api/v1/listings/{offer}", headers=headers)
        marketplace = await client.get("/api/v1/listings", headers=headers)
        for response in (details, marketplace):
            assert OWNER_PHONE not in response.text
            assert OWNER_EMAIL not in response.text


async def test_reveals_are_not_limited(client: AsyncClient, offer, customer):
    responses = [await reveal(client, offer, customer) for _ in range(5)]

    assert {response.status_code for response in responses} == {200}


@pytest.mark.parametrize("state", ["paused", "expired"])
async def test_paused_and_expired_listings_still_reveal(
    client: AsyncClient, offer, customer, sessionmaker, state
):
    values = (
        {"paused_at": datetime.now(UTC)}
        if state == "paused"
        else {"expires_at": datetime.now(UTC) - timedelta(minutes=1)}
    )
    async with sessionmaker() as session:
        await session.execute(update(Listing).values(**values))
        await session.commit()

    response = await reveal(client, offer, customer)

    assert response.json() == {"phone": OWNER_PHONE}


async def test_unknown_listing_is_not_found(client: AsyncClient, customer):
    response = await reveal(client, "00000000-0000-0000-0000-000000000000", customer)

    assert response.status_code == 404
