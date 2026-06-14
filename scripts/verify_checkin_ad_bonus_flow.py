"""Verify Stage 2 check-in rewarded-ad bonus flow.

By default this script only prints the plan. Pass --execute to run against the
configured database inside a rollback transaction.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import inspect
from sqlmodel import select

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from models.ad_event import AdEventRecord  # noqa: E402
from models.base import async_session_factory  # noqa: E402
from models.checkin_record import CheckinRecord  # noqa: E402
from models.daily_task_stat import DailyTaskStat  # noqa: E402
from models.points_ledger import PointsLedger  # noqa: E402
from models.user import User  # noqa: E402
from core.timezone import today_bj  # noqa: E402
from services.checkin_service import CheckinService  # noqa: E402
from services.config_service import ConfigService  # noqa: E402
from services.points_account_service import PointsAccountService  # noqa: E402

REQUIRED_TABLES = {
    "users",
    "user_accounts",
    "points_ledger",
    "checkin_records",
    "daily_task_stats",
    "ad_event_records",
    "system_configs",
}


def _assert_equal(label: str, actual, expected) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


async def verify() -> None:
    marker = f"stage2-checkin-ad-{uuid.uuid4().hex[:10]}"
    today = today_bj()

    async with async_session_factory() as session:
        try:
            await _assert_required_tables(session)
            await ConfigService.set(
                session,
                "stage2_points_config",
                {
                    "exchange_rate": 100,
                    "checkin_base_points_normal": 1,
                    "checkin_base_points_member": 2,
                    "checkin_ad_bonus_points": 3,
                },
            )

            user = User(openid=f"{marker}-user", nickname="Checkin Ad Verify", avatar="", invite_code=marker[-10:])
            session.add(user)
            await session.flush()

            base_payload, base_created = await CheckinService.execute_checkin(session, user)
            _assert_equal("base checkin created", base_created, True)
            _assert_equal("base total points", int(base_payload["total_points"]), 1)

            event_id = f"{marker}:checkin:complete"
            session.add(
                AdEventRecord(
                    event_id=event_id,
                    user_id=user.id,
                    openid=user.openid,
                    module="checkin",
                    section="daily_bonus",
                    scene="checkin_bonus",
                    ad_unit_id="adunit-checkin-bonus-test",
                    event_type="complete",
                    is_completed=True,
                    date_key=today.isoformat(),
                    week_key="verify",
                    month_key=today.strftime("%Y-%m"),
                )
            )
            await session.flush()

            bonus_payload, bonus_created, bonus_error = await CheckinService.claim_ad_bonus(session, user, event_id)
            _assert_equal("first bonus error", bonus_error, None)
            _assert_equal("first bonus created", bonus_created, True)
            _assert_equal("first bonus total points", int(bonus_payload["total_points"]), 4)

            replay_payload, replay_created, replay_error = await CheckinService.claim_ad_bonus(session, user, event_id)
            _assert_equal("same ad_event replay error", replay_error, None)
            _assert_equal("same ad_event replay created", replay_created, False)
            _assert_equal("same ad_event replay total points", int(replay_payload["total_points"]), 4)

            second_event_id = f"{marker}:checkin:complete-2"
            session.add(
                AdEventRecord(
                    event_id=second_event_id,
                    user_id=user.id,
                    openid=user.openid,
                    module="checkin",
                    section="daily_bonus",
                    scene="checkin_bonus",
                    ad_unit_id="adunit-checkin-bonus-test-2",
                    event_type="complete",
                    is_completed=True,
                    date_key=today.isoformat(),
                    week_key="verify",
                    month_key=today.strftime("%Y-%m"),
                )
            )
            await session.flush()

            second_payload, second_created, second_error = await CheckinService.claim_ad_bonus(session, user, second_event_id)
            _assert_equal("same-day second event error", second_error, None)
            _assert_equal("same-day second event created", second_created, False)
            _assert_equal("same-day second event total points", int(second_payload["total_points"]), 4)

            account, _ = await PointsAccountService.ensure_user_account(session, user.id)
            _assert_equal("account withdrawable points", int(account.withdrawable_points), 4)
            _assert_equal("account total points", int(account.total_points), 4)

            record_result = await session.execute(
                select(CheckinRecord).where(CheckinRecord.user_id == user.id, CheckinRecord.checkin_date == today)
            )
            record = record_result.scalar_one()
            _assert_equal("record ad bonus used", bool(record.ad_bonus_used), True)
            _assert_equal("record bonus points", int(record.bonus_points), 3)
            _assert_equal("record total points", int(record.total_points), 4)
            _assert_equal("record ad event id", record.ad_event_id, event_id)

            ledger_result = await session.execute(
                select(PointsLedger).where(PointsLedger.user_id == user.id, PointsLedger.source == "checkin")
            )
            ledgers = list(ledger_result.scalars().all())
            _assert_equal("checkin ledger count", len(ledgers), 2)
            _assert_equal("checkin ad bonus ledger count", len([row for row in ledgers if row.change_type == "ad_bonus"]), 1)

            stat_result = await session.execute(
                select(DailyTaskStat).where(DailyTaskStat.user_id == user.id, DailyTaskStat.stat_date == today)
            )
            stat = stat_result.scalar_one()
            _assert_equal("daily stat today points", int(stat.today_points), 4)

            print("Checkin ad bonus verification passed")
            print("checks=base checkin, first ad bonus, ad_event replay, same-day second bonus block, ledger/account/stat")
        finally:
            await session.rollback()


async def _assert_required_tables(session) -> None:
    connection = await session.connection()
    table_names = await connection.run_sync(lambda sync_conn: set(inspect(sync_conn).get_table_names()))
    missing = sorted(REQUIRED_TABLES - table_names)
    if missing:
        raise RuntimeError(
            "Missing required tables for checkin-ad verification: "
            + ", ".join(missing)
            + ". Run the Stage 2 Alembic migrations against the intended database first."
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify Stage 2 check-in ad bonus flow.")
    parser.add_argument("--execute", action="store_true", help="run verification against the configured database")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.execute:
        print("Dry run only. Re-run with --execute to verify against the configured database.")
        print("Checks: base checkin, first ad bonus, ad_event replay, same-day second bonus block.")
        return

    try:
        asyncio.run(verify())
    except RuntimeError as exc:
        print(f"Verification blocked: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
