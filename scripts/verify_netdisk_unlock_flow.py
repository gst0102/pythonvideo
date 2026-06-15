"""Verify netdisk resource unlock and invite first-resource reward flow.

By default it only prints the plan. Pass --execute to run against the current
database inside a rollback transaction.
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
from models.points_ledger import PointsLedger  # noqa: E402
from models.user import User  # noqa: E402
from services.netdisk_resource_service import NetdiskResourceService  # noqa: E402
from services.points_account_service import PointsAccountService  # noqa: E402
from services.user_service import UserService  # noqa: E402

REQUIRED_TABLES = {"users", "user_accounts", "points_ledger", "invite_relations"}


def _assert_equal(label: str, actual, expected) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def _assert_true(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)


async def verify() -> None:
    marker = f"netdisk-unlock-{uuid.uuid4().hex[:10]}"

    async with async_session_factory() as session:
        try:
            await _assert_required_tables(session)

            inviter, _ = await UserService.get_or_create_user(
                session,
                openid=f"{marker}-inviter",
                nickname="Netdisk Inviter",
                avatar="",
            )
            invitee, _ = await UserService.get_or_create_user(
                session,
                openid=f"{marker}-invitee",
                nickname="Netdisk Invitee",
                avatar="",
                invite_code=inviter.invite_code,
            )
            inviter_account, _ = await PointsAccountService.ensure_user_account(session, inviter.id)
            _assert_equal("register invite reward", int(inviter_account.consumable_points), 5)

            await PointsAccountService.add_points(
                session=session,
                user_id=invitee.id,
                points=50,
                source="admin_adjust",
                change_type="adjust_add",
                availability="consumable",
                idempotency_key=f"{marker}:seed-consumable",
                related_type="verification",
                related_id=marker,
                remark="seed points for netdisk unlock verification",
            )

            first_payload, first_unlocked = await NetdiskResourceService.unlock_resource(session, invitee, "r2")
            _assert_equal("first unlock created", first_unlocked, True)
            _assert_equal("first unlock cost", int(first_payload["unlock"]["points_delta"]), -5)
            _assert_equal("first unlock link visible", first_payload["unlock"]["link"], "https://pan.baidu.com/s/mock-yuexiang-r2")
            _assert_equal("invitee consumable after first unlock", int(first_payload["account"]["consumable_points"]), 45)
            _assert_true("first resource invite reward payload", first_payload["invite_reward"] is not None)
            _assert_equal("first resource reward points", int(first_payload["invite_reward"]["points_delta"]), 10)

            replay_payload, replay_unlocked = await NetdiskResourceService.unlock_resource(session, invitee, "r2")
            _assert_equal("replay unlock created", replay_unlocked, False)
            _assert_equal("replay unlock same ledger", replay_payload["unlock"]["ledger_id"], first_payload["unlock"]["ledger_id"])
            _assert_equal("replay consumable unchanged", int(replay_payload["account"]["consumable_points"]), 45)
            _assert_equal("replay invite reward skipped", replay_payload["invite_reward"], None)

            second_payload, second_unlocked = await NetdiskResourceService.unlock_resource(session, invitee, "r1")
            _assert_equal("second resource unlock created", second_unlocked, True)
            _assert_equal("second resource cost", int(second_payload["unlock"]["points_delta"]), -10)
            _assert_equal("second resource consumable", int(second_payload["account"]["consumable_points"]), 35)
            _assert_equal("first-resource reward not repeated", bool(second_payload["invite_reward"]["created"]), False)

            inviter_account_after, _ = await PointsAccountService.ensure_user_account(session, inviter.id)
            _assert_equal("inviter consumable after first resource reward", int(inviter_account_after.consumable_points), 15)

            share_sender = User(
                openid=f"{marker}-share-sender",
                nickname="Share Sender",
                avatar="",
                invite_code=f"{marker}s"[-10:],
            )
            share_friend = User(
                openid=f"{marker}-share-friend",
                nickname="Share Friend",
                avatar="",
                invite_code=f"{marker}f"[-10:],
            )
            session.add(share_sender)
            session.add(share_friend)
            await session.flush()

            token_payload = await NetdiskResourceService.prepare_share_unlock_token(session, share_sender, "r3")
            _assert_true("share token created", bool(token_payload["share_token"]))

            sender_payload, sender_unlocked = await NetdiskResourceService.share_unlock_resource(session, share_sender, "r3")
            _assert_equal("sender share unlock created", sender_unlocked, True)
            _assert_equal("sender share unlock is free", int(sender_payload["unlock"]["points_delta"]), 0)
            _assert_equal("sender consumable unchanged", int(sender_payload["account"]["consumable_points"]), 0)
            _assert_true("sender share token returned", bool(sender_payload["share_token"]))

            friend_payload, friend_unlocked = await NetdiskResourceService.claim_share_unlock(
                session,
                share_friend,
                "r3",
                token_payload["share_token"],
            )
            _assert_equal("friend share unlock created", friend_unlocked, True)
            _assert_equal("friend share unlock is free", int(friend_payload["unlock"]["points_delta"]), 0)
            _assert_equal("friend consumable unchanged", int(friend_payload["account"]["consumable_points"]), 0)
            _assert_true("friend link visible", bool(friend_payload["unlock"]["link"]))

            replay_friend_payload, replay_friend_unlocked = await NetdiskResourceService.claim_share_unlock(
                session,
                share_friend,
                "r3",
                token_payload["share_token"],
            )
            _assert_equal("friend share replay skipped", replay_friend_unlocked, False)
            _assert_equal(
                "friend share replay same ledger",
                replay_friend_payload["unlock"]["ledger_id"],
                friend_payload["unlock"]["ledger_id"],
            )

            poor_user = User(
                openid=f"{marker}-poor",
                nickname="Poor User",
                avatar="",
                invite_code=f"{marker}p"[-10:],
            )
            session.add(poor_user)
            await session.flush()
            try:
                await NetdiskResourceService.unlock_resource(session, poor_user, "r3")
            except ValueError as exc:
                _assert_true("insufficient points error", "insufficient consumable points" in str(exc))
            else:
                raise AssertionError("poor user unlock should fail")

            unlock_ledgers_result = await session.execute(
                select(PointsLedger).where(
                    PointsLedger.user_id == invitee.id,
                    PointsLedger.source == "netdisk",
                    PointsLedger.change_type == "resource_unlock",
                )
            )
            unlock_ledgers = list(unlock_ledgers_result.scalars().all())
            _assert_equal("netdisk unlock ledger count", len(unlock_ledgers), 2)

            print("Netdisk unlock verification passed")
            print("checks=deduct consumable points, unlock idempotency, first-resource invite reward, share free unlock, insufficient balance")
        finally:
            await session.rollback()


async def _assert_required_tables(session) -> None:
    connection = await session.connection()
    table_names = await connection.run_sync(lambda sync_conn: set(inspect(sync_conn).get_table_names()))
    missing = sorted(REQUIRED_TABLES - table_names)
    if missing:
        raise RuntimeError(
            "Missing required tables for netdisk unlock verification: "
            + ", ".join(missing)
            + ". Run the Stage 2 Alembic migrations against the intended database first."
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify netdisk resource unlock flow.")
    parser.add_argument("--execute", action="store_true", help="run verification against the configured database")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.execute:
        print("Dry run only. Re-run with --execute to verify against the configured database.")
        print("Checks: deduct consumable points, unlock idempotency, first-resource invite reward, share free unlock, insufficient balance.")
        return

    try:
        asyncio.run(verify())
    except RuntimeError as exc:
        print(f"Verification blocked: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
