"""Verify payment refund clawback flow.

The script runs inside a rollback transaction when called with --execute.
It covers:
1. VIP order refund revokes vip gift points and invite rebate points.
2. Settled invite rebate is clawed back from withdrawable points.
3. Points recharge refund revokes recharge points and first-recharge invite reward.
4. Refund and late payment-success replays are idempotent.
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
    marker = f"stage2-refund-{uuid.uuid4().hex[:10]}"

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
                    "rules": "test refund config",
                },
            )

            grandparent = User(
                openid=f"{marker}-grand",
                nickname="Refund Grand",
                avatar="",
                invite_code=f"{marker}g"[-10:],
            )
            parent = User(
                openid=f"{marker}-parent",
                nickname="Refund Parent",
                avatar="",
                invite_code=f"{marker}p"[-10:],
                parent_id=grandparent.id,
            )
            buyer = User(
                openid=f"{marker}-buyer",
                nickname="Refund Buyer",
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

            vip_order = Order(
                user_id=buyer.id,
                amount=10.00,
                period="month",
                duration_days=30,
                description="Stage2 refund VIP verification",
                out_trade_no=f"{marker}-vip-order",
                status="pending",
            )
            session.add(vip_order)
            await session.flush()

            ok = await PaymentService.handle_payment_success(
                session=session,
                out_trade_no=vip_order.out_trade_no,
                transaction_id=f"{marker}-vip-tx",
                total_fee_in_fen=1000,
                paid_at=datetime.now(timezone.utc).isoformat(),
            )
            _assert_equal("vip payment success", ok, True)

            records_result = await session.execute(
                select(CommissionRecord).where(CommissionRecord.order_id == vip_order.id).order_by(CommissionRecord.level)
            )
            records = list(records_result.scalars().all())
            _assert_equal("vip commission count", len(records), 2)
            level1, level2 = records
            await CommissionService.release_commission_points(session, level1.id)

            refund_ok = await PaymentService.handle_payment_refund(
                session=session,
                out_trade_no=vip_order.out_trade_no,
                refund_id=f"{marker}-vip-refund",
                refunded_at=datetime.now(timezone.utc).isoformat(),
            )
            _assert_equal("vip refund success", refund_ok, True)
            _assert_equal("vip order status", vip_order.status, "refunded")

            buyer_account, _ = await PointsAccountService.ensure_user_account(session, buyer.id)
            parent_account, _ = await PointsAccountService.ensure_user_account(session, parent.id)
            grand_account, _ = await PointsAccountService.ensure_user_account(session, grandparent.id)
            _assert_equal("buyer withdrawable after vip refund", int(buyer_account.withdrawable_points), 0)
            _assert_equal("buyer total after vip refund", int(buyer_account.total_points), 0)
            _assert_equal("settled level1 withdrawable after refund", int(parent_account.withdrawable_points), 0)
            _assert_equal("settled level1 total after refund", int(parent_account.total_points), 0)
            _assert_equal("pending level2 frozen after refund", int(grand_account.frozen_points), 0)
            _assert_equal("pending level2 total after refund", int(grand_account.total_points), 0)
            _assert_equal("level1 status after refund", level1.status, "cancelled")
            _assert_equal("level2 status after refund", level2.status, "cancelled")

            refund_replay_ok = await PaymentService.handle_payment_refund(
                session=session,
                out_trade_no=vip_order.out_trade_no,
                refund_id=f"{marker}-vip-refund-replay",
                refunded_at=datetime.now(timezone.utc).isoformat(),
            )
            _assert_equal("vip refund replay", refund_replay_ok, True)
            success_replay_ok = await PaymentService.handle_payment_success(
                session=session,
                out_trade_no=vip_order.out_trade_no,
                transaction_id=f"{marker}-vip-tx-late",
                total_fee_in_fen=1000,
                paid_at=datetime.now(timezone.utc).isoformat(),
            )
            _assert_equal("late success after refund", success_replay_ok, True)

            vip_gift_refunds = await _ledger_count(session, "vip_gift_refund", str(vip_order.id))
            _assert_equal("vip gift refund ledger count", vip_gift_refunds, 1)
            rebate_refunds = await _source_ledger_count(session, "refund", prefix="invite_rebate_refund")
            _assert_equal("invite rebate refund ledger count", rebate_refunds, 2)

            points_parent = User(
                openid=f"{marker}-points-parent",
                nickname="Points Refund Parent",
                avatar="",
                invite_code=f"{marker}pp"[-10:],
            )
            points_buyer = User(
                openid=f"{marker}-points-buyer",
                nickname="Points Refund Buyer",
                avatar="",
                invite_code=f"{marker}pb"[-10:],
                parent_id=points_parent.id,
            )
            session.add(points_parent)
            session.add(points_buyer)
            await session.flush()
            session.add(
                InviteRelation(
                    inviter_id=points_parent.id,
                    invitee_id=points_buyer.id,
                    invite_code=points_parent.invite_code,
                    source="test",
                )
            )
            await session.flush()

            points_order = Order(
                user_id=points_buyer.id,
                amount=1.00,
                period="points_10",
                duration_days=0,
                description="Stage2 refund points verification",
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
            _assert_equal("points payment success", points_ok, True)

            points_refund_ok = await PaymentService.handle_payment_refund(
                session=session,
                out_trade_no=points_order.out_trade_no,
                refund_id=f"{marker}-points-refund",
                refunded_at=datetime.now(timezone.utc).isoformat(),
            )
            _assert_equal("points refund success", points_refund_ok, True)

            points_buyer_account, _ = await PointsAccountService.ensure_user_account(session, points_buyer.id)
            points_parent_account, _ = await PointsAccountService.ensure_user_account(session, points_parent.id)
            _assert_equal("points buyer consumable after refund", int(points_buyer_account.consumable_points), 0)
            _assert_equal("points buyer total after refund", int(points_buyer_account.total_points), 0)
            _assert_equal("first recharge parent consumable after refund", int(points_parent_account.consumable_points), 0)
            _assert_equal("first recharge parent total after refund", int(points_parent_account.total_points), 0)

            points_refund_replay_ok = await PaymentService.handle_payment_refund(
                session=session,
                out_trade_no=points_order.out_trade_no,
                refund_id=f"{marker}-points-refund-replay",
                refunded_at=datetime.now(timezone.utc).isoformat(),
            )
            _assert_equal("points refund replay", points_refund_replay_ok, True)
            points_recharge_refunds = await _ledger_count(session, "points_recharge_refund", str(points_order.id))
            _assert_equal("points recharge refund ledger count", points_recharge_refunds, 1)
            first_recharge_refunds = await _ledger_count(session, "invite_first_recharge_refund", str(points_order.id))
            _assert_equal("first recharge refund ledger count", first_recharge_refunds, 1)

            print("Payment refund verification passed")
            print(
                "checks=vip gift refund, invite rebate refund pending+settled, points recharge refund, "
                "first recharge reward refund, refund idempotency, late success replay ignored"
            )
        finally:
            await session.rollback()


async def _ledger_count(session, change_type: str, related_id: str) -> int:
    result = await session.execute(
        select(PointsLedger).where(
            PointsLedger.change_type == change_type,
            PointsLedger.related_id == related_id,
        )
    )
    return len(list(result.scalars().all()))


async def _source_ledger_count(session, source: str, prefix: str) -> int:
    result = await session.execute(
        select(PointsLedger).where(
            PointsLedger.source == source,
            PointsLedger.change_type.startswith(prefix),
        )
    )
    return len(list(result.scalars().all()))


async def _assert_required_tables(session) -> None:
    connection = await session.connection()
    table_names = await connection.run_sync(lambda sync_conn: set(inspect(sync_conn).get_table_names()))
    missing = sorted(REQUIRED_TABLES - table_names)
    if missing:
        raise RuntimeError(
            "Missing required tables for payment-refund verification: "
            + ", ".join(missing)
            + ". Run the Stage 2 Alembic migrations against the intended database first."
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify Stage 2 payment refund flow.")
    parser.add_argument("--execute", action="store_true", help="run verification against the configured database")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.execute:
        print("Dry run only. Re-run with --execute to verify against the configured database.")
        print(
            "Checks: vip gift refund, invite rebate refund, points recharge refund, "
            "first recharge reward refund, refund idempotency."
        )
        return

    try:
        asyncio.run(verify())
    except RuntimeError as exc:
        print(f"Verification blocked: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
