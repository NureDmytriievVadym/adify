"""ADY-015: expire listings by the owner's date or after three months of inactivity."""

import uuid
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage

import pytest
from conftest import verify_contacts
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from adify_api import jobs
from adify_api.accounts.models import Account
from adify_api.core import mail
from adify_api.listings.expiry import (
    expire_due_listings,
    expire_inactive_listings,
    expiry_moment,
    months_before,
    notify_inactive_owners,
    today_in_kyiv,
)
from adify_api.listings.models import ExpiryReason, Listing, ListingStatus

pytestmark = pytest.mark.anyio

OFFER = {
    "category": "website-banners",
    "title": "Your brand on a design journal",
    "description": "A display banner placement on an independent design journal.",
    "price_uah": "3500.00",
    "delivery_days": 5,
    "expiry_date": (today_in_kyiv() + timedelta(days=30)).isoformat(),
    "specs": [{"label": "Dimensions", "value": "728 x 90 px"}],
}
REQUEST = {
    "category": "sponsored-articles",
    "title": "Looking for a home for our story",
    "description": "We want a website to publish a sponsored article about our brand.",
    "budget_uah": "4500",
    "expiry_date": (today_in_kyiv() + timedelta(days=30)).isoformat(),
    "specs": [],
}


async def sign_up(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession], role: str, email: str
) -> dict[str, str]:
    body = {
        "display_name": f"Test {role}",
        "email": email,
        "phone": "+38067" + str(abs(hash(email)) % 10_000_000).zfill(7),
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
async def customer(client: AsyncClient, sessionmaker) -> dict[str, str]:
    return await sign_up(client, sessionmaker, "customer", "customer@example.com")


@pytest.fixture
async def provider(client: AsyncClient, sessionmaker) -> dict[str, str]:
    return await sign_up(client, sessionmaker, "provider", "provider@example.com")


def error_type(response) -> str:
    return response.json()["detail"][0]["type"]


async def publish(client: AsyncClient, headers: dict[str, str], body: dict | None = None) -> dict:
    response = await client.post("/api/v1/listings/offers", json=body or OFFER, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def set_login(
    sessionmaker: async_sessionmaker[AsyncSession], email: str, value: datetime | None
) -> None:
    async with sessionmaker() as session:
        await session.execute(
            update(Account).where(Account.email == email).values(last_login_at=value)
        )
        await session.commit()


async def listing_status(
    sessionmaker: async_sessionmaker[AsyncSession], listing_id: str
) -> tuple[ListingStatus, ExpiryReason | None, datetime | None]:
    async with sessionmaker() as session:
        listing = await session.get(Listing, uuid.UUID(listing_id))
        assert listing is not None
        return listing.status, listing.expired_reason, listing.expiry_notified_at


def parsed(moment: str) -> datetime:
    value = datetime.fromisoformat(moment)
    return value if value.tzinfo else value.replace(tzinfo=UTC)


# FR-021 and FR-012: the owner-selected date


async def test_creating_a_listing_requires_an_expiry_date(client: AsyncClient, provider):
    body = {key: value for key, value in OFFER.items() if key != "expiry_date"}

    response = await client.post("/api/v1/listings/offers", json=body, headers=provider)

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "expiry_date"]


@pytest.mark.parametrize("days", [-1, -30])
async def test_rejects_an_expiry_date_in_the_past(client: AsyncClient, provider, days):
    response = await client.post(
        "/api/v1/listings/offers",
        json=OFFER | {"expiry_date": (today_in_kyiv() + timedelta(days=days)).isoformat()},
        headers=provider,
    )

    assert response.status_code == 422
    assert error_type(response) == "expiry_date_passed"


async def test_today_is_allowed_and_ends_at_2359_kyiv(client: AsyncClient, provider):
    today = today_in_kyiv()

    listing = await publish(client, provider, OFFER | {"expiry_date": today.isoformat()})

    assert listing["expiry_date"] == today.isoformat()
    assert parsed(listing["expires_at"]) == expiry_moment(today)


async def test_the_owner_can_move_a_future_expiry_date(client: AsyncClient, provider):
    listing = await publish(client, provider)
    later = today_in_kyiv() + timedelta(days=60)

    response = await client.patch(
        f"/api/v1/listings/{listing['id']}",
        json={"expiry_date": later.isoformat()},
        headers=provider,
    )

    assert response.status_code == 200
    assert response.json()["expiry_date"] == later.isoformat()
    assert parsed(response.json()["expires_at"]) == expiry_moment(later)


async def test_an_expired_listing_cannot_be_extended(client: AsyncClient, provider, sessionmaker):
    listing = await publish(client, provider)
    async with sessionmaker() as session:
        await session.execute(
            update(Listing)
            .where(Listing.id == uuid.UUID(listing["id"]))
            .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        await session.commit()

    extension = await client.patch(
        f"/api/v1/listings/{listing['id']}",
        json={"expiry_date": (today_in_kyiv() + timedelta(days=30)).isoformat()},
        headers=provider,
    )
    expired = (await client.get(f"/api/v1/listings/{listing['id']}")).json()
    # The edit form sends the unchanged date back; that is not an extension.
    title_edit = await client.patch(
        f"/api/v1/listings/{listing['id']}",
        json={
            "title": "A fresh title for an expired listing",
            "expiry_date": expired["expiry_date"],
        },
        headers=provider,
    )

    assert extension.status_code == 409
    assert error_type(extension) == "listing_expired"
    assert extension.json()["detail"][0]["loc"] == ["body", "expiry_date"]
    assert title_edit.status_code == 200
    assert title_edit.json()["title"] == "A fresh title for an expired listing"
    assert title_edit.json()["status"] == "expired"


# FR-021/FR-022: the cron jobs


async def test_the_date_job_expires_each_due_listing_once(
    client: AsyncClient, provider, sessionmaker
):
    day = today_in_kyiv() + timedelta(days=1)
    due = await publish(client, provider, OFFER | {"expiry_date": day.isoformat()})
    future = await publish(client, provider, OFFER | {"title": "A future listing"})
    when = expiry_moment(day) + timedelta(seconds=1)

    first = await expire_due_listings(sessionmaker(), when)
    second = await expire_due_listings(sessionmaker(), when)

    assert [str(listing.id) for listing in first] == [due["id"]]
    assert second == []
    assert await listing_status(sessionmaker, due["id"]) == (
        ListingStatus.EXPIRED,
        ExpiryReason.DATE,
        None,
    )
    assert (await listing_status(sessionmaker, future["id"]))[0] == ListingStatus.ACTIVE
    assert due["id"] not in [
        item["id"] for item in (await client.get("/api/v1/listings")).json()["items"]
    ]


async def test_the_job_entrypoint_runs_the_selected_rule(
    client: AsyncClient, provider, sessionmaker, monkeypatch
):
    day = today_in_kyiv() + timedelta(days=1)
    await publish(client, provider, OFFER | {"expiry_date": day.isoformat()})
    monkeypatch.setattr(jobs, "get_sessionmaker", lambda: sessionmaker)

    result = await jobs.run(expiry_moment(day) + timedelta(seconds=1), job="date")

    assert result.listings_expired_by_date == 1
    assert result.orders_canceled == 0
    assert result.notices_sent == 0


async def test_the_inactivity_job_expires_only_active_listings(
    client: AsyncClient, customer, provider, sessionmaker
):
    inactive = await sign_up(client, sessionmaker, "provider", "inactive@example.com")
    active = await sign_up(client, sessionmaker, "provider", "active@example.com")
    stale = await publish(client, inactive)
    paused = await publish(client, inactive, OFFER | {"title": "A paused listing"})
    await client.post(f"/api/v1/listings/{paused['id']}/pause", headers=inactive)
    fresh = await publish(client, active)
    now = datetime.now(UTC)
    await set_login(sessionmaker, "inactive@example.com", months_before(now, 3) - timedelta(days=1))

    expired = await expire_inactive_listings(sessionmaker(), now)

    assert [str(listing.id) for listing in expired] == [stale["id"]]
    assert await listing_status(sessionmaker, stale["id"]) == (
        ListingStatus.EXPIRED,
        ExpiryReason.INACTIVITY,
        None,
    )
    assert (await listing_status(sessionmaker, paused["id"]))[0] == ListingStatus.PAUSED
    assert (await listing_status(sessionmaker, fresh["id"]))[0] == ListingStatus.ACTIVE


async def test_inactivity_falls_back_to_the_account_creation_date(
    client: AsyncClient, provider, sessionmaker
):
    listing = await publish(client, provider)
    now = datetime.now(UTC)
    async with sessionmaker() as session:
        await session.execute(
            update(Account)
            .where(Account.email == "provider@example.com")
            .values(last_login_at=None, created_at=months_before(now, 3) - timedelta(days=2))
        )
        await session.commit()

    expired = await expire_inactive_listings(sessionmaker(), now)

    assert [str(item.id) for item in expired] == [listing["id"]]


async def test_inactivity_notice_lists_the_expired_listings_once(
    client: AsyncClient, customer, outbox: list[EmailMessage], sessionmaker
):
    inactive = await sign_up(client, sessionmaker, "provider", "inactive@example.com")
    first = await publish(client, inactive)
    second = await publish(client, inactive, OFFER | {"title": "Another stale listing"})
    now = datetime.now(UTC)
    await set_login(sessionmaker, "inactive@example.com", months_before(now, 3) - timedelta(days=1))

    await expire_inactive_listings(sessionmaker(), now)
    before = len(outbox)
    sent = await notify_inactive_owners(sessionmaker())
    repeated = await notify_inactive_owners(sessionmaker())

    assert sent == 1
    assert repeated == 0
    assert len(outbox) == before + 1
    message = outbox[-1]
    assert message["To"] == "inactive@example.com"
    body = message.get_content()
    assert first["title"] in body and second["title"] in body
    for listing in (first, second):
        assert (await listing_status(sessionmaker, listing["id"]))[2] is not None


async def test_a_failed_expiry_notice_is_retried(
    client: AsyncClient, customer, monkeypatch, sessionmaker
):
    inactive = await sign_up(client, sessionmaker, "provider", "inactive@example.com")
    await publish(client, inactive)
    now = datetime.now(UTC)
    await set_login(sessionmaker, "inactive@example.com", months_before(now, 3) - timedelta(days=1))
    await expire_inactive_listings(sessionmaker(), now)

    def broken(message):
        raise OSError("smtp is down")

    monkeypatch.setattr(mail, "_send", broken)
    assert await notify_inactive_owners(sessionmaker()) == 0

    delivered: list[EmailMessage] = []
    monkeypatch.setattr(mail, "_send", delivered.append)
    assert await notify_inactive_owners(sessionmaker()) == 1
    assert len(delivered) == 1


# A successful sign-in, not a token refresh, resets the inactivity clock.


async def test_successful_sign_in_records_last_login(client: AsyncClient, provider, sessionmaker):
    async with sessionmaker() as session:
        before = await session.scalar(
            select(Account.last_login_at).where(Account.email == "provider@example.com")
        )
    await client.post(
        "/api/v1/auth/sign-in",
        json={"email": "provider@example.com", "password": "secret123"},
    )
    async with sessionmaker() as session:
        after = await session.scalar(
            select(Account.last_login_at).where(Account.email == "provider@example.com")
        )

    assert before is not None and after is not None
    assert after >= before
    assert months_before(after, 3) < after


async def test_refresh_and_failed_sign_in_do_not_reset_the_inactivity_clock(
    client: AsyncClient, provider, sessionmaker
):
    async with sessionmaker() as session:
        before = await session.scalar(
            select(Account.last_login_at).where(Account.email == "provider@example.com")
        )

    refreshed = await client.post("/api/v1/auth/refresh", json={})
    wrong = await client.post(
        "/api/v1/auth/sign-in",
        json={"email": "provider@example.com", "password": "not-the-password"},
    )
    async with sessionmaker() as session:
        after = await session.scalar(
            select(Account.last_login_at).where(Account.email == "provider@example.com")
        )

    assert refreshed.status_code == 200
    assert wrong.status_code == 401
    assert after == before
