import uuid
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from adify_api.accounts.models import Account, AccountRole
from adify_api.chats.models import Chat
from adify_api.listings.models import Listing


class ChatError(Exception):
    def __init__(self, status_code: int, type_: str, msg: str) -> None:
        super().__init__(msg)
        self.status_code = status_code
        self.type = type_
        self.msg = msg


def _participants(listing: Listing, account: Account) -> tuple[uuid.UUID, uuid.UUID]:
    owner = listing.owner
    if owner.role == AccountRole.CUSTOMER:
        return owner.id, account.id
    return account.id, owner.id


async def _find(session: AsyncSession, listing: Listing, account: Account) -> Chat | None:
    customer_id, provider_id = _participants(listing, account)
    return await session.scalar(
        select(Chat).where(
            Chat.listing_id == listing.id,
            Chat.customer_id == customer_id,
            Chat.provider_id == provider_id,
        )
    )


async def start_chat(
    session: AsyncSession, listing: Listing, account: Account
) -> tuple[Chat, bool]:
    """Open the chat with the listing owner, or return the one already started.

    The FR-026 checks (verified, not own listing, opposite roles) run before this.
    """
    if existing := await _find(session, listing, account):
        return existing, False
    customer_id, provider_id = _participants(listing, account)
    chat = Chat(
        listing_id=listing.id,
        customer_id=customer_id,
        provider_id=provider_id,
        created_at=datetime.now(UTC),
    )
    session.add(chat)
    try:
        await session.commit()
    except IntegrityError:
        # Two clicks raced; the other request created the chat first.
        await session.rollback()
        return await _find(session, listing, account), False
    await session.refresh(chat)
    return chat, True


async def list_chats(session: AsyncSession, account: Account) -> list[Chat]:
    chats = await session.scalars(
        select(Chat)
        .where(or_(Chat.customer_id == account.id, Chat.provider_id == account.id))
        .order_by(Chat.created_at.desc(), Chat.id)
    )
    return list(chats)


async def get_chat(session: AsyncSession, chat_id: uuid.UUID, account: Account) -> Chat:
    """FR-027: only the chat's customer and provider may open it."""
    chat = await session.get(Chat, chat_id)
    if chat is None:
        raise ChatError(404, "chat_not_found", "This chat could not be found.")
    if account.id not in (chat.customer_id, chat.provider_id):
        raise ChatError(
            403, "not_chat_participant", "Only the two participants can open this chat."
        )
    return chat
