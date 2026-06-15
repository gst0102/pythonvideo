"""Verify daily earn summary excludes returned principal from the 0/60 progress."""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

from sqlmodel import select

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.timezone import today_bj  # noqa: E402
from models.base import async_session_factory  # noqa: E402
from models.user import User  # noqa: E402
from services.points_account_service import PointsAccountService  # noqa: E402
from services.points_summary_service import PointsSummaryService  # noqa: E402


def _assert_equal(label: str, actual, expected) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


async def verify() -> None:
    marker = f"daily-earn-{uuid.uuid4().hex[:10]}"
    today = today_bj()

    async with async_session_factory() as session:
        try:
            user = User(openid=marker, nickname="Daily Earn Probe", avatar="", invite_code=marker[-10:])
            session.add(user)
            await session.flush()

            await PointsAccountService.add_points(
                session,
                user.id,
                points=1,
                source="checkin",
                change_type="earn",
                availability="consumable",
                idempotency_key=f"{marker}:checkin",
                related_type="checkin",
                related_id=today.isoformat(),
            )
            await PointsAccountService.add_points(
                session,
                user.id,
                points=4,
                source="game",
                change_type="game_estimated",
                availability="consumable",
                idempotency_key=f"{marker}:game",
                related_type="game_round",
                related_id=marker,
            )
            await PointsAccountService.add_points(
                session,
                user.id,
                points=20,
                source="netdisk_request",
                change_type="request_bounty_return",
                availability="consumable",
                idempotency_key=f"{marker}:bounty-return",
                related_type="netdisk_request",
                related_id=marker,
            )

            summary = await PointsSummaryService.build_summary(session, user.id, today=today)
            _assert_equal("today earned excludes returned bounty", int(summary["today_earned_points"]), 5)
            _assert_equal("today cap", int(summary["today_earn_cap"]), 60)

            print("Daily earn summary verification passed")
            print("checks=checkin/game counted, returned request bounty excluded")
        finally:
            await session.rollback()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify daily earn summary.")
    parser.add_argument("--execute", action="store_true", help="run verification against the configured database")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.execute:
        print("Dry run only. Re-run with --execute to verify against the configured database.")
        print("Checks: checkin/game counted, returned request bounty excluded.")
        return

    asyncio.run(verify())


if __name__ == "__main__":
    main()
