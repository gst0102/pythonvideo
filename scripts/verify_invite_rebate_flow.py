"""Verify Stage 2 invite rebate, frozen points, and unfreeze flow.

By default this script only prints the plan. Pass --execute to run against the
configured database inside a rollback transaction.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import inspect
from sqlmodel import select

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from models.base import async_session_factory  # noqa: E402
from models.commission import CommissionRecord  # noqa: E402
from models.invite_relation import InviteRelation  # noqa: E402
from models.order import Order  # noqa: E402
from models.points_ledger import PointsLedger  # noqa: E402
from models.user import User  # noqa: E402
from services.commission_service import CommissionService  # noqa: E402
from services.config_service import ConfigService  # noqa: E402
from services.payment_service import PaymentService  # noqa: E402
from services.points_account_service import PointsAccountService  # noqa: E402

REQUIRED_TABLES = {
    "users",
    "orders",
    "invite_relations",
    "commission_records",
    "user_accounts",
    "points_ledger",
    "system_configs",
}


def _assert_equal(label: str, actual, expected) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


async def verify() -> None:
    marker = f"stage2-rebate-{uuid.uuid4().hex[:10]}"
    amount = 10.00
    out_trade_no = f"{marker}-order"

    async with async_session_factory() as session:
        try:
            await _assert_required_tables(session)
            await ConfigService.set(session, "stage2_points_config", {"exchange_rate": 100})
            await ConfigService.set(
                session,
                "commission_settings",
                {
                    "level1_rate": 50.0,
                    "level2_rate": 5.0,
                    "settlement_days": 7,
                    "rules": "test invite rebate config",
                },
            )

            grandparent = User(
                openid=f"{marker}-grand",
                nickname="Rebate Grand",
                avatar="",
                invite_code=f"{marker}g"[-10:],
            )
            parent = User(
                openid=f"{marker}-parent",
                nickname="Rebate Parent",
                avatar="",
                invite_code=f"{marker}p"[-10:],
                parent_id=grandparent.id,
            )
            buyer = User(
                openid=f"{marker}-buyer",
                nickname="Rebate Buyer",
                avatar="",
                invite_code=f"{marker}b"[-10:],
                parent_id=parent.id,
                grand_parent_id=grandparent.id,
            )
            session.add(grandparent)
            session.add(parent)
            session.add(buyer)
            await session.flush()
            session.add(
                InviteRelation(
                    inviter_id=parent.id,
                    invitee_id=buyer.id,
                    invite_code=parent.invite_code,
                    source="test",
                )
            )
            await session.flush()

            order = Order(
                user_id=buyer.id,
                amount=amount,
                period="month",
                duration_days=30,
                description="Stage2 invite rebate verification",
                out_trade_no=out_trade_no,
                status="pending",
            )
            session.add(order)
            await session.flush()

            ok = await PaymentService.handle_payment_success(
                session=session,
                out_trade_no=out_trade_no,
                transaction_id=f"{marker}-tx",
                total_fee_in_fen=int(round(amount * 100)),
                paid_at=datetime.now(timezone.utc).isoformat(),
            )
            _assert_equal("payment success", ok, True)

            duplicate_ok = await PaymentService.handle_payment_success(
                session=session,
                out_trade_no=out_trade_no,
                transaction_id=f"{marker}-tx-duplicate",
                total_fee_in_fen=int(round(amount * 100)),
                paid_at=datetime.now(timezone.utc).isoformat(),
            )
            _assert_equal("duplicate payment callback", duplicate_ok, True)

            records_result = await session.execute(
                select(CommissionRecord).where(CommissionRecord.order_id == order.id).order_by(CommissionRecord.level)
            )
            records = list(records_result.scalars().all())
            _assert_equal("commission record count", len(records), 2)

            level1 = records[0]
            level2 = records[1]
            _assert_equal("level1 owner", level1.user_id, parent.id)
            _assert_equal("level1 rate", float(level1.commission_rate), 50.0)
            _assert_equal("level1 amount", float(level1.commission_amount), 5.0)
            _assert_equal("level1 status", level1.status, "pending")
            _assert_equal("level2 owner", level2.user_id, grandparent.id)
            _assert_equal("level2 rate", float(level2.commission_rate), 5.0)
            _assert_equal("level2 amount", float(level2.commission_amount), 0.5)
            _assert_equal("level2 status", level2.status, "pending")

            parent_account, _ = await PointsAccountService.ensure_user_account(session, parent.id)
            grand_account, _ = await PointsAccountService.ensure_user_account(session, grandparent.id)
            _assert_equal("level1 frozen points", int(parent_account.frozen_points), 500)
            _assert_equal("level2 frozen points", int(grand_account.frozen_points), 50)

            ledger_result = await session.execute(
                select(PointsLedger).where(
                    PointsLedger.user_id.in_([parent.id, grandparent.id]),
                    PointsLedger.source == "invite",
                    PointsLedger.change_type == "invite_rebate_frozen",
                    PointsLedger.related_type == "commission_record",
                )
            )
            frozen_ledgers = list(ledger_result.scalars().all())
            _assert_equal("frozen rebate ledger count", len(frozen_ledgers), 2)

            vip_first_recharge_result = await session.execute(
                select(PointsLedger).where(
                    PointsLedger.user_id == parent.id,
                    PointsLedger.change_type == "invite_first_recharge",
                    PointsLedger.related_type == "invite_relation",
                )
            )
            vip_first_recharge_ledgers = list(vip_first_recharge_result.scalars().all())
            _assert_equal("vip order should not grant fixed first recharge reward", len(vip_first_recharge_ledgers), 0)

            released_level1, level1_released = await CommissionService.release_commission_points(session, level1.id)
            _assert_equal("level1 release created", level1_released, True)
            if not released_level1:
                raise AssertionError("level1 release returned no record")
            _assert_equal("level1 release status", released_level1.status, "settled")

            _, level1_replay = await CommissionService.release_commission_points(session, level1.id)
            _assert_equal("level1 release replay", level1_replay, False)

            parent_account_after, _ = await PointsAccountService.ensure_user_account(session, parent.id)
            _assert_equal("level1 withdrawable after release", int(parent_account_after.withdrawable_points), 500)
            _assert_equal("level1 frozen after release", int(parent_account_after.frozen_points), 0)

            unfreeze_result = await session.execute(
                select(PointsLedger).where(
                    PointsLedger.user_id == parent.id,
                    PointsLedger.change_type == "invite_rebate_unfreeze",
                    PointsLedger.related_type == "commission_record",
                    PointsLedger.related_id == str(level1.id),
                )
            )
            unfreeze_ledgers = list(unfreeze_result.scalars().all())
            _assert_equal("level1 unfreeze ledger count", len(unfreeze_ledgers), 1)

            released_level2, level2_released = await CommissionService.release_commission_points(session, level2.id)
            _assert_equal("level2 release created", level2_released, True)
            if not released_level2:
                raise AssertionError("level2 release returned no record")
            _assert_equal("level2 release status", released_level2.status, "settled")

            _, level2_replay = await CommissionService.release_commission_points(session, level2.id)
            _assert_equal("level2 release replay", level2_replay, False)

            grand_account_after, _ = await PointsAccountService.ensure_user_account(session, grandparent.id)
            _assert_equal("level2 withdrawable after release", int(grand_account_after.withdrawable_points), 50)
            _assert_equal("level2 frozen after release", int(grand_account_after.frozen_points), 0)

            level2_unfreeze_result = await session.execute(
                select(PointsLedger).where(
                    PointsLedger.user_id == grandparent.id,
                    PointsLedger.change_type == "invite_rebate_unfreeze",
                    PointsLedger.related_type == "commission_record",
                    PointsLedger.related_id == str(level2.id),
                )
            )
            level2_unfreeze_ledgers = list(level2_unfreeze_result.scalars().all())
            _assert_equal("level2 unfreeze ledger count", len(level2_unfreeze_ledgers), 1)

            records_after_replay_result = await session.execute(
                select(CommissionRecord).where(CommissionRecord.order_id == order.id)
            )
            records_after_replay = list(records_after_replay_result.scalars().all())
            _assert_equal("commission record count after duplicate callback", len(records_after_replay), 2)

            points_buyer = User(
                openid=f"{marker}-points-buyer",
                nickname="Points Buyer",
                avatar="",
                invite_code=f"{marker}pb"[-10:],
                parent_id=parent.id,
                grand_parent_id=grandparent.id,
            )
            session.add(points_buyer)
            await session.flush()
            session.add(
                InviteRelation(
                    inviter_id=parent.id,
                    invitee_id=points_buyer.id,
                    invite_code=parent.invite_code,
                    source="test",
                )
            )
            await session.flush()

            points_order = Order(
                user_id=points_buyer.id,
                amount=1.00,
                period="points_10",
                duration_days=0,
                description="Stage2 invite fixed first recharge verification",
                out_trade_no=f"{marker}-points-order",
                status="pending",
            )
            session.add(points_order)
            await session.flush()
            points_ok = await PaymentService.handle_payment_success(
                session=session,
                out_trade_no=points_order.out_trade_no,
                transaction_id=f"{marker}-points-tx",
                total_fee_in_fen=100,
                paid_at=datetime.now(timezone.utc).isoformat(),
            )
            _assert_equal("points recharge payment success", points_ok, True)

            fixed_reward_result = await session.execute(
                select(PointsLedger).where(
                    PointsLedger.user_id == parent.id,
                    PointsLedger.change_type == "invite_first_recharge",
                    PointsLedger.related_type == "invite_relation",
                )
            )
            fixed_reward_ledgers = list(fixed_reward_result.scalars().all())
            _assert_equal("points recharge grants fixed first recharge reward once", len(fixed_reward_ledgers), 1)
            _assert_equal("fixed first recharge reward points", int(fixed_reward_ledgers[0].points_delta), 20)

            print("Invite rebate verification passed")
            print(
                "checks=level1 50%, level2 5%, frozen points, duplicate callback idempotency, "
                "level1 unfreeze idempotency, level2 unfreeze idempotency, "
                "vip order does not grant fixed recharge reward, points recharge does grant fixed reward"
            )
        finally:
            await session.rollback()


async def _assert_required_tables(session) -> None:
    connection = await session.connection()
    table_names = await connection.run_sync(lambda sync_conn: set(inspect(sync_conn).get_table_names()))
    missing = sorted(REQUIRED_TABLES - table_names)
    if missing:
        raise RuntimeError(
            "Missing required tables for invite-rebate verification: "
            + ", ".join(missing)
            + ". Run the Stage 2 Alembic migrations against the intended database first."
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify Stage 2 invite rebate flow.")
    parser.add_argument("--execute", action="store_true", help="run verification against the configured database")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.execute:
        print("Dry run only. Re-run with --execute to verify against the configured database.")
        print(
            "Checks: level1 50%, level2 5%, frozen points, duplicate callback idempotency, "
            "level1 unfreeze idempotency, level2 unfreeze idempotency."
        )
        return

    try:
        asyncio.run(verify())
    except RuntimeError as exc:
        print(f"Verification blocked: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
