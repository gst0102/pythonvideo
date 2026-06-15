"""Verify netdisk feedback reward flow.

Checks:
1. user submits feedback ticket
2. admin resolves ticket with reward points
3. reward enters consumable points and points ledger
4. repeated admin resolve is idempotent and does not grant twice

By default this script only prints the plan. Pass --execute to run against the
configured database inside a rollback transaction.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

from sqlalchemy import inspect
from sqlmodel import select

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from models.base import async_session_factory  # noqa: E402
from models.netdisk_feedback import NetdiskFeedback  # noqa: E402
from models.points_ledger import PointsLedger  # noqa: E402
from models.user import User  # noqa: E402
from services.netdisk_resource_service import NetdiskResourceService  # noqa: E402
from services.points_account_service import PointsAccountService  # noqa: E402

REQUIRED_TABLES = {"users", "user_accounts", "points_ledger", "netdisk_feedbacks"}


def _assert_equal(label: str, actual, expected) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


async def verify() -> None:
    marker = f"feedback-reward-{uuid.uuid4().hex[:10]}"
    reward_points = 20

    async with async_session_factory() as session:
        try:
            await _assert_required_tables(session)
            user = User(openid=f"{marker}-user", nickname="Feedback Reward User", avatar="", invite_code=marker[-10:])
            session.add(user)
            await session.flush()

            before_account, _ = await PointsAccountService.ensure_user_account(session, user.id)
            _assert_equal("initial consumable points", int(before_account.consumable_points), 0)

            created_payload = await NetdiskResourceService.create_feedback(
                session=session,
                user=user,
                feedback_type="feature",
                content="希望资源页增加更清晰的分类筛选。",
                contact="test-contact",
            )
            feedback = created_payload["feedback"]
            feedback_id = feedback["id"]
            _assert_equal("feedback status", feedback["status"], "pending")
            _assert_equal("feedback reward before resolve", int(feedback["reward_points"]), 0)

            resolved_payload = await NetdiskResourceService.update_admin_feedback(
                session=session,
                feedback_id=feedback_id,
                status="resolved",
                admin_reply="建议已采纳，奖励已发放。",
                reward_points=reward_points,
            )
            resolved = resolved_payload["feedback"]
            _assert_equal("resolved status", resolved["status"], "resolved")
            _assert_equal("resolved reward points", int(resolved["reward_points"]), reward_points)
            if not resolved["reward_ledger_id"]:
                raise AssertionError("reward ledger id was not returned")

            account_after, _ = await PointsAccountService.ensure_user_account(session, user.id)
            _assert_equal("consumable after reward", int(account_after.consumable_points), reward_points)
            _assert_equal("total after reward", int(account_after.total_points), reward_points)

            ledger_result = await session.execute(
                select(PointsLedger).where(
                    PointsLedger.user_id == user.id,
                    PointsLedger.source == "feedback_reward",
                    PointsLedger.change_type == "feedback_reward",
                    PointsLedger.related_type == "netdisk_feedback",
                    PointsLedger.related_id == feedback_id,
                )
            )
            ledgers = list(ledger_result.scalars().all())
            _assert_equal("feedback reward ledger count", len(ledgers), 1)
            _assert_equal("feedback reward ledger delta", int(ledgers[0].points_delta), reward_points)
            _assert_equal("feedback reward idempotency key", ledgers[0].idempotency_key, f"feedback_reward:{feedback_id}")

            replay_payload = await NetdiskResourceService.update_admin_feedback(
                session=session,
                feedback_id=feedback_id,
                status="resolved",
                admin_reply="重复保存不应重复发放。",
                reward_points=reward_points,
            )
            replay = replay_payload["feedback"]
            _assert_equal("replay reward points", int(replay["reward_points"]), reward_points)
            replay_account, _ = await PointsAccountService.ensure_user_account(session, user.id)
            _assert_equal("replay consumable unchanged", int(replay_account.consumable_points), reward_points)

            replay_ledger_result = await session.execute(
                select(PointsLedger).where(
                    PointsLedger.user_id == user.id,
                    PointsLedger.source == "feedback_reward",
                    PointsLedger.related_id == feedback_id,
                )
            )
            replay_ledgers = list(replay_ledger_result.scalars().all())
            _assert_equal("replay ledger count unchanged", len(replay_ledgers), 1)

            db_feedback = await session.get(NetdiskFeedback, uuid.UUID(feedback_id))
            if not db_feedback:
                raise AssertionError("feedback row not found")
            _assert_equal("db feedback reward points", int(db_feedback.reward_points), reward_points)
            _assert_equal("db feedback reward ledger id", str(db_feedback.reward_ledger_id), str(ledgers[0].id))

            print("Feedback reward verification passed")
            print("checks=create ticket, resolve reward, ledger/account consistency, idempotent replay")
        finally:
            await session.rollback()


async def _assert_required_tables(session) -> None:
    connection = await session.connection()
    table_names = await connection.run_sync(lambda sync_conn: set(inspect(sync_conn).get_table_names()))
    missing = sorted(REQUIRED_TABLES - table_names)
    if missing:
        raise RuntimeError(
            "Missing required tables for feedback reward verification: "
            + ", ".join(missing)
            + ". Run Alembic migrations against the intended database first."
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify netdisk feedback reward flow.")
    parser.add_argument("--execute", action="store_true", help="run verification against the configured database")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.execute:
        print("Dry run only. Re-run with --execute to verify against the configured database.")
        print("Checks: create ticket, resolve reward, ledger/account consistency, idempotent replay.")
        return

    try:
        asyncio.run(verify())
    except RuntimeError as exc:
        print(f"Verification blocked: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
