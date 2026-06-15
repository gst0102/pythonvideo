"""Verify equity ledger movements.

Runs in a rollback transaction with --execute.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import inspect
from sqlmodel import select

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from models.base import async_session_factory  # noqa: E402
from models.equity_ledger import EquityLedger  # noqa: E402
from models.invite_relation import InviteRelation  # noqa: E402
from models.order import Order  # noqa: E402
from models.user import User  # noqa: E402
from models.withdrawal import WithdrawalRecord  # noqa: E402
from services.config_service import ConfigService  # noqa: E402
from services.payment_service import PaymentService  # noqa: E402
from services.withdrawal_service import WithdrawalService  # noqa: E402

REQUIRED_TABLES = {"users", "orders", "invite_relations", "commission_records", "withdraw_records", "equity_ledger", "system_configs"}


def _assert_equal(label: str, actual, expected) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def _money(value) -> float:
    return round(float(value or 0), 2)


async def _fake_submit_processing_withdrawal(session, record_id, openid=None, allow_existing_submission=False):
    record = await session.get(WithdrawalRecord, record_id)
    return record, None


async def verify() -> None:
    marker = f"equity-ledger-{uuid.uuid4().hex[:10]}"

    async with async_session_factory() as session:
        try:
            await _assert_required_tables(session)
            await ConfigService.set(session, "stage2_points_config", {"exchange_rate": 100})
            await ConfigService.set(session, "commission_settings", {"level1_rate": 50.0, "level2_rate": 5.0})
            await ConfigService.set(
                session,
                "withdrawal_config",
                {
                    "enabled": True,
                    "min_amount": 0.10,
                    "withdraw_min_first": 1.00,
                    "withdraw_min_normal": 1.00,
                    "withdraw_min_member": 1.00,
                    "max_amount": 200.00,
                    "daily_limit": 100.00,
                    "tips": "提现申请提交后，预计24小时内到账。",
                },
            )

            inviter = User(openid=f"{marker}-inviter", nickname="Equity Inviter", avatar="", invite_code=f"{marker}i"[-10:])
            buyer = User(
                openid=f"{marker}-buyer",
                nickname="Equity Buyer",
                avatar="",
                invite_code=f"{marker}b"[-10:],
                parent_id=inviter.id,
            )
            session.add(inviter)
            session.add(buyer)
            await session.flush()
            session.add(InviteRelation(inviter_id=inviter.id, invitee_id=buyer.id, invite_code=inviter.invite_code, source="test"))
            await session.flush()

            order = Order(
                user_id=buyer.id,
                amount=10.00,
                period="card_month_10",
                duration_days=30,
                description="equity ledger card order",
                out_trade_no=f"{marker}-card",
                status="pending",
            )
            session.add(order)
            await session.flush()
            pay_ok = await PaymentService.handle_payment_success(
                session,
                out_trade_no=order.out_trade_no,
                transaction_id=f"{marker}-tx",
                total_fee_in_fen=1000,
                paid_at=datetime.now(timezone.utc).isoformat(),
            )
            _assert_equal("card payment success", pay_ok, True)

            invite_ledgers = await _ledgers(session, inviter.id, "invite_reward")
            _assert_equal("invite reward ledger count", len(invite_ledgers), 1)
            invite_ledger = invite_ledgers[0]
            _assert_equal("invite reward amount delta", _money(invite_ledger.amount_delta), 5.00)
            _assert_equal("invite reward income delta", _money(invite_ledger.total_income_delta), 5.00)
            _assert_equal("invite reward balance after", _money(invite_ledger.balance_after), 5.00)
            _assert_equal("invite reward income after", _money(invite_ledger.total_income_after), 5.00)

            refund_ok = await PaymentService.handle_payment_refund(
                session,
                out_trade_no=order.out_trade_no,
                refund_id=f"{marker}-refund",
                refunded_at=datetime.now(timezone.utc).isoformat(),
            )
            _assert_equal("card refund success", refund_ok, True)
            refund_replay_ok = await PaymentService.handle_payment_refund(
                session,
                out_trade_no=order.out_trade_no,
                refund_id=f"{marker}-refund-replay",
                refunded_at=datetime.now(timezone.utc).isoformat(),
            )
            _assert_equal("card refund replay", refund_replay_ok, True)

            refund_ledgers = await _ledgers(session, inviter.id, "refund_revoke")
            _assert_equal("refund revoke ledger count", len(refund_ledgers), 1)
            refund_ledger = refund_ledgers[0]
            _assert_equal("refund amount delta", _money(refund_ledger.amount_delta), -5.00)
            _assert_equal("refund income delta", _money(refund_ledger.total_income_delta), -5.00)
            _assert_equal("refund balance after", _money(refund_ledger.balance_after), 0.00)
            _assert_equal("refund income after", _money(refund_ledger.total_income_after), 0.00)

            withdraw_user = User(
                openid=f"{marker}-withdraw",
                nickname="Equity Withdraw",
                avatar="",
                invite_code=f"{marker}w"[-10:],
                balance=10.00,
                total_income=10.00,
            )
            session.add(withdraw_user)
            await session.flush()

            with patch("services.withdrawal_service._get_transfer_notify_url", return_value="https://example.com/notify"), patch.object(
                WithdrawalService,
                "submit_processing_withdrawal",
                side_effect=_fake_submit_processing_withdrawal,
            ):
                failed_record, failed_error = await WithdrawalService.apply_withdrawal(
                    session,
                    withdraw_user.id,
                    3.50,
                    openid=withdraw_user.openid,
                )
                _assert_equal("withdraw apply error", failed_error, None)

            freeze_ledgers = await _ledgers(session, withdraw_user.id, "withdraw_freeze")
            _assert_equal("withdraw freeze ledger count after first apply", len(freeze_ledgers), 1)
            _assert_equal("freeze balance after", _money(freeze_ledgers[0].balance_after), 6.50)
            _assert_equal("freeze frozen after", _money(freeze_ledgers[0].frozen_balance_after), 3.50)

            failed_ok = await WithdrawalService.handle_transfer_failed(session, failed_record.batch_no, "test_failed")
            _assert_equal("withdraw failed callback", failed_ok, True)
            failed_replay_ok = await WithdrawalService.handle_transfer_failed(session, failed_record.batch_no, "test_failed_replay")
            _assert_equal("withdraw failed replay", failed_replay_ok, True)
            failed_return_ledgers = await _ledgers(session, withdraw_user.id, "withdraw_failed_return")
            _assert_equal("withdraw failed return ledger count", len(failed_return_ledgers), 1)
            _assert_equal("failed return balance after", _money(failed_return_ledgers[0].balance_after), 10.00)
            _assert_equal("failed return frozen after", _money(failed_return_ledgers[0].frozen_balance_after), 0.00)

            with patch("services.withdrawal_service._get_transfer_notify_url", return_value="https://example.com/notify"), patch.object(
                WithdrawalService,
                "submit_processing_withdrawal",
                side_effect=_fake_submit_processing_withdrawal,
            ):
                success_record, success_error = await WithdrawalService.apply_withdrawal(
                    session,
                    withdraw_user.id,
                    4.00,
                    openid=withdraw_user.openid,
                )
                _assert_equal("second withdraw apply error", success_error, None)

            success_ok = await WithdrawalService.handle_transfer_success(session, success_record.batch_no, f"{marker}-bill")
            _assert_equal("withdraw success callback", success_ok, True)
            success_replay_ok = await WithdrawalService.handle_transfer_success(session, success_record.batch_no, f"{marker}-bill-replay")
            _assert_equal("withdraw success replay", success_replay_ok, True)

            freeze_ledgers_after = await _ledgers(session, withdraw_user.id, "withdraw_freeze")
            _assert_equal("withdraw freeze ledger count after second apply", len(freeze_ledgers_after), 2)
            success_ledgers = await _ledgers(session, withdraw_user.id, "withdraw_success")
            _assert_equal("withdraw success ledger count", len(success_ledgers), 1)
            _assert_equal("success frozen after", _money(success_ledgers[0].frozen_balance_after), 0.00)
            _assert_equal("success withdrawn after", _money(success_ledgers[0].total_withdrawn_after), 4.00)

            print("Equity ledger verification passed")
            print("checks=invite reward, refund revoke, withdraw freeze, withdraw failed return, withdraw success, idempotency")
        finally:
            await session.rollback()


async def _ledgers(session, user_id, change_type: str) -> list[EquityLedger]:
    result = await session.execute(
        select(EquityLedger)
        .where(EquityLedger.user_id == user_id, EquityLedger.change_type == change_type)
        .order_by(EquityLedger.created_at.asc(), EquityLedger.id.asc())
    )
    return list(result.scalars().all())


async def _assert_required_tables(session) -> None:
    connection = await session.connection()
    table_names = await connection.run_sync(lambda sync_conn: set(inspect(sync_conn).get_table_names()))
    missing = sorted(REQUIRED_TABLES - table_names)
    if missing:
        raise RuntimeError("Missing required tables for equity-ledger verification: " + ", ".join(missing))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify equity ledger flow.")
    parser.add_argument("--execute", action="store_true", help="run verification against the configured database")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.execute:
        print("Dry run only. Re-run with --execute to verify against the configured database.")
        print("Checks: invite reward, refund revoke, withdraw freeze, withdraw failed return, withdraw success.")
        return
    try:
        asyncio.run(verify())
    except RuntimeError as exc:
        print(f"Verification blocked: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
