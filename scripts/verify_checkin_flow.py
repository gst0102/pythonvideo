"""Verify Stage 2 check-in flow.

Checks:
1. normal user check-in grants configured base points
2. same-day duplicate check-in is idempotent
3. member check-in uses member points
4. checkin_records, daily_task_stats and points_ledger stay consistent

By default it only prints the plan. Pass --execute to run against the current
database inside a rollback transaction.
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

from models.base import async_session_factory  # noqa: E402
from models.checkin_record import CheckinRecord  # noqa: E402
from models.daily_task_stat import DailyTaskStat  # noqa: E402
from models.points_ledger import PointsLedger  # noqa: E402
from models.user import User  # noqa: E402
from services.checkin_service import CheckinService  # noqa: E402
from services.config_service import ConfigService  # noqa: E402
from services.points_account_service import PointsAccountService  # noqa: E402

REQUIRED_TABLES = {"users", "user_accounts", "points_ledger", "checkin_records", "daily_task_stats", "system_configs"}


def _assert_equal(label: str, actual, expected) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


async def verify() -> None:
    marker = f"stage2-checkin-{uuid.uuid4().hex[:10]}"
    today = datetime.utcnow().date()

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
                },
            )

            normal_user = User(openid=f"{marker}-normal", nickname="Checkin Normal", avatar="", invite_code=marker[-10:])
            member_user = User(
                openid=f"{marker}-member",
                nickname="Checkin Member",
                avatar="",
                invite_code=f"{marker}m"[-10:],
                is_vip=True,
            )
            session.add(normal_user)
            session.add(member_user)
            await session.flush()

            normal_status_before = await CheckinService.get_status(session, normal_user)
            _assert_equal("normal status before checked_in", bool(normal_status_before["checked_in"]), False)
            _assert_equal("normal status before total_points", int(normal_status_before["total_points"]), 1)

            payload, created = await CheckinService.execute_checkin(session, normal_user)
            _assert_equal("normal checkin created", created, True)
            _assert_equal("normal checkin total_points", int(payload["total_points"]), 1)

            duplicate_payload, duplicate_created = await CheckinService.execute_checkin(session, normal_user)
            _assert_equal("normal duplicate created", duplicate_created, False)
            _assert_equal("normal duplicate total_points", int(duplicate_payload["total_points"]), 1)

            normal_account, _ = await PointsAccountService.ensure_user_account(session, normal_user.id)
            _assert_equal("normal withdrawable points", int(normal_account.withdrawable_points), 1)
            _assert_equal("normal total points", int(normal_account.total_points), 1)

            normal_record_result = await session.execute(
                select(CheckinRecord).where(
                    CheckinRecord.user_id == normal_user.id,
                    CheckinRecord.checkin_date == today,
                )
            )
            normal_records = list(normal_record_result.scalars().all())
            _assert_equal("normal record count", len(normal_records), 1)
            _assert_equal("normal record ad bonus used", bool(normal_records[0].ad_bonus_used), False)

            normal_ledger_result = await session.execute(
                select(PointsLedger).where(
                    PointsLedger.user_id == normal_user.id,
                    PointsLedger.source == "checkin",
                )
            )
            normal_ledgers = list(normal_ledger_result.scalars().all())
            _assert_equal("normal checkin ledger count", len(normal_ledgers), 1)
            _assert_equal("normal checkin idempotency", normal_ledgers[0].idempotency_key, f"checkin:{normal_user.id}:{today.isoformat()}")

            normal_stat_result = await session.execute(
                select(DailyTaskStat).where(DailyTaskStat.user_id == normal_user.id, DailyTaskStat.stat_date == today)
            )
            normal_stat = normal_stat_result.scalar_one_or_none()
            if not normal_stat:
                raise AssertionError("normal daily task stat was not created")
            _assert_equal("normal stat checkin_done", bool(normal_stat.checkin_done), True)
            _assert_equal("normal stat today_points", int(normal_stat.today_points), 1)

            member_payload, member_created = await CheckinService.execute_checkin(session, member_user)
            _assert_equal("member checkin created", member_created, True)
            _assert_equal("member checkin total_points", int(member_payload["total_points"]), 2)

            member_status_after = await CheckinService.get_status(session, member_user)
            _assert_equal("member status checked_in", bool(member_status_after["checked_in"]), True)
            _assert_equal("member status member_bonus_enabled", bool(member_status_after["member_bonus_enabled"]), True)

            member_account, _ = await PointsAccountService.ensure_user_account(session, member_user.id)
            _assert_equal("member withdrawable points", int(member_account.withdrawable_points), 2)

            print("Checkin verification passed")
            print("checks=normal success, duplicate block, member bonus, ledger/stat consistency")
        finally:
            await session.rollback()


async def _assert_required_tables(session) -> None:
    connection = await session.connection()
    table_names = await connection.run_sync(lambda sync_conn: set(inspect(sync_conn).get_table_names()))
    missing = sorted(REQUIRED_TABLES - table_names)
    if missing:
        raise RuntimeError(
            "Missing required tables for checkin verification: "
            + ", ".join(missing)
            + ". Run the Stage 2 Alembic migrations against the intended database first."
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify Stage 2 check-in flow.")
    parser.add_argument("--execute", action="store_true", help="run verification against the configured database")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.execute:
        print("Dry run only. Re-run with --execute to verify against the configured database.")
        print("Checks: normal success, duplicate block, member bonus, ledger/stat consistency.")
        return

    try:
        asyncio.run(verify())
    except RuntimeError as exc:
        print(f"Verification blocked: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
