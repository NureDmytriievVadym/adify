"""Scheduled jobs, run once per invocation by cron: ``python -m adify_api.jobs``.

FR-132: cancel paid orders whose provider did not start work in time and release their
Mono holds. Run it at least daily; ``--now`` replays a later date for demos and checks.
"""

import argparse
import asyncio
import logging
from datetime import UTC, datetime

from adify_api.core.db import get_sessionmaker
from adify_api.orders.workflow import cancel_unstarted_orders
from adify_api.payments.mono import get_mono


async def run(now: datetime | None = None) -> int:
    mono = get_mono()
    if mono is None:
        raise SystemExit("Mono is not configured (ADIFY_MONO_TOKEN), so holds cannot be released.")
    async with get_sessionmaker()() as session:
        canceled = await cancel_unstarted_orders(session, mono, now)
    for order in canceled:
        print(f"Canceled order {order.id}: work did not start in time; the hold was released.")
    print(f"Start timeout: {len(canceled)} order(s) canceled.")
    return len(canceled)


def _moment(value: str) -> datetime:
    moment = datetime.fromisoformat(value)
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m adify_api.jobs", description="Run Adify's order timeout jobs once."
    )
    parser.add_argument(
        "--now",
        type=_moment,
        help="pretend the job runs at this ISO date or time, e.g. 2026-11-21 (UTC if no zone)",
    )
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    asyncio.run(run(parser.parse_args().now))


if __name__ == "__main__":
    main()
