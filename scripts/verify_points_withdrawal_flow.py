"""Verify Stage 2 points-withdrawal flow.

Checks:
1. summary returns correct first/member/normal thresholds
2. insufficient or below-threshold apply requests are rejected
3. successful apply locks withdrawable points
4. failed/rejected withdrawal returns locked points
5. successful transfer settles locked points into withdrawn_points

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
from sqlmodel import select

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from models.base import async_session_factory  # noqa: E402
from models.points_ledger import PointsLedger  # noqa: E402
from models.user import User  # noqa: E402
from models.withdrawal import WithdrawalRecord  # noqa: E402
from services.config_service import ConfigService  # noqa: E402
from services.points_account_service import PointsAccountService  # noqa: E402
from services.withdrawal_service import WithdrawalService  # noqa: E402

REQUIRED_TABLES = {"users", "user_accounts", "points_ledger", "withdraw_records", "system_configs"}


def _assert_equal(label: str, actual, expected) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def _assert_true(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)


async def _fake_submit_processing_withdrawal(session, record_id, openid=None, allow_existing_submission=False):
    record = await session.get(WithdrawalRecord, record_id)
    return record, None


async def verify() -> None:
    marker = f"stage2-withdraw-{uuid.uuid4().hex[:10]}"

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
                    "withdraw_min_normal": 5.00,
                    "withdraw_min_member": 1.00,
                    "max_amount": 200.00,
                    "daily_limit": 100.00,
                    "tips": "test withdrawal config",
                },
            )
            await ConfigService.set(session, "stage2_points_config", {"exchange_rate": 100})

            first_user = User(openid=f"{marker}-first", nickname="Withdraw First", avatar="", invite_code=marker[-10:])
            normal_user = User(openid=f"{marker}-normal", nickname="Withdraw Normal", avatar="", invite_code=f"{marker}n"[-10:])
            member_user = User(
                openid=f"{marker}-member",
                nickname="Withdraw Member",
                avatar="",
                invite_code=f"{marker}m"[-10:],
                is_vip=True,
            )
            rejected_user = User(openid=f"{marker}-reject", nickname="Withdraw Reject", avatar="", invite_code=f"{marker}r"[-10:])
            success_user = User(openid=f"{marker}-success", nickname="Withdraw Success", avatar="", invite_code=f"{marker}s"[-10:])
            session.add(first_user)
            session.add(normal_user)
            session.add(member_user)
            session.add(rejected_user)
            session.add(success_user)
            await session.flush()

            normal_prior_record = WithdrawalRecord(user_id=normal_user.id, amount=1.0, status="success", batch_no=f"{marker}-done-1")
            member_prior_record = WithdrawalRecord(user_id=member_user.id, amount=1.0, status="success", batch_no=f"{marker}-done-2")
            session.add(normal_prior_record)
            session.add(member_prior_record)
            await session.flush()

            first_summary = await WithdrawalService.get_points_withdrawal_summary(session, first_user.id)
            normal_summary = await WithdrawalService.get_points_withdrawal_summary(session, normal_user.id)
            member_summary = await WithdrawalService.get_points_withdrawal_summary(session, member_user.id)
            _assert_equal("first min points", int(first_summary["min_withdraw_points"]), 100)
            _assert_equal("normal min points", int(normal_summary["min_withdraw_points"]), 500)
            _assert_equal("member min points", int(member_summary["min_withdraw_points"]), 100)

            with patch("services.withdrawal_service._get_transfer_notify_url", return_value="https://example.com/notify"), patch.object(
                WithdrawalService,
                "submit_processing_withdrawal",
                side_effect=_fake_submit_processing_withdrawal,
            ):
                low_record, low_account, low_error = await WithdrawalService.apply_points_withdrawal(
                    session,
                    first_user.id,
                    50,
                    openid=first_user.openid,
                )
                _assert_equal("low threshold record", low_record, None)
                _assert_equal("low threshold account", low_account, None)
                _assert_true("low threshold error expected", "minimum withdrawal points" in str(low_error))

                insufficient_record, insufficient_account, insufficient_error = await WithdrawalService.apply_points_withdrawal(
                    session,
                    first_user.id,
                    100,
                    openid=first_user.openid,
                )
                _assert_equal("insufficient record", insufficient_record, None)
                _assert_equal("insufficient account", insufficient_account, None)
                _assert_true("insufficient error expected", "insufficient withdrawable points" in str(insufficient_error))

                await PointsAccountService.add_points(
                    session=session,
                    user_id=rejected_user.id,
                    points=500,
                    source="admin_adjust",
                    change_type="adjust_add",
                    availability="withdrawable",
                    idempotency_key=f"{marker}:reject:seed",
                )
                await PointsAccountService.add_points(
                    session=session,
                    user_id=success_user.id,
                    points=500,
                    source="admin_adjust",
                    change_type="adjust_add",
                    availability="withdrawable",
                    idempotency_key=f"{marker}:success:seed",
                )

                reject_record, reject_account, reject_error = await WithdrawalService.apply_points_withdrawal(
                    session,
                    rejected_user.id,
                    500,
                    openid=rejected_user.openid,
                )
                _assert_equal("reject apply error", reject_error, None)
                _assert_equal("reject apply status", reject_record.status, "processing")
                _assert_equal("reject apply locked points", int(reject_account["locked_withdraw_points"]), 500)
                _assert_equal("reject apply withdrawable points", int(reject_account["withdrawable_points"]), 0)

                success_record, success_account, success_error = await WithdrawalService.apply_points_withdrawal(
                    session,
                    success_user.id,
                    500,
                    openid=success_user.openid,
                )
                _assert_equal("success apply error", success_error, None)
                _assert_equal("success apply status", success_record.status, "processing")
                _assert_equal("success apply locked points", int(success_account["locked_withdraw_points"]), 500)

            reject_ok = await WithdrawalService.handle_transfer_failed(session, reject_record.batch_no, "admin_reject")
            _assert_equal("reject handle result", reject_ok, True)
            reject_latest_account, _ = await PointsAccountService.ensure_user_account(session, rejected_user.id)
            _assert_equal("reject locked points returned", int(reject_latest_account.locked_withdraw_points), 0)
            _assert_equal("reject withdrawable returned", int(reject_latest_account.withdrawable_points), 500)

            success_ok = await WithdrawalService.handle_transfer_success(session, success_record.batch_no, f"{marker}-bill")
            _assert_equal("success handle result", success_ok, True)
            success_latest_account, _ = await PointsAccountService.ensure_user_account(session, success_user.id)
            _assert_equal("success locked points cleared", int(success_latest_account.locked_withdraw_points), 0)
            _assert_equal("success withdrawn points", int(success_latest_account.withdrawn_points), 500)

            reject_ledger_rows = await session.execute(
                select(PointsLedger).where(
                    PointsLedger.user_id == rejected_user.id,
                    PointsLedger.related_type == "withdraw_record",
                )
            )
            reject_ledger_types = sorted(row.change_type for row in reject_ledger_rows.scalars().all())
            _assert_equal("reject ledger types", reject_ledger_types, ["withdraw_lock", "withdraw_reject_return"])

            success_ledger_rows = await session.execute(
                select(PointsLedger).where(
                    PointsLedger.user_id == success_user.id,
                    PointsLedger.related_type == "withdraw_record",
                )
            )
            success_ledger_types = sorted(row.change_type for row in success_ledger_rows.scalars().all())
            _assert_equal("success ledger types", success_ledger_types, ["withdraw_lock", "withdraw_success"])

            print("Points withdrawal verification passed")
            print("checks=thresholds, insufficient, lock, reject return, success settle")
        finally:
            await session.rollback()


async def _assert_required_tables(session) -> None:
    connection = await session.connection()
    table_names = await connection.run_sync(lambda sync_conn: set(inspect(sync_conn).get_table_names()))
    missing = sorted(REQUIRED_TABLES - table_names)
    if missing:
        raise RuntimeError(
            "Missing required tables for points-withdrawal verification: "
            + ", ".join(missing)
            + ". Run the Stage 2 Alembic migrations against the intended database first."
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify Stage 2 points-withdrawal flow.")
    parser.add_argument("--execute", action="store_true", help="run verification against the configured database")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.execute:
        print("Dry run only. Re-run with --execute to verify against the configured database.")
        print("Checks: thresholds, insufficient, lock, reject return, success settle.")
        return

    try:
        asyncio.run(verify())
    except RuntimeError as exc:
        print(f"Verification blocked: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
