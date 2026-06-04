"""Verify Stage 2 VIP payment entitlements.

This script exercises the service layer with a simulated payment success:
1. create a temporary user and VIP order
2. call PaymentService.handle_payment_success
3. assert VIP status, vip_gift ledger, game task limit, and withdrawal summary

By default it only prints the plan. Pass --execute to run inside a transaction
that is rolled back before exit.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import inspect
from sqlmodel import select

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from models.base import async_session_factory  # noqa: E402
from models.daily_task_stat import DailyTaskStat  # noqa: E402
from models.order import Order  # noqa: E402
from models.points_ledger import PointsLedger  # noqa: E402
from models.user import User  # noqa: E402
from services.game_task_service import GameTaskService  # noqa: E402
from services.payment_service import PaymentService  # noqa: E402
from services.points_account_service import PointsAccountService  # noqa: E402
from services.points_ledger_service import PointsLedgerService  # noqa: E402
from services.withdrawal_service import WithdrawalService  # noqa: E402


PERIOD_EXPECTATIONS = {
    "month": {"gift_points": 199, "game_limit": 100, "duration_days": 30, "amount": 9.90},
    "quarter": {"gift_points": 599, "game_limit": 150, "duration_days": 90, "amount": 26.90},
    "year": {"gift_points": 1299, "game_limit": 200, "duration_days": 365, "amount": 88.80},
}
REQUIRED_TABLES = {
    "daily_task_stats",
    "orders",
    "points_ledger",
    "user_accounts",
    "users",
    "withdraw_records",
}


def _assert_equal(label: str, actual, expected) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


async def verify(period: str) -> None:
    expected = PERIOD_EXPECTATIONS[period]
    marker = f"stage2-vip-e2e-{uuid.uuid4().hex[:12]}"
    out_trade_no = f"{marker}-order"

    async with async_session_factory() as session:
        try:
            await _assert_required_tables(session)

            user = User(
                openid=marker,
                nickname="Stage2 VIP E2E",
                avatar="",
                invite_code=marker[-10:],
            )
            session.add(user)
            await session.flush()

            order = Order(
                user_id=user.id,
                amount=expected["amount"],
                period=period,
                duration_days=expected["duration_days"],
                description=f"Stage2 {period} VIP entitlement verification",
                out_trade_no=out_trade_no,
                status="pending",
            )
            session.add(order)
            await session.flush()

            ok = await PaymentService.handle_payment_success(
                session=session,
                out_trade_no=out_trade_no,
                transaction_id=f"{marker}-tx",
                total_fee_in_fen=int(round(expected["amount"] * 100)),
                paid_at=datetime.now(UTC).isoformat(),
            )
            _assert_equal("payment success result", ok, True)

            refreshed_user = await session.get(User, user.id)
            if not refreshed_user:
                raise AssertionError("test user was not found after payment")
            _assert_equal("user.is_vip", refreshed_user.is_vip, True)
            if not refreshed_user.vip_expire_at:
                raise AssertionError("vip_expire_at was not set")

            account, _ = await PointsAccountService.ensure_user_account(session, user.id)
            _assert_equal("account.withdrawable_points", int(account.withdrawable_points), expected["gift_points"])
            _assert_equal("account.total_points", int(account.total_points), expected["gift_points"])

            ledger_result = await session.execute(
                select(PointsLedger).where(
                    PointsLedger.user_id == user.id,
                    PointsLedger.change_type == "vip_gift",
                    PointsLedger.source == "vip",
                    PointsLedger.related_type == "order",
                    PointsLedger.related_id == str(order.id),
                )
            )
            ledger = ledger_result.scalar_one_or_none()
            if not ledger:
                raise AssertionError("vip_gift ledger was not created")
            _assert_equal("ledger.points_delta", int(ledger.points_delta), expected["gift_points"])
            _assert_equal("ledger.idempotency_key", ledger.idempotency_key, f"vip_gift:{order.id}")

            ledger_page = await PointsLedgerService.list_user_ledger(
                session=session,
                user=refreshed_user,
                page=1,
                page_size=10,
                source="vip",
            )
            _assert_equal("points ledger total for vip source", int(ledger_page["total"]), 1)
            _assert_equal("points ledger item change_type", ledger_page["items"][0]["change_type"], "vip_gift")

            game_status = await GameTaskService.get_status(session, refreshed_user)
            _assert_equal("game today_limit", int(game_status["today_limit"]), expected["game_limit"])
            _assert_equal("game member_bonus_enabled", bool(game_status["member_bonus_enabled"]), True)

            withdrawal_summary = await WithdrawalService.get_points_withdrawal_summary(session, user.id)
            _assert_equal("withdrawal summary is_member", bool(withdrawal_summary["is_member"]), True)
            _assert_equal("withdrawal min member amount", float(withdrawal_summary["min_withdraw_amount"]), 1.0)
            _assert_equal("withdrawal min member points", int(withdrawal_summary["min_withdraw_points"]), 100)

            stat_result = await session.execute(
                select(DailyTaskStat).where(DailyTaskStat.user_id == user.id)
            )
            daily_stat = stat_result.scalar_one_or_none()
            if not daily_stat:
                raise AssertionError("daily task stat was not initialized")
            _assert_equal("daily stat game_tasks_limit", int(daily_stat.game_tasks_limit), expected["game_limit"])

            print("VIP entitlement verification passed")
            print(f"period={period}")
            print(f"gift_points={expected['gift_points']}")
            print(f"game_daily_limit={expected['game_limit']}")
            print("ledger_change_type=vip_gift")
            print("withdraw_min_amount=1.0")
        finally:
            await session.rollback()


async def _assert_required_tables(session) -> None:
    connection = await session.connection()
    table_names = await connection.run_sync(lambda sync_conn: set(inspect(sync_conn).get_table_names()))
    missing = sorted(REQUIRED_TABLES - table_names)
    if missing:
        raise RuntimeError(
            "Missing required tables for Stage 2 VIP entitlement verification: "
            + ", ".join(missing)
            + ". Run the Stage 2 Alembic migrations against the intended database first."
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify Stage 2 VIP payment entitlements.")
    parser.add_argument("--execute", action="store_true", help="run verification against the configured database")
    parser.add_argument(
        "--period",
        choices=sorted(PERIOD_EXPECTATIONS.keys()),
        default="quarter",
        help="VIP package period to verify",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.execute:
        print("Dry run only. Re-run with --execute to verify against the configured database.")
        print("Checks: VIP status, vip_gift ledger, game daily limit, withdrawal member threshold.")
        return

    try:
        asyncio.run(verify(args.period))
    except RuntimeError as exc:
        print(f"Verification blocked: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
