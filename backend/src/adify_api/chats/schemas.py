import uuid
from datetime import datetime

from pydantic import BaseModel

from adify_api.accounts.models import Account
from adify_api.chats.models import Chat
from adify_api.listings.models import ListingStatus, ListingType
from adify_api.listings.schemas import OwnerResponse


class ChatListing(BaseModel):
    id: uuid.UUID
    title: str
    type: ListingType
    status: ListingStatus


class ChatResponse(BaseModel):
    """A chat from the viewer's side: only the other participant's public profile (FR-087)."""

    id: uuid.UUID
    listing: ChatListing | None
    counterpart: OwnerResponse
    created_at: datetime

    @classmethod
    def for_viewer(cls, chat: Chat, viewer: Account) -> "ChatResponse":
        other = chat.provider if viewer.id == chat.customer_id else chat.customer
        listing = chat.listing
        return cls(
            id=chat.id,
            listing=ChatListing(
                id=listing.id, title=listing.title, type=listing.type, status=listing.status
            )
            if listing
            else None,
            counterpart=OwnerResponse(
                id=other.id, display_name=other.display_name, role=other.role
            ),
            created_at=chat.created_at,
        )
