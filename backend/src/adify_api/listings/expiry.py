"""FR-021–FR-023: listing expiry by the owner's date and by account inactivity.

A listing expires at 23:59 Kyiv time on the date its owner selected (FR-021) and,
regardless of that date, when its owner has not signed in for three consecutive
months (FR-022). Both rules are applied by :mod:`adify_api.jobs`, which runs once per
invocation from an external cron.

The owner's date is stored as the UTC instant of 23:59 ``Europe/Kyiv``; the helpers
here convert between that instant and the calendar date the owner sees.
"""

from __future__ import annotations

import calendar
import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adify_api.accounts.models import Account
from adify_api.core.config import get_settings
from adify_api.core.mail import DeliveryError, send_email
from adify_api.listings.models import ExpiryReason, Listing

logger = logging.getLogger(__name__)
KYIV = ZoneInfo("Europe/Kyiv")
INACTIVITY_MONTHS = 3


def aware(moment: datetime) -> datetime:
    """SQLite drops the zone of stored timestamps; every stored time is UTC."""
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def expiry_moment(day: date) -> datetime:
    """FR-021: 23:59 Kyiv time on the selected date, as a UTC instant."""
    return datetime.combine(day, time(23, 59), tzinfo=KYIV).astimezone(UTC)


def expiry_date(moment: datetime) -> date:
    """The calendar date the owner selected, read back in Kyiv time."""
    return aware(moment).astimezone(KYIV).date()


def today_in_kyiv(now: datetime | None = None) -> date:
    return (now or datetime.now(UTC)).astimezone(KYIV).date()


def months_before(moment: datetime, months: int) -> datetime:
    """The same day ``months`` calendar months earlier, clamped to the month's length."""
    month_index = moment.year * 12 + (moment.month - 1) - months
    year, month = divmod(month_index, 12)
    month += 1
    day = min(moment.day, calendar.monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)


@dataclass
class InactivityExpiry:
    """The listings of one inactive owner that the inactivity job expired."""

    account: Account
    listings: list[Listing]


async def expire_due_listings(session: AsyncSession, now: datetime | None = None) -> list[Listing]:
    """FR-021: record the ``expired`` status once the owner's date has passed.

    The status is already derived when a listing is read; storing ``expired_at`` makes
    the change explicit, keeps it stable, and records why it happened. Paused listings
    expire on their date as well, since expiry wins over the pause (FR-019).
    """
    moment = aware(now or datetime.now(UTC))
    listings = list(
        await session.scalars(
            select(Listing)
            .where(
                Listing.deleted_at.is_(None),
                Listing.expired_at.is_(None),
                Listing.expires_at <= moment,
            )
            .order_by(Listing.expires_at, Listing.id)
        )
    )
    for listing in listings:
        listing.expired_at = moment
        listing.expired_reason = ExpiryReason.DATE
    await session.commit()
    return listings


async def expire_inactive_listings(
    session: AsyncSession, now: datetime | None = None
) -> list[Listing]:
    """FR-022: expire the active listings of owners idle for three consecutive months.

    A user counts as idle from their last successful sign-in, or from account creation
    when they have never signed in. Only listings whose status is ``active`` are
    affected: paused, soft-deleted, and already expired listings are left as they are.
    """
    moment = aware(now or datetime.now(UTC))
    cutoff = months_before(moment, INACTIVITY_MONTHS)
    accounts = list(await session.scalars(select(Account)))
    expired: list[Listing] = []
    for account in accounts:
        last_active = aware(account.last_login_at or account.created_at)
        if last_active >= cutoff:
            continue
        listings = list(
            await session.scalars(
                select(Listing)
                .where(
                    Listing.owner_id == account.id,
                    Listing.deleted_at.is_(None),
                    Listing.expired_at.is_(None),
                    Listing.paused_at.is_(None),
                    Listing.expires_at > moment,
                )
                .order_by(Listing.created_at, Listing.id)
            )
        )
        for listing in listings:
            listing.expired_at = moment
            listing.expired_reason = ExpiryReason.INACTIVITY
        expired.extend(listings)
    await session.commit()
    return expired


def inactivity_notices(listings: list[Listing]) -> list[tuple[Account, list[Listing]]]:
    """Group inactivity-expired listings by owner, keeping only unnotified ones."""
    owners: dict[object, tuple[Account, list[Listing]]] = {}
    for listing in listings:
        if listing.expiry_notified_at is not None:
            continue
        group = owners.setdefault(listing.owner_id, (listing.owner, []))
        group[1].append(listing)
    return [(account, group) for account, group in owners.values()]


async def deliver_inactivity_notice(account: Account, listings: list[Listing]) -> None:
    """FR-023 and COM-003: email the owner once about their inactivity-expired listings."""
    settings = get_settings()
    lines = "\n".join(
        f"- {listing.title} ({settings.web_base_url}/listings/{listing.id})" for listing in listings
    )
    await send_email(
        account.email,
        "Your Adify listings have expired",
        f"Hello {account.display_name},\n\n"
        "Because the account had not been used for three months, these listings "
        f"have expired and are no longer shown in the marketplace:\n\n{lines}\n\n"
        "Sign in and publish a new listing when you are ready to advertise again.\n\n"
        "The Adify team\n",
    )


async def notify_inactive_owners(session: AsyncSession) -> int:
    """Send FR-023 notices, retrying any that failed on an earlier run."""
    listings = list(
        await session.scalars(
            select(Listing).where(
                Listing.expired_reason == ExpiryReason.INACTIVITY,
                Listing.expiry_notified_at.is_(None),
            )
        )
    )
    sent = 0
    for account, group in inactivity_notices(listings):
        try:
            await deliver_inactivity_notice(account, group)
        except DeliveryError:
            logger.exception("Could not email the expiry notice to account %s", account.id)
            continue
        moment = datetime.now(UTC)
        for listing in group:
            listing.expiry_notified_at = moment
        sent += 1
    await session.commit()
    return sent
