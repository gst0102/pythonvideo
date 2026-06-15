"""Verify equity/cash withdrawal safety flow.

Checks:
1. applying a withdrawal freezes balance and creates one processing record
2. another apply while processing is blocked and does not change balances
3. failed transfer callback returns frozen balance
4. successful transfer callback clears frozen balance and records withdrawn amount
5. repeated callbacks are idempotent

By default it only prints the plan. Pass --execute to run against the current
database inside a rollback transaction.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import inspect
from sqlmodel import func, select

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from models.base import async_session_factory  # noqa: E402
from models.user import User  # noqa: E402
from models.withdrawal import WithdrawalRecord  # noqa: E402
from services.config_service import ConfigService  # noqa: E402
from services.withdrawal_service import WithdrawalService  # noqa: E402

REQUIRED_TABLES = {"users", "withdraw_records", "system_configs"}


def _assert_equal(label: str, actual, expected) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def _assert_true(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)


def _money(value) -> float:
    return round(float(value or 0), 2)


async def _fake_submit_processing_withdrawal(session, record_id, openid=None, allow_existing_submission=False):
    record = await session.get(WithdrawalRecord, record_id)
    return record, None


async def verify() -> None:
    marker = f"equity-withdraw-{uuid.uuid4().hex[:10]}"

    async with async_session_factory() as session:
        try:
            await _assert_required_tables(session)
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

            user = User(
                openid=f"{marker}-openid",
                nickname="Equity Withdraw",
                avatar="",
                invite_code=marker[-10:],
                balance=10.00,
                frozen_balance=0.00,
                total_income=10.00,
                total_withdrawn=0.00,
            )
            session.add(user)
            await session.flush()

            with patch("services.withdrawal_service._get_transfer_notify_url", return_value="https://example.com/notify"), patch.object(
                WithdrawalService,
                "submit_processing_withdrawal",
                side_effect=_fake_submit_processing_withdrawal,
            ):
                first_record, first_error = await WithdrawalService.apply_withdrawal(
                    session,
                    user.id,
                    3.50,
                    openid=user.openid,
                )
                _assert_equal("first apply error", first_error, None)
                _assert_equal("first apply status", first_record.status, "processing")
                _assert_equal("balance after freeze", _money(user.balance), 6.50)
                _assert_equal("frozen after freeze", _money(user.frozen_balance), 3.50)

                duplicate_record, duplicate_error = await WithdrawalService.apply_withdrawal(
                    session,
                    user.id,
                    2.00,
                    openid=user.openid,
                )
                _assert_equal("duplicate apply record", duplicate_record, None)
                _assert_equal("duplicate apply error", duplicate_error, "existing withdrawal is processing")
                _assert_equal("balance unchanged after duplicate", _money(user.balance), 6.50)
                _assert_equal("frozen unchanged after duplicate", _money(user.frozen_balance), 3.50)

            record_count_result = await session.execute(
                select(func.count()).select_from(WithdrawalRecord).where(WithdrawalRecord.user_id == user.id)
            )
            _assert_equal("one record after duplicate block", int(record_count_result.scalar() or 0), 1)

            failed_ok = await WithdrawalService.handle_transfer_failed(session, first_record.batch_no, "test_failed")
            _assert_equal("failed callback result", failed_ok, True)
            _assert_equal("balance returned after failed", _money(user.balance), 10.00)
            _assert_equal("frozen cleared after failed", _money(user.frozen_balance), 0.00)

            failed_again_ok = await WithdrawalService.handle_transfer_failed(session, first_record.batch_no, "test_failed_again")
            _assert_equal("failed callback idempotent result", failed_again_ok, True)
            _assert_equal("balance unchanged after repeated failed", _money(user.balance), 10.00)
            _assert_equal("frozen unchanged after repeated failed", _money(user.frozen_balance), 0.00)

            with patch("services.withdrawal_service._get_transfer_notify_url", return_value="https://example.com/notify"), patch.object(
                WithdrawalService,
                "submit_processing_withdrawal",
                side_effect=_fake_submit_processing_withdrawal,
            ):
                second_record, second_error = await WithdrawalService.apply_withdrawal(
                    session,
                    user.id,
                    4.00,
                    openid=user.openid,
                )
                _assert_equal("second apply error", second_error, None)
                _assert_equal("balance after second freeze", _money(user.balance), 6.00)
                _assert_equal("frozen after second freeze", _money(user.frozen_balance), 4.00)

            success_ok = await WithdrawalService.handle_transfer_success(session, second_record.batch_no, f"{marker}-bill")
            _assert_equal("success callback result", success_ok, True)
            _assert_equal("balance after success", _money(user.balance), 6.00)
            _assert_equal("frozen cleared after success", _money(user.frozen_balance), 0.00)
            _assert_equal("total withdrawn after success", _money(user.total_withdrawn), 4.00)

            success_again_ok = await WithdrawalService.handle_transfer_success(session, second_record.batch_no, f"{marker}-bill-2")
            _assert_equal("success callback idempotent result", success_again_ok, True)
            _assert_equal("total withdrawn unchanged after repeated success", _money(user.total_withdrawn), 4.00)

            print("Equity withdrawal verification passed")
            print("checks=freeze, duplicate-block, failed-return, success-settle, callback-idempotency")
        finally:
            await session.rollback()


async def _assert_required_tables(session) -> None:
    connection = await session.connection()
    table_names = await connection.run_sync(lambda sync_conn: set(inspect(sync_conn).get_table_names()))
    missing = sorted(REQUIRED_TABLES - table_names)
    if missing:
        raise RuntimeError(
            "Missing required tables for equity-withdrawal verification: "
            + ", ".join(missing)
            + ". Run the migrations against the intended database first."
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify equity/cash withdrawal flow.")
    parser.add_argument("--execute", action="store_true", help="run verification against the configured database")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.execute:
        print("Dry run only. Re-run with --execute to verify against the configured database.")
        print("Checks: freeze, duplicate block, failed return, success settle, callback idempotency.")
        return

    try:
        asyncio.run(verify())
    except RuntimeError as exc:
        print(f"Verification blocked: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
