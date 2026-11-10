import uuid
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from adify_api.accounts.models import Account
from adify_api.chats.models import Chat
from adify_api.listings.models import Listing
from adify_api.listings.service import ListingError, ensure_accepts_orders
from adify_api.orders.models import Order, OrderStage, OrderStatus
from adify_api.orders.schemas import OrderCreate


class OrderError(Exception):
    def __init__(self, status_code: int, type_: str, msg: str) -> None:
        super().__init__(msg)
        self.status_code = status_code
        self.type = type_
        self.msg = msg


def requirements_snapshot(listing: Listing) -> dict:
    """FR-118: a frozen copy of the listing's technical requirements."""
    specs = [{"label": spec["label"], "value": spec["value"]} for spec in listing.specs]
    return {
        "listing_type": listing.type.value,
        "category": listing.category.value,
        "has_requirements": bool(specs),
        "specs": specs,
    }


async def create_order(
    session: AsyncSession, chat: Chat, account: Account, data: OrderCreate
) -> Order:
    """FR-031, FR-033–FR-037: the listing owner records an order with the other participant."""
    listing = chat.listing
    if listing is None:
        raise OrderError(409, "listing_deleted", "The listing was deleted, so no new orders.")
    if listing.owner_id != account.id:
        raise OrderError(403, "not_listing_owner", "Only the listing owner can create an order.")
    try:
        ensure_accepts_orders(listing)
    except ListingError as error:
        raise OrderError(error.status_code, error.type, error.msg) from None
    order = Order(
        listing_id=listing.id,
        chat_id=chat.id,
        owner_id=account.id,
        customer_id=chat.customer_id,
        provider_id=chat.provider_id,
        status=OrderStatus.AWAITING_PAYMENT,
        details=data.details,
        price=data.price_uah,
        deadline=data.deadline,
        requirements=requirements_snapshot(listing),
        created_at=datetime.now(UTC),
        stages=[
            OrderStage(position=index, title=stage.title, deadline=stage.deadline)
            for index, stage in enumerate(data.stages)
        ],
    )
    session.add(order)
    await session.commit()
    await session.refresh(order)
    return order


async def chat_orders(session: AsyncSession, chat: Chat) -> list[Order]:
    orders = await session.scalars(
        select(Order).where(Order.chat_id == chat.id).order_by(Order.created_at.desc(), Order.id)
    )
    return list(orders)


async def get_order(session: AsyncSession, order_id: uuid.UUID, account: Account) -> Order:
    order = await session.get(Order, order_id)
    if order is None:
        raise OrderError(404, "order_not_found", "This order could not be found.")
    if account.id not in (order.customer_id, order.provider_id):
        raise OrderError(
            403, "not_order_participant", "Only the two participants can see this order."
        )
    return order


async def my_orders(session: AsyncSession, account: Account) -> list[Order]:
    orders = await session.scalars(
        select(Order)
        .where(or_(Order.customer_id == account.id, Order.provider_id == account.id))
        .order_by(Order.created_at.desc(), Order.id)
    )
    return list(orders)
