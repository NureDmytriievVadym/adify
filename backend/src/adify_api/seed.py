"""Development-only demo data: six accounts and twelve listings across both roles.

Run inside the backend container while the development stack is up:

    just seed
    just seed --reset

Re-running is safe: accounts are matched by email and listings by a deterministic
UUID, so existing demo rows are left untouched. ``--reset`` removes only rows this
script created (accounts with ``@demo.adify.app`` emails and their listings).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from adify_api.accounts.models import Account, AccountBan, AccountRole
from adify_api.auth.models import RefreshToken
from adify_api.core.config import get_settings
from adify_api.core.db import get_sessionmaker
from adify_api.core.security import hash_password
from adify_api.listings.models import (
    Listing,
    ListingAttachment,
    ListingCategory,
    ListingType,
)

DEFAULT_PASSWORD = "AdifyDemo123"
DEMO_DOMAIN = "demo.adify.app"
DEMO_NAMESPACE = uuid.UUID("d3f4a6b2-6c1e-4f2a-9b8d-7e5c1a2b3c4d")


@dataclass(frozen=True)
class DemoAccount:
    key: str
    display_name: str
    email: str
    phone: str
    role: AccountRole


@dataclass(frozen=True)
class DemoListing:
    key: str
    owner: str
    type: ListingType
    category: ListingCategory
    title: str
    description: str
    price: str
    delivery_days: int | None = None
    specs: tuple[tuple[str, str], ...] = ()


@dataclass
class SeedResult:
    accounts_created: int = 0
    accounts_existing: int = 0
    listings_created: int = 0
    listings_existing: int = 0
    accounts_removed: int = 0
    listings_removed: int = 0
    accounts: list[Account] = field(default_factory=list)


ACCOUNTS: tuple[DemoAccount, ...] = (
    DemoAccount(
        "olena",
        "Olena Marchenko",
        f"olena.marchenko@{DEMO_DOMAIN}",
        "+380501110001",
        AccountRole.CUSTOMER,
    ),
    DemoAccount(
        "andrii",
        "Andrii Bondar",
        f"andrii.bondar@{DEMO_DOMAIN}",
        "+380501110002",
        AccountRole.CUSTOMER,
    ),
    DemoAccount(
        "tetiana",
        "Tetiana Shevchenko",
        f"tetiana.shevchenko@{DEMO_DOMAIN}",
        "+380501110003",
        AccountRole.CUSTOMER,
    ),
    DemoAccount(
        "digital-daily",
        "Digital Daily",
        f"digital.daily@{DEMO_DOMAIN}",
        "+380501110101",
        AccountRole.PROVIDER,
    ),
    DemoAccount(
        "sofiia",
        "Sofiia K.",
        f"sofiia.k@{DEMO_DOMAIN}",
        "+380501110102",
        AccountRole.PROVIDER,
    ),
    DemoAccount(
        "pocket-studio",
        "Pocket Studio",
        f"pocket.studio@{DEMO_DOMAIN}",
        "+380501110103",
        AccountRole.PROVIDER,
    ),
)

LISTINGS: tuple[DemoListing, ...] = (
    DemoListing(
        "banners-journal",
        "digital-daily",
        ListingType.OFFER,
        ListingCategory.WEBSITE_BANNERS,
        "Your brand, front and centre on a design journal",
        "A display banner placement on an independent design journal read by "
        "designers and creative teams. We agree the publication week and the exact "
        "pages before work starts, so you know where your brand will appear.",
        "3500.00",
        5,
        (
            ("File formats", "JPG, PNG, or GIF"),
            ("Dimensions", "300 × 250 px or 728 × 90 px"),
            ("Maximum file size", "150 KB"),
            ("Animation", "Up to 15 seconds"),
            ("Alt text", "Up to 100 characters, no emoji"),
        ),
    ),
    DemoListing(
        "banners-homeware",
        "olena",
        ListingType.REQUEST,
        ListingCategory.WEBSITE_BANNERS,
        "Looking for banner placements on home and lifestyle sites",
        "We are launching a small homeware collection and want two weeks of banner "
        "coverage on Ukrainian home, lifestyle, or interior websites. Share your "
        "audience, available formats, and the earliest start date.",
        "4500.00",
        7,
        (("Formats", "JPG or PNG"), ("Preferred sizes", "728 × 90 px, 300 × 250 px")),
    ),
    DemoListing(
        "articles-slow-edit",
        "sofiia",
        ListingType.OFFER,
        ListingCategory.SPONSORED_ARTICLES,
        "A sponsored story in The Slow Edit",
        "An editorial feature on our slow-living blog, written by our editor with "
        "your input. The article stays online indefinitely and is shared with our "
        "newsletter audience. We agree the angle and images before writing begins.",
        "5200.00",
        10,
        (
            ("Article length", "1,000–3,000 characters"),
            ("Headline", "Up to 100 characters, no emoji"),
            ("Images", "Up to 5 JPG or PNG files, 2 MB each"),
            ("Links", "Up to 3"),
        ),
    ),
    DemoListing(
        "articles-b2b",
        "andrii",
        ListingType.REQUEST,
        ListingCategory.SPONSORED_ARTICLES,
        "B2B software story looking for a business publication",
        "We build inventory software for small retailers and want a sponsored "
        "article in a Ukrainian business or retail publication. We can provide a "
        "case study, product screenshots, and a technical reviewer.",
        "7000.00",
        14,
        (("Topic", "Retail operations"), ("Tone", "Practical, no hype")),
    ),
    DemoListing(
        "social-everyday",
        "sofiia",
        ListingType.OFFER,
        ListingCategory.SOCIAL_MEDIA_POSTS,
        "An Instagram post for brands with a little more soul",
        "A thoughtfully styled Instagram post for a lifestyle, home, or independent "
        "brand. We agree on the concept, caption, and publication date before work "
        "begins. The post stays in the feed as a permanent placement.",
        "2400.00",
        3,
        (
            ("Image formats", "JPG or PNG, up to 8 MB"),
            ("Aspect ratio", "1:1, 4:5, or 9:16"),
            ("Caption", "Up to 2,200 characters; emoji allowed"),
            ("Hashtags", "Up to 30"),
        ),
    ),
    DemoListing(
        "social-coffee",
        "tetiana",
        ListingType.REQUEST,
        ListingCategory.SOCIAL_MEDIA_POSTS,
        "Launch posts for a specialty coffee subscription",
        "We need three consecutive Instagram posts introducing our coffee "
        "subscription to a Ukrainian audience aged 22–40. We will supply the bag "
        "design, product photos, and the launch offer.",
        "3600.00",
        6,
        (("Posts", "3"), ("Formats", "JPG or PNG"), ("Caption tone", "Warm and simple")),
    ),
    DemoListing(
        "video-creator",
        "pocket-studio",
        ListingType.OFFER,
        ListingCategory.VIDEO_INTEGRATIONS,
        "A natural YouTube integration, made for your brand",
        "A scripted 60-second brand integration inside a technology review video. "
        "We share the draft script for approval, then film and publish. The video "
        "remains available on the channel after publication.",
        "9000.00",
        12,
        (
            ("Integration length", "30–120 seconds"),
            ("Script", "Up to 3,000 characters"),
            ("Reference video", "Optional MP4, up to 500 MB"),
        ),
    ),
    DemoListing(
        "video-saas",
        "andrii",
        ListingType.REQUEST,
        ListingCategory.VIDEO_INTEGRATIONS,
        "SaaS walkthrough for a YouTube product review",
        "We want a short walkthrough of our inventory dashboard inside a YouTube "
        "review of small-business tools. We can give a demo account and a list of "
        "talking points; editorial control stays with the creator.",
        "6500.00",
        18,
        (("Length", "45–90 seconds"), ("Language", "Ukrainian or English")),
    ),
    DemoListing(
        "stream-overlay",
        "pocket-studio",
        ListingType.OFFER,
        ListingCategory.STREAM_ADS,
        "Bring your brand into the live conversation",
        "A stream overlay and a spoken brand mention during a live gaming "
        "broadcast. We agree the placement, the mention script, and the stream "
        "date in advance. The overlay is visible for the whole agreed segment.",
        "1800.00",
        4,
        (
            ("Overlay", "PNG, 1920 × 1080 or 728 × 90 px"),
            ("Maximum file size", "1 MB"),
            ("Spoken mention", "Up to 500 characters"),
            ("Duration", "15, 30, or 60 seconds"),
        ),
    ),
    DemoListing(
        "stream-boardgames",
        "olena",
        ListingType.REQUEST,
        ListingCategory.STREAM_ADS,
        "Board-game publisher looking for two live stream slots",
        "We publish family board games and want two live placements in Ukrainian "
        "gaming or family streamer channels. We will provide the overlay artwork "
        "and a short mention script.",
        "2200.00",
        9,
        (("Slots", "2"), ("Overlay format", "PNG, 1920 × 1080 px")),
    ),
    DemoListing(
        "app-discovery",
        "digital-daily",
        ListingType.OFFER,
        ListingCategory.IN_APP_MOBILE_ADS,
        "A little screen space for your next big idea",
        "An in-app advertising placement in a reading and discovery app. Choose a "
        "banner, an interstitial, or a short video; we agree the placement and the "
        "campaign window before the assets are handed over.",
        "2800.00",
        5,
        (
            ("Banner", "320 × 50 or 300 × 250 px; up to 150 KB"),
            ("Interstitial", "1080 × 1920 px; up to 1 MB"),
            ("Video", "MP4 H.264, up to 30 seconds and 10 MB"),
        ),
    ),
    DemoListing(
        "app-fitness",
        "tetiana",
        ListingType.REQUEST,
        ListingCategory.IN_APP_MOBILE_ADS,
        "Fitness app wants a two-week in-app campaign",
        "We are promoting a training-plan subscription inside a Ukrainian fitness "
        "or habit-tracking app. We prefer a 300 × 250 banner and can supply three "
        "creative variants for testing.",
        "3900.00",
        8,
        (("Format", "300 × 250 px PNG"), ("Duration", "Two weeks")),
    ),
)


class SeedError(RuntimeError):
    """The database contains a conflicting row the script will not overwrite."""


def _account_id(key: str) -> uuid.UUID:
    return uuid.uuid5(DEMO_NAMESPACE, f"account:{key}")


def _listing_id(key: str) -> uuid.UUID:
    return uuid.uuid5(DEMO_NAMESPACE, f"listing:{key}")


async def _demo_accounts(session: AsyncSession) -> list[Account]:
    emails = [account.email for account in ACCOUNTS]
    return list(await session.scalars(select(Account).where(Account.email.in_(emails))))


async def reset_demo_data(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> SeedResult:
    """Remove only the demo accounts and their listings; other rows are untouched."""
    result = SeedResult()
    async with sessionmaker() as session:
        accounts = await _demo_accounts(session)
        if not accounts:
            await session.commit()
            return result
        account_ids = [account.id for account in accounts]
        listing_ids = list(
            await session.scalars(select(Listing.id).where(Listing.owner_id.in_(account_ids)))
        )
        if listing_ids:
            await session.execute(
                delete(ListingAttachment).where(ListingAttachment.listing_id.in_(listing_ids))
            )
            await session.execute(delete(Listing).where(Listing.id.in_(listing_ids)))
        await session.execute(delete(AccountBan).where(AccountBan.account_id.in_(account_ids)))
        await session.execute(delete(RefreshToken).where(RefreshToken.account_id.in_(account_ids)))
        await session.execute(delete(Account).where(Account.id.in_(account_ids)))
        await session.commit()
        result.accounts_removed = len(accounts)
        result.listings_removed = len(listing_ids)
    return result


async def seed_demo_data(
    sessionmaker: async_sessionmaker[AsyncSession],
    password: str = DEFAULT_PASSWORD,
    reset: bool = False,
) -> SeedResult:
    """Create the demo accounts and listings, or wipe and recreate them with ``reset``."""
    result = SeedResult()
    if reset:
        removed = await reset_demo_data(sessionmaker)
        result.accounts_removed = removed.accounts_removed
        result.listings_removed = removed.listings_removed

    now = datetime.now(UTC)
    accounts: dict[str, Account] = {}

    async with sessionmaker() as session:
        for spec in ACCOUNTS:
            account = await session.scalar(select(Account).where(Account.email == spec.email))
            if account is not None:
                if account.role != spec.role:
                    raise SeedError(
                        f"{spec.email} exists with role {account.role.value}, "
                        f"expected {spec.role.value}; remove the conflicting row first."
                    )
                result.accounts_existing += 1
            else:
                account = Account(
                    id=_account_id(spec.key),
                    display_name=spec.display_name,
                    email=spec.email,
                    phone=spec.phone,
                    password_hash=hash_password(password),
                    role=spec.role,
                )
                session.add(account)
                await session.flush()
                result.accounts_created += 1
            accounts[spec.key] = account
        await session.commit()
        result.accounts = [accounts[spec.key] for spec in ACCOUNTS]

        for index, spec in enumerate(LISTINGS):
            listing_id = _listing_id(spec.key)
            if await session.get(Listing, listing_id) is not None:
                result.listings_existing += 1
                continue
            session.add(
                Listing(
                    id=listing_id,
                    owner_id=accounts[spec.owner].id,
                    type=spec.type,
                    category=spec.category,
                    title=spec.title,
                    description=spec.description,
                    price=Decimal(spec.price),
                    delivery_days=spec.delivery_days,
                    specs=[{"label": label, "value": value} for label, value in spec.specs],
                    created_at=now - timedelta(hours=index * 3),
                )
            )
            result.listings_created += 1
        await session.commit()

    return result


def _print_summary(result: SeedResult, password: str) -> None:
    if result.accounts_removed or result.listings_removed:
        print(
            f"Removed {result.accounts_removed} demo accounts "
            f"and {result.listings_removed} demo listings."
        )
    print(
        f"Accounts: {result.accounts_created} created, {result.accounts_existing} already present."
    )
    print(
        f"Listings: {result.listings_created} created, {result.listings_existing} already present."
    )
    print(f"\nPassword for every demo account: {password}\n")
    print(f"{'ROLE':<9} {'EMAIL':<40} NAME")
    for account in result.accounts:
        print(f"{account.role.value:<9} {account.email:<40} {account.display_name}")
    print("\nSign in at http://localhost:5173/sign-in")


async def _run(args: argparse.Namespace) -> None:
    if not get_settings().allow_seed:
        raise SystemExit(
            "Refusing to seed: set ADIFY_ALLOW_SEED=true for this command. "
            "Use `just seed` for the local development database."
        )
    result = await seed_demo_data(get_sessionmaker(), password=args.password, reset=args.reset)
    _print_summary(result, args.password)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m adify_api.seed",
        description="Fill the development database with Adify demo accounts and listings.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="delete existing demo rows first, then recreate them",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("ADIFY_SEED_PASSWORD", DEFAULT_PASSWORD),
        help=f"password for every demo account (default: {DEFAULT_PASSWORD})",
    )
    _run_args = parser.parse_args()
    try:
        asyncio.run(_run(_run_args))
    except SeedError as error:
        raise SystemExit(f"Seed failed: {error}") from None


if __name__ == "__main__":
    main()
