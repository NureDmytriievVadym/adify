"""Scheduled jobs, run once per invocation by cron: ``python -m adify_api.jobs``.

FR-132: cancel paid orders whose provider did not start work in time and release their
Mono holds. Run it at least daily.

FR-021: expire listings at 23:59 Kyiv time on the date their owner selected.
FR-022: expire the active listings of owners who have not signed in for three months.
FR-023: email those owners through the COM-003 channel (email is the interim choice).

Use ``--job orders`` for the order timeout, ``--job date`` at 23:59 Europe/Kyiv for the
owner-selected dates, and ``--job inactivity`` for the three-month rule and notices.
``--job listings`` runs both listing rules without touching orders; the default ``all``
runs every job. ``--now`` replays a later moment for demos and checks.
"""

import argparse
import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from adify_api.core.db import get_sessionmaker
from adify_api.listings.expiry import (
    expire_due_listings,
    expire_inactive_listings,
    notify_inactive_owners,
)
from adify_api.orders.workflow import cancel_unstarted_orders
from adify_api.payments.mono import get_mono

logger = logging.getLogger(__name__)


@dataclass
class JobResult:
    orders_canceled: int = 0
    listings_expired_by_date: int = 0
    listings_expired_by_inactivity: int = 0
    notices_sent: int = 0


async def run(now: datetime | None = None, job: str = "all") -> JobResult:
    """Run the selected jobs once and return their counts."""
    moment = now or datetime.now(UTC)
    result = JobResult()

    if job in ("all", "orders"):
        mono = get_mono()
        if mono is None:
            raise SystemExit(
                "Mono is not configured (ADIFY_MONO_TOKEN), so holds cannot be released."
            )
        async with get_sessionmaker()() as session:
            canceled = await cancel_unstarted_orders(session, mono, moment)
        for order in canceled:
            print(f"Canceled order {order.id}: work did not start in time; the hold was released.")
        result.orders_canceled = len(canceled)

    if job in ("all", "listings", "date", "inactivity"):
        async with get_sessionmaker()() as session:
            due = (
                await expire_due_listings(session, moment)
                if job in ("all", "listings", "date")
                else []
            )
            inactive = (
                await expire_inactive_listings(session, moment)
                if job in ("all", "listings", "inactivity")
                else []
            )
            notices = (
                await notify_inactive_owners(session)
                if job in ("all", "listings", "inactivity")
                else 0
            )
        for listing in due:
            print(f"Expired by date: {listing.id} — {listing.title}")
        for listing in inactive:
            print(f"Expired by inactivity: {listing.id} — {listing.title}")
        result.listings_expired_by_date = len(due)
        result.listings_expired_by_inactivity = len(inactive)
        result.notices_sent = notices

    print(
        "Jobs: "
        f"{result.orders_canceled} order(s) canceled, "
        f"{result.listings_expired_by_date} listing(s) expired by date, "
        f"{result.listings_expired_by_inactivity} by inactivity, "
        f"{result.notices_sent} expiry notice(s) sent."
    )
    return result


def _moment(value: str) -> datetime:
    moment = datetime.fromisoformat(value)
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m adify_api.jobs",
        description="Run Adify's scheduled order and listing jobs once.",
    )
    parser.add_argument(
        "--now",
        type=_moment,
        help="pretend the job runs at this ISO date or time, e.g. 2026-11-14T23:59+02:00",
    )
    parser.add_argument(
        "--job",
        choices=("all", "orders", "listings", "date", "inactivity"),
        default="all",
        help=(
            "all (default), order timeouts, both listing rules, owner-selected dates "
            "only, or inactivity plus notices only"
        ),
    )
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = parser.parse_args()
    asyncio.run(run(args.now, args.job))


if __name__ == "__main__":
    main()
