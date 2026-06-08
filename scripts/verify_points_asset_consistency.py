"""Verify points account, ledger, and mine assets consistency.

By default this script only prints the plan. Pass --execute to run against the
configured database inside a rollback transaction.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import inspect
from sqlmodel import select

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from models.base import async_session_factory  # noqa: E402
from models.game_settlement_batch import GameSettlementBatch  # noqa: E402
from models.game_user_settlement import GameUserSettlement  # noqa: E402
from models.order import Order  # noqa: E402
from models.points_ledger import PointsLedger  # noqa: E402
from models.user import User  # noqa: E402
from models.withdrawal import WithdrawalRecord  # noqa: E402
from services.checkin_service import CheckinService  # noqa: E402
from services.config_service import ConfigService  # noqa: E402
from services.game_task_service import GameTaskService  # noqa: E402
from services.game_settlement_service import GameSettlementService  # noqa: E402
from services.home_overview_service import HomeOverviewService  # noqa: E402
from services.mine_assets_service import MineAssetsService  # noqa: E402
from services.payment_service import PaymentService  # noqa: E402
from services.points_account_service import PointsAccountService  # noqa: E402
from services.points_ledger_service import PointsLedgerService  # noqa: E402
from services.withdrawal_service import WithdrawalService  # noqa: E402

REQUIRED_TABLES = {
    "users",
    "orders",
    "commission_records",
    "user_accounts",
    "points_ledger",
    "daily_task_stats",
    "checkin_records",
    "game_rounds",
    "game_settlement_batches",
    "game_user_settlements",
    "withdraw_records",
    "system_configs",
}


def _assert_equal(label: str, actual, expected) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


async def _fake_submit_processing_withdrawal(session, record_id, openid=None, allow_existing_submission=False):
    record = await session.get(WithdrawalRecord, record_id)
    return record, None


async def verify() -> None:
    marker = f"stage2-assets-{uuid.uuid4().hex[:10]}"

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
                    "game_base_points_min": 1,
                    "game_base_points_max": 2,
                },
            )
            await ConfigService.set(
                session,
                "withdrawal_config",
                {
                    "enabled": True,
                    "min_amount": 0.10,
                    "withdraw_min_first": 1.00,
                    "withdraw_min_normal": 5.00,
                    "withdraw_min_member": 1.00,
                    "max_amount": 200.00,
                    "daily_limit": 100.00,
                    "tips": "test withdrawal config",
                },
            )
            await ConfigService.set(session, "commission_settings", {"level1_rate": 50.0, "level2_rate": 5.0})

            user = User(openid=f"{marker}-user", nickname="Asset User", avatar="", invite_code=f"{marker}u"[-10:])
            buyer = User(
                openid=f"{marker}-buyer",
                nickname="Asset Buyer",
                avatar="",
                invite_code=f"{marker}b"[-10:],
                parent_id=user.id,
            )
            session.add(user)
            session.add(buyer)
            await session.flush()

            await CheckinService.execute_checkin(session, user)
            round_payload, _ = await GameTaskService.complete_round(
                session,
                user,
                game_code="rps",
                round_id=f"{marker}-round-1",
                result="win",
            )
            _assert_equal("game round no immediate reward", int(round_payload["points_added"]), 0)
            _assert_equal("game round ad required", bool(round_payload["ad_required"]), True)
            await PointsAccountService.add_points(
                session=session,
                user_id=user.id,
                points=500,
                source="admin_adjust",
                change_type="adjust_add",
                availability="withdrawable",
                idempotency_key=f"{marker}:seed-withdrawable",
                related_type="verification",
                related_id=marker,
                remark="seed points for withdrawal verification",
            )

            order = Order(
                user_id=buyer.id,
                amount=10.0,
                period="month",
                duration_days=30,
                description="Stage2 asset consistency rebate",
                out_trade_no=f"{marker}-order",
                status="pending",
            )
            session.add(order)
            await session.flush()
            await PaymentService.handle_payment_success(
                session=session,
                out_trade_no=order.out_trade_no,
                transaction_id=f"{marker}-tx",
                total_fee_in_fen=1000,
                paid_at=datetime.now(timezone.utc).isoformat(),
            )

            settlement_day = datetime.now(timezone.utc).date() - timedelta(days=1)
            settlement_batch = GameSettlementBatch(
                settlement_date=settlement_day,
                status="settled",
                ecpm_value=30.0,
                ecpm_source="manual",
                ad_pv=10,
                valid_clicks=10,
                total_revenue=0.3,
                settled_user_count=1,
                total_estimated_points=100,
                total_settled_points=120,
                total_adjustment_points=20,
                note="asset consistency settlement sample",
                settled_at=datetime.now(timezone.utc),
            )
            session.add(settlement_batch)
            await session.flush()
            session.add(
                GameUserSettlement(
                    batch_id=settlement_batch.id,
                    settlement_date=settlement_day,
                    user_id=user.id,
                    membership_level="normal",
                    factor_value=0.2,
                    estimated_points=100,
                    settled_points=120,
                    adjustment_points=20,
                    round_count=5,
                    ad_pv=10,
                    valid_clicks=10,
                    status="adjusted",
                )
            )
            await session.flush()

            with patch("services.withdrawal_service._get_transfer_notify_url", return_value="https://example.com/notify"), patch.object(
                WithdrawalService,
                "submit_processing_withdrawal",
                side_effect=_fake_submit_processing_withdrawal,
            ):
                withdraw_record, _, withdraw_error = await WithdrawalService.apply_points_withdrawal(
                    session,
                    user.id,
                    100,
                    openid=user.openid,
                )
            _assert_equal("withdraw apply error", withdraw_error, None)
            if not withdraw_record:
                raise AssertionError("withdraw record was not created")
            await WithdrawalService.handle_transfer_failed(session, withdraw_record.batch_no, "verification_return")

            account, _ = await PointsAccountService.ensure_user_account(session, user.id)
            home = await HomeOverviewService.get_overview(session, user)
            assets = await MineAssetsService.get_assets(session, user)
            ledger_page = await PointsLedgerService.list_user_ledger(session, user, page=1, page_size=50)
            settlement_detail = await GameSettlementService.get_daily_detail(session, settlement_day)

            wallet = assets["points_wallet"]
            _assert_equal(
                "home yesterday settled points",
                int(home["welfare_card"]["yesterday_settled_points"]),
                120,
            )
            _assert_equal("mine yesterday settled points", int(wallet["yesterday_settled_points"]), 120)
            _assert_equal(
                "admin settlement user settled points",
                int(settlement_detail["settlements"][0]["settled_points"]),
                120,
            )
            _assert_equal(
                "admin settlement total settled points",
                int(settlement_detail["batch"]["total_settled_points"]),
                120,
            )
            _assert_equal("wallet total_points", int(wallet["total_points"]), int(account.total_points))
            _assert_equal("wallet withdrawable_points", int(wallet["withdrawable_points"]), int(account.withdrawable_points))
            _assert_equal("wallet frozen_points", int(wallet["frozen_points"]), int(account.frozen_points))
            _assert_equal("wallet locked_withdraw_points", int(wallet["locked_withdraw_points"]), int(account.locked_withdraw_points))
            _assert_equal("wallet withdrawn_points", int(wallet["withdrawn_points"]), int(account.withdrawn_points))
            _assert_equal("ledger account withdrawable", int(ledger_page["account"]["withdrawable_points"]), int(account.withdrawable_points))
            _assert_equal("ledger account frozen", int(ledger_page["account"]["frozen_points"]), int(account.frozen_points))

            source_result = await session.execute(select(PointsLedger.source).where(PointsLedger.user_id == user.id))
            sources = {row[0] for row in source_result.all()}
            for source in {"checkin", "invite", "withdraw"}:
                if source not in sources:
                    raise AssertionError(f"missing expected ledger source: {source}")

            latest_ledger_result = await session.execute(
                select(PointsLedger)
                .where(PointsLedger.user_id == user.id)
                .order_by(PointsLedger.created_at.desc(), PointsLedger.id.desc())
            )
            latest_ledger = latest_ledger_result.scalars().first()
            if not latest_ledger:
                raise AssertionError("latest ledger was not found")
            _assert_equal("latest ledger withdrawable balance", int(latest_ledger.balance_withdrawable_after), int(account.withdrawable_points))
            _assert_equal("latest ledger frozen balance", int(latest_ledger.balance_frozen_after), int(account.frozen_points))
            _assert_equal("latest ledger consumable balance", int(latest_ledger.balance_consumable_after), int(account.consumable_points))

            print("Points asset consistency verification passed")
            print(
                "checks=checkin, game, invite frozen rebate, withdrawal lock/return, "
                "home summary, mine assets, ledger account, admin settlement"
            )
        finally:
            await session.rollback()


async def _assert_required_tables(session) -> None:
    connection = await session.connection()
    table_names = await connection.run_sync(lambda sync_conn: set(inspect(sync_conn).get_table_names()))
    missing = sorted(REQUIRED_TABLES - table_names)
    if missing:
        raise RuntimeError(
            "Missing required tables for asset consistency verification: "
            + ", ".join(missing)
            + ". Run the Stage 2 Alembic migrations against the intended database first."
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify Stage 2 points asset consistency.")
    parser.add_argument("--execute", action="store_true", help="run verification against the configured database")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.execute:
        print("Dry run only. Re-run with --execute to verify against the configured database.")
        print(
            "Checks: checkin, game, invite frozen rebate, withdrawal lock/return, "
            "home summary, mine assets, ledger account, admin settlement."
        )
        return

    try:
        asyncio.run(verify())
    except RuntimeError as exc:
        print(f"Verification blocked: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
