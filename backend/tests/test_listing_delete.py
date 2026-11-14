import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from conftest import verify_contacts
from httpx import AsyncClient
from sqlalchemy import select, update

from adify_api.core.config import get_settings
from adify_api.listings.models import Listing, ListingAttachment
from adify_api.orders.models import Order, OrderStatus

pytestmark = pytest.mark.anyio

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
OFFER = {
    "category": "website-banners",
    "title": "Your brand on a design journal",
    "description": "A display banner placement on an independent design journal.",
    "price_uah": "3500.00",
    "delivery_days": 5,
    "expiry_date": (datetime.now(UTC).date() + timedelta(days=30)).isoformat(),
    "specs": [{"label": "Dimensions", "value": "728 x 90 px"}],
}
ORDER = {"details": "Homepage banner for two weeks.", "price_uah": "3000", "stages": []}


@pytest.fixture(autouse=True)
def storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(get_settings(), "storage_dir", str(tmp_path))
    return tmp_path


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


async def place_order(client: AsyncClient, offer: str, customer, provider) -> dict:
    chat = (await client.post(f"/api/v1/listings/{offer}/chats", headers=customer)).json()
    response = await client.post(f"/api/v1/chats/{chat['id']}/orders", json=ORDER, headers=provider)
    assert response.status_code == 201
    return response.json()


async def in_marketplace(client: AsyncClient, listing_id: str, headers) -> tuple[bool, bool]:
    public = (await client.get("/api/v1/listings", params={"q": "design journal"})).json()
    mine = (await client.get("/api/v1/listings/mine", headers=headers)).json()
    return (
        any(item["id"] == listing_id for item in public["items"]),
        any(item["id"] == listing_id for item in mine["items"]),
    )


async def stored(sessionmaker, model, id: str):
    async with sessionmaker() as session:
        # SQLAlchemy's UUID type needs UUID objects, not the strings the API returns.
        return await session.scalar(select(model).filter_by(id=uuid.UUID(id)))


async def test_listing_without_orders_is_removed(
    client: AsyncClient, provider, offer, sessionmaker, storage
):
    upload = await client.post(
        f"/api/v1/listings/{offer}/attachments",
        content=PNG,
        params={"filename": "banner.png"},
        headers=provider | {"Content-Type": "application/octet-stream"},
    )
    attachment_id = upload.json()["id"]

    response = await client.delete(f"/api/v1/listings/{offer}", headers=provider)

    assert (response.status_code, response.json()) == (200, {"result": "removed"})
    assert await in_marketplace(client, offer, provider) == (False, False)
    assert (await client.get(f"/api/v1/listings/{offer}")).status_code == 404
    assert await stored(sessionmaker, Listing, id=offer) is None
    assert await stored(sessionmaker, ListingAttachment, id=attachment_id) is None
    assert not (storage / attachment_id).exists()


async def test_listing_with_a_chat_but_no_orders_is_removed(
    client: AsyncClient, customer, provider, offer
):
    chat = (await client.post(f"/api/v1/listings/{offer}/chats", headers=customer)).json()

    response = await client.delete(f"/api/v1/listings/{offer}", headers=provider)

    assert response.json() == {"result": "removed"}
    # PostgreSQL clears the chat's reference (ON DELETE SET NULL); the chat itself stays.
    assert (await client.get(f"/api/v1/chats/{chat['id']}", headers=customer)).status_code == 200


@pytest.mark.parametrize("status", [OrderStatus.AWAITING_PAYMENT, OrderStatus.DONE])
async def test_listing_with_order_history_is_soft_deleted(
    client: AsyncClient, customer, provider, offer, sessionmaker, status
):
    order = await place_order(client, offer, customer, provider)
    async with sessionmaker() as session:
        await session.execute(update(Order).values(status=status))
        await session.commit()

    response = await client.delete(f"/api/v1/listings/{offer}", headers=provider)

    assert (response.status_code, response.json()) == (200, {"result": "soft_deleted"})
    assert await in_marketplace(client, offer, provider) == (False, False)
    kept = await stored(sessionmaker, Listing, id=offer)
    assert kept is not None and kept.deleted_at is not None
    details = await client.get(f"/api/v1/listings/{offer}")
    assert (details.status_code, details.json()["status"]) == (200, "soft_deleted")
    opened = await client.get(f"/api/v1/orders/{order['id']}", headers=customer)
    assert opened.json()["listing"]["id"] == offer


async def test_soft_deleted_listing_takes_no_changes_or_orders(
    client: AsyncClient, customer, provider, offer
):
    await place_order(client, offer, customer, provider)
    await client.delete(f"/api/v1/listings/{offer}", headers=provider)

    attempts = [
        await client.patch(
            f"/api/v1/listings/{offer}",
            json={"title": "A fresh banner on the journal"},
            headers=provider,
        ),
        await client.post(f"/api/v1/listings/{offer}/pause", headers=provider),
        await client.post(f"/api/v1/listings/{offer}/resume", headers=provider),
        await client.post(
            f"/api/v1/listings/{offer}/attachments",
            content=PNG,
            params={"filename": "banner.png"},
            headers=provider | {"Content-Type": "application/octet-stream"},
        ),
    ]
    chat = await client.post(f"/api/v1/listings/{offer}/chats", headers=customer)
    order = await client.post(
        f"/api/v1/chats/{chat.json()['id']}/orders", json=ORDER, headers=provider
    )

    for response in attempts:
        assert (response.status_code, response.json()["detail"][0]["type"]) == (
            409,
            "listing_deleted",
        )
    # FR-026: chats still start from a soft-deleted listing; only new orders stop.
    assert chat.status_code == 200
    assert (order.status_code, order.json()["detail"][0]["type"]) == (409, "listing_deleted")


async def test_deleting_twice_keeps_the_soft_deleted_listing(
    client: AsyncClient, customer, provider, offer
):
    await place_order(client, offer, customer, provider)
    await client.delete(f"/api/v1/listings/{offer}", headers=provider)

    again = await client.delete(f"/api/v1/listings/{offer}", headers=provider)

    assert (again.status_code, again.json()) == (200, {"result": "soft_deleted"})


async def test_paused_and_expired_listings_can_be_deleted(
    client: AsyncClient, provider, offer, sessionmaker
):
    second = await client.post("/api/v1/listings/offers", json=OFFER, headers=provider)
    await client.post(f"/api/v1/listings/{offer}/pause", headers=provider)
    async with sessionmaker() as session:
        await session.execute(
            update(Listing)
            .where(Listing.id == uuid.UUID(second.json()["id"]))
            .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        await session.commit()

    paused = await client.delete(f"/api/v1/listings/{offer}", headers=provider)
    expired = await client.delete(f"/api/v1/listings/{second.json()['id']}", headers=provider)

    assert paused.json() == expired.json() == {"result": "removed"}


async def test_only_the_owner_deletes(client: AsyncClient, customer, offer):
    stranger = await client.delete(f"/api/v1/listings/{offer}", headers=customer)
    anonymous = await client.delete(f"/api/v1/listings/{offer}")
    missing = await client.delete(
        "/api/v1/listings/00000000-0000-0000-0000-000000000000", headers=customer
    )

    assert (stranger.status_code, stranger.json()["detail"][0]["type"]) == (
        403,
        "not_listing_owner",
    )
    assert anonymous.status_code == 401
    assert missing.status_code == 404
    assert (await client.get(f"/api/v1/listings/{offer}")).status_code == 200
