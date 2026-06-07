"""Verify Stage 2 daily game settlement workflow.

By default this script only prints the verification plan. Pass --execute to run
against the configured database inside a rollback transaction.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import inspect, select

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from models.ad_event import AdEventRecord  # noqa: E402
from models.base import async_session_factory  # noqa: E402
from models.game_round import GameRound  # noqa: E402
from models.game_user_settlement import GameUserSettlement  # noqa: E402
from models.order import Order  # noqa: E402
from models.points_ledger import PointsLedger  # noqa: E402
from models.user import User  # noqa: E402
from services.config_service import ConfigService  # noqa: E402
from services.game_settlement_service import GameSettlementService  # noqa: E402
from services.points_account_service import PointsAccountService  # noqa: E402
from services.points_summary_service import PointsSummaryService  # noqa: E402

REQUIRED_TABLES = {
    "users",
    "orders",
    "ad_event_records",
    "user_accounts",
    "points_ledger",
    "game_rounds",
    "game_settlement_batches",
    "game_user_settlements",
    "system_configs",
}


def _assert_equal(label: str, actual, expected) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def _assert_true(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)


async def verify() -> None:
    marker = f"stage2-settlement-{uuid.uuid4().hex[:10]}"
    settlement_day = (datetime.now(timezone.utc) - timedelta(days=1)).date()
    summary_day = settlement_day + timedelta(days=1)

    async with async_session_factory() as session:
        try:
            await _assert_required_tables(session)
            await ConfigService.set(
                session,
                "stage2_game_settlement_config",
                {
                    "rolling_average_days": 7,
                    "default_ecpm": 30.0,
                    "normal_factor": 0.2,
                    "month_factor": 0.4,
                    "quarter_factor": 0.6,
                    "year_factor": 0.8,
                },
            )

            normal_user = User(
                openid=f"{marker}-normal",
                nickname="Settlement Normal",
                avatar="",
                invite_code=f"{marker}n"[-10:],
            )
            vip_user = User(
                openid=f"{marker}-vip",
                nickname="Settlement VIP",
                avatar="",
                invite_code=f"{marker}v"[-10:],
                is_vip=True,
                vip_expire_at=datetime.now(timezone.utc) + timedelta(days=30),
            )
            session.add(normal_user)
            session.add(vip_user)
            await session.flush()

            vip_order = Order(
                user_id=vip_user.id,
                amount=19.9,
                period="month",
                duration_days=30,
                description="Stage2 settlement verify month vip",
                out_trade_no=f"{marker}-vip-order",
                status="paid",
                paid_at=datetime.now(timezone.utc),
            )
            session.add(vip_order)
            await session.flush()

            await _seed_user_estimated_points(
                session,
                user=normal_user,
                settlement_day=settlement_day,
                round_points=[2, 2, 2, 2, 2],
                ad_pv=10,
                marker=f"{marker}-normal",
            )
            await _seed_user_estimated_points(
                session,
                user=vip_user,
                settlement_day=settlement_day,
                round_points=[2, 2],
                ad_pv=10,
                marker=f"{marker}-vip",
            )

            await GameSettlementService.save_daily_input(
                session,
                settlement_day=settlement_day,
                ecpm_value=30.0,
                ad_pv=20,
                valid_clicks=20,
                total_revenue=0.6,
                note="initial settlement verify",
            )
            first_result = await GameSettlementService.trigger_daily_settlement(
                session,
                settlement_day=settlement_day,
                allow_fallback=False,
            )

            normal_account, _ = await PointsAccountService.ensure_user_account(session, normal_user.id)
            vip_account, _ = await PointsAccountService.ensure_user_account(session, vip_user.id)

            _assert_equal("first normal settled points", int(normal_account.withdrawable_points), 6)
            _assert_equal("first normal consumable points", int(normal_account.consumable_points), 0)
            _assert_equal("first normal total points", int(normal_account.total_points), 6)
            _assert_equal("first vip settled points", int(vip_account.withdrawable_points), 12)
            _assert_equal("first vip consumable points", int(vip_account.consumable_points), 0)
            _assert_equal("first vip total points", int(vip_account.total_points), 12)
            _assert_equal("first batch status", first_result["batch"]["status"], "adjusted")

            first_adjust_rows = await session.execute(
                select(PointsLedger).where(
                    PointsLedger.user_id == normal_user.id,
                    PointsLedger.change_type == "game_adjust_sub",
                )
            )
            _assert_true("normal user first negative adjustment exists", first_adjust_rows.scalars().first() is not None)

            first_add_rows = await session.execute(
                select(PointsLedger).where(
                    PointsLedger.user_id == vip_user.id,
                    PointsLedger.change_type == "game_adjust_add",
                )
            )
            _assert_true("vip user first positive adjustment exists", first_add_rows.scalars().first() is not None)

            await GameSettlementService.save_daily_input(
                session,
                settlement_day=settlement_day,
                ecpm_value=20.0,
                ad_pv=20,
                valid_clicks=20,
                total_revenue=0.4,
                note="rerun settlement verify",
            )
            second_result = await GameSettlementService.trigger_daily_settlement(
                session,
                settlement_day=settlement_day,
                allow_fallback=False,
                force_recalculate=True,
            )

            normal_account, _ = await PointsAccountService.ensure_user_account(session, normal_user.id)
            vip_account, _ = await PointsAccountService.ensure_user_account(session, vip_user.id)

            _assert_equal("rerun normal settled points", int(normal_account.withdrawable_points), 4)
            _assert_equal("rerun normal total points", int(normal_account.total_points), 4)
            _assert_equal("rerun vip settled points", int(vip_account.withdrawable_points), 8)
            _assert_equal("rerun vip total points", int(vip_account.total_points), 8)
            _assert_equal("rerun batch status", second_result["batch"]["status"], "adjusted")

            normal_summary = await PointsSummaryService.build_summary(session, normal_user.id, today=summary_day)
            vip_summary = await PointsSummaryService.build_summary(session, vip_user.id, today=summary_day)
            _assert_equal("summary normal yesterday settled", int(normal_summary["yesterday_settled_points"]), 4)
            _assert_equal("summary vip yesterday settled", int(vip_summary["yesterday_settled_points"]), 8)

            normal_detail = await _get_user_settlement(session, settlement_day, normal_user.id)
            vip_detail = await _get_user_settlement(session, settlement_day, vip_user.id)
            if not normal_detail or not vip_detail:
                raise AssertionError("user settlement rows were not created")

            _assert_equal("normal detail estimated", int(normal_detail.estimated_points), 10)
            _assert_equal("normal detail settled", int(normal_detail.settled_points), 4)
            _assert_equal("vip detail estimated", int(vip_detail.estimated_points), 4)
            _assert_equal("vip detail settled", int(vip_detail.settled_points), 8)

            print("Game settlement verification passed")
            print("checks=first settlement, rerun adjustment, summary settled points, add/sub ledger entries")
        finally:
            await session.rollback()


async def _seed_user_estimated_points(
    session,
    *,
    user: User,
    settlement_day,
    round_points: list[int],
    ad_pv: int,
    marker: str,
) -> None:
    for index, points in enumerate(round_points, start=1):
        round_id = f"{marker}-round-{index}"
        ledger, _, _ = await PointsAccountService.add_points(
            session=session,
            user_id=user.id,
            points=points,
            source="game",
            change_type="game_estimated",
            availability="consumable",
            idempotency_key=f"{marker}:estimated:{index}",
            related_type="game_round",
            related_id=round_id,
            remark="seed estimated game points",
        )
        session.add(
            GameRound(
                user_id=user.id,
                round_id=round_id,
                game_code="rps",
                result="win",
                base_points=points,
                bonus_points=0,
                total_points=points,
                ad_event_id=f"{marker}-event-{index}",
                status="estimated_rewarded",
                ledger_id=ledger.id,
                played_date=settlement_day,
                created_at=datetime.now(timezone.utc) - timedelta(days=1),
                updated_at=datetime.now(timezone.utc) - timedelta(days=1),
            )
        )

    date_key = settlement_day.isoformat()
    for index in range(1, ad_pv + 1):
        event_id = f"{marker}-pv-{index}"
        session.add(
            AdEventRecord(
                event_id=event_id,
                user_id=user.id,
                openid=user.openid,
                module="game",
                section="bonus",
                scene="game_bonus",
                ad_unit_id="adunit-stage2-settlement",
                event_type="show",
                is_completed=False,
                reward_points=0,
                reward_amount=0,
                date_key=date_key,
                week_key=f"{settlement_day.isocalendar().year}-W{settlement_day.isocalendar().week:02d}",
                month_key=settlement_day.strftime("%Y-%m"),
                created_at=datetime.now(timezone.utc) - timedelta(days=1),
            )
        )
        session.add(
            AdEventRecord(
                event_id=event_id,
                user_id=user.id,
                openid=user.openid,
                module="game",
                section="bonus",
                scene="game_bonus",
                ad_unit_id="adunit-stage2-settlement",
                event_type="complete",
                is_completed=True,
                reward_points=0,
                reward_amount=0,
                date_key=date_key,
                week_key=f"{settlement_day.isocalendar().year}-W{settlement_day.isocalendar().week:02d}",
                month_key=settlement_day.strftime("%Y-%m"),
                created_at=datetime.now(timezone.utc) - timedelta(days=1),
            )
        )
    await session.flush()


async def _get_user_settlement(session, settlement_day, user_id):
    result = await session.execute(
        select(GameUserSettlement).where(
            GameUserSettlement.settlement_date == settlement_day,
            GameUserSettlement.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def _assert_required_tables(session) -> None:
    connection = await session.connection()
    table_names = await connection.run_sync(lambda sync_conn: set(inspect(sync_conn).get_table_names()))
    missing = sorted(REQUIRED_TABLES - table_names)
    if missing:
        raise RuntimeError(
            "Missing required tables for Stage 2 game settlement verification: "
            + ", ".join(missing)
            + ". Run the Stage 2 Alembic migrations against the intended database first."
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify Stage 2 game settlement workflow.")
    parser.add_argument("--execute", action="store_true", help="run verification against the configured database")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.execute:
        print("Dry run only. Re-run with --execute to verify against the configured database.")
        print("Checks: first settlement, rerun adjustment, add/sub ledger entries, yesterday settled summary.")
        return

    try:
        asyncio.run(verify())
    except RuntimeError as exc:
        print(f"Verification blocked: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
