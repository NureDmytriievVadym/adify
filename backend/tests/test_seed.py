import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from adify_api.accounts.models import Account, AccountRole
from adify_api.core.security import verify_password
from adify_api.listings.models import Listing, ListingStatus
from adify_api.listings.service import locked_fields
from adify_api.orders.models import Order, OrderStatus
from adify_api.seed import (
    ACCOUNTS,
    DEFAULT_PASSWORD,
    LISTINGS,
    ORDERS,
    _account_id,
    _listing_id,
    reset_demo_data,
    seed_demo_data,
)

pytestmark = pytest.mark.anyio


async def counts(sessionmaker: async_sessionmaker[AsyncSession]) -> tuple[int, int]:
    async with sessionmaker() as session:
        accounts = await session.scalar(select(func.count()).select_from(Account))
        listings = await session.scalar(select(func.count()).select_from(Listing))
    return accounts or 0, listings or 0


async def test_creates_demo_accounts_and_listings(sessionmaker):
    result = await seed_demo_data(sessionmaker)

    assert result.accounts_created == len(ACCOUNTS) == 6
    assert result.listings_created == len(LISTINGS) == 13
    assert await counts(sessionmaker) == (6, 13)

    async with sessionmaker() as session:
        customers = await session.scalars(
            select(Account).where(Account.role == AccountRole.CUSTOMER)
        )
        providers = await session.scalars(
            select(Account).where(Account.role == AccountRole.PROVIDER)
        )
        listing = await session.get(Listing, _listing_id("banners-journal"))
    assert len(list(customers)) == 3
    assert len(list(providers)) == 3
    assert listing is not None
    assert listing.specs


async def test_demo_accounts_can_sign_in_with_the_documented_password(sessionmaker):
    await seed_demo_data(sessionmaker)

    async with sessionmaker() as session:
        account = await session.scalar(select(Account).where(Account.email == ACCOUNTS[0].email))
        other = await session.scalar(select(Account).where(Account.email == ACCOUNTS[3].email))

    assert account is not None and other is not None
    assert verify_password(DEFAULT_PASSWORD, account.password_hash)
    assert verify_password(DEFAULT_PASSWORD, other.password_hash)
    assert account.password_hash != other.password_hash


async def test_seeding_twice_is_idempotent(sessionmaker):
    await seed_demo_data(sessionmaker)

    second = await seed_demo_data(sessionmaker)

    assert second.accounts_created == 0
    assert second.listings_created == 0
    assert second.accounts_existing == 6
    assert second.listings_existing == 13
    assert await counts(sessionmaker) == (6, 13)


async def test_reset_recreates_only_demo_rows(sessionmaker):
    async with sessionmaker() as session:
        session.add(
            Account(
                id=uuid.uuid4(),
                display_name="Real User",
                email="real@example.com",
                phone="+380671239999",
                password_hash="x",
                role=AccountRole.CUSTOMER,
            )
        )
        await session.commit()
    await seed_demo_data(sessionmaker)

    result = await seed_demo_data(sessionmaker, reset=True)

    assert result.accounts_removed == 6
    assert result.listings_removed == 13
    assert result.accounts_created == 6
    assert result.listings_created == 13
    assert await counts(sessionmaker) == (7, 13)
    async with sessionmaker() as session:
        assert await session.scalar(select(Account).where(Account.email == "real@example.com"))


async def test_reset_without_demo_data_is_a_no_op(sessionmaker):
    result = await reset_demo_data(sessionmaker)

    assert result.accounts_removed == 0
    assert result.listings_removed == 0
    assert await counts(sessionmaker) == (0, 0)


async def test_fixed_ids_keep_listings_attached_to_the_same_owner(sessionmaker):
    await seed_demo_data(sessionmaker)
    async with sessionmaker() as session:
        account = await session.scalar(select(Account).where(Account.email == ACCOUNTS[3].email))
        listing = await session.scalar(select(Listing).where(Listing.title.like("Your brand,%")))

    assert account is not None and listing is not None
    assert account.id == _account_id("digital-daily")
    assert listing.owner_id == account.id


async def test_an_active_demo_order_locks_one_listing_category(sessionmaker):
    result = await seed_demo_data(sessionmaker)
    again = await seed_demo_data(sessionmaker)

    assert result.orders_created == len(ORDERS) == 1
    assert again.orders_created == 0
    assert again.orders_existing == 1
    async with sessionmaker() as session:
        order = await session.scalar(select(Order))
        locked = await session.get(Listing, _listing_id("banners-journal"))
        open_ = await session.get(Listing, _listing_id("app-discovery"))
        assert order is not None and locked is not None and open_ is not None
        assert order.status == OrderStatus.IN_PROGRESS
        assert order.listing_id == locked.id
        assert order.provider_id == locked.owner_id == _account_id("digital-daily")
        assert order.customer_id == _account_id("olena")
        assert await locked_fields(session, locked) == ["category"]
        assert await locked_fields(session, open_) == []


async def test_reset_removes_demo_orders_before_their_listings(sessionmaker):
    await seed_demo_data(sessionmaker)

    removed = await reset_demo_data(sessionmaker)

    assert removed.orders_removed == 1
    async with sessionmaker() as session:
        assert await session.scalar(select(func.count()).select_from(Order)) == 0


async def test_one_demo_listing_is_expired_and_the_rest_are_active(sessionmaker):
    await seed_demo_data(sessionmaker)

    async with sessionmaker() as session:
        listings = list(await session.scalars(select(Listing)))
    statuses = {listing.id: listing.status for listing in listings}

    assert statuses.pop(_listing_id("articles-newsletter")) == ListingStatus.EXPIRED
    assert set(statuses.values()) == {ListingStatus.ACTIVE}
    expired = next(item for item in listings if item.id == _listing_id("articles-newsletter"))
    assert expired.owner_id == _account_id("digital-daily")
    assert expired.paused_at is not None
