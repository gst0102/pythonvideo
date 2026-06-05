"""Verify Stage 2 game rewarded-ad rotation and idempotency flow.

This script validates three critical behaviors for the Stage 2 mini-game ad
bonus chain:
1. a saturated ad unit is skipped and another slot is selected
2. when every ad unit is saturated, the API reports no available slot
3. the same ad_event_id or the same round cannot receive duplicate bonus

By default it only prints the plan. Pass --execute to run against the current
database inside a rollback transaction.
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

from models.ad_event import AdEventRecord  # noqa: E402
from models.base import async_session_factory  # noqa: E402
from models.points_ledger import PointsLedger  # noqa: E402
from models.user import User  # noqa: E402
from services.ad_analytics_service import now_keys  # noqa: E402
from services.config_service import ConfigService  # noqa: E402
from services.game_ad_service import GameAdService  # noqa: E402
from services.game_task_service import GameTaskService  # noqa: E402


REQUIRED_TABLES = {
    "ad_event_records",
    "daily_task_stats",
    "game_rounds",
    "points_ledger",
    "system_configs",
    "user_accounts",
    "users",
}

TEST_CONFIG = {
    "scene": "game_bonus",
    "instances": [
        {
            "ad_code": "reward_game_a",
            "ad_unit_id": "adunit-stage2-test-a",
            "ad_type": "rewarded_video",
            "status": "active",
            "priority": 100,
            "weight": 100,
            "daily_user_show_limit": 1,
            "daily_user_complete_limit": 1,
        },
        {
            "ad_code": "reward_game_b",
            "ad_unit_id": "adunit-stage2-test-b",
            "ad_type": "rewarded_video",
            "status": "active",
            "priority": 100,
            "weight": 100,
            "daily_user_show_limit": 1,
            "daily_user_complete_limit": 1,
        },
        {
            "ad_code": "reward_game_c",
            "ad_unit_id": "adunit-stage2-test-c",
            "ad_type": "rewarded_video",
            "status": "active",
            "priority": 100,
            "weight": 100,
            "daily_user_show_limit": 1,
            "daily_user_complete_limit": 1,
        },
    ],
}


def _assert_true(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)


def _assert_equal(label: str, actual, expected) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


async def verify() -> None:
    marker = f"stage2-game-ad-{uuid.uuid4().hex[:12]}"

    async with async_session_factory() as session:
        try:
            await _assert_required_tables(session)
            await ConfigService.set(session, "stage2_game_bonus_ad_config", TEST_CONFIG)

            user = User(
                openid=marker,
                nickname="Stage2 Game Ad Verify",
                avatar="",
                invite_code=marker[-10:],
            )
            session.add(user)
            await session.flush()

            await _verify_slot_rotation(session, user, marker)
            await _verify_ad_bonus_idempotency(session, user, marker)

            print("Game ad flow verification passed")
            print("checks=rotation, exhaustion, ad_event_id idempotency, round idempotency")
        finally:
            await session.rollback()


async def _verify_slot_rotation(session, user: User, marker: str) -> None:
    round_one = f"{marker}-slot-1"
    round_two = f"{marker}-slot-2"
    round_three = f"{marker}-slot-3"

    await GameTaskService.complete_round(session, user, game_code="rps", round_id=round_one, result="win")
    slot_one = await GameAdService.select_available_slot(session, user, round_id=round_one)
    _assert_true("first slot should be available", bool(slot_one["available"]))

    first_ad_unit = str(slot_one["ad_unit_id"])
    await _consume_limit(session, user, first_ad_unit, event_id=f"{marker}-limit-a")

    await GameTaskService.complete_round(session, user, game_code="rps", round_id=round_two, result="draw")
    slot_two = await GameAdService.select_available_slot(session, user, round_id=round_two)
    _assert_true("second slot should be available", bool(slot_two["available"]))
    _assert_true(
        "saturated ad unit should not be returned again",
        str(slot_two["ad_unit_id"]) != first_ad_unit,
    )

    for instance in TEST_CONFIG["instances"]:
        ad_unit_id = str(instance["ad_unit_id"])
        if ad_unit_id == first_ad_unit or ad_unit_id == str(slot_two["ad_unit_id"]):
            continue
        await _consume_limit(session, user, ad_unit_id, event_id=f"{marker}-{ad_unit_id}")

    await _consume_limit(session, user, str(slot_two["ad_unit_id"]), event_id=f"{marker}-limit-b")

    await GameTaskService.complete_round(session, user, game_code="rps", round_id=round_three, result="lose")
    slot_three = await GameAdService.select_available_slot(session, user, round_id=round_three)
    _assert_equal("all saturated available", bool(slot_three["available"]), False)
    _assert_true(
        "all saturated message should be returned",
        "used" in str(slot_three.get("message", "")).lower() or bool(slot_three.get("message")),
    )


async def _verify_ad_bonus_idempotency(session, user: User, marker: str) -> None:
    round_id = f"{marker}-bonus-1"
    await GameTaskService.complete_round(session, user, game_code="rps", round_id=round_id, result="win")
    slot = await GameAdService.select_available_slot(session, user, round_id=round_id)
    _assert_true("bonus slot should be available", bool(slot["available"]))

    await _record_complete_event(
        session,
        user,
        event_id=str(slot["ad_event_id"]),
        ad_unit_id=str(slot["ad_unit_id"]),
    )

    first_payload, first_rewarded = await GameTaskService.claim_round_ad_bonus(
        session,
        user,
        round_id=round_id,
        ad_event_id=str(slot["ad_event_id"]),
    )
    _assert_equal("first bonus rewarded", first_rewarded, True)
    first_bonus = int(first_payload["points_added"])

    second_payload, second_rewarded = await GameTaskService.claim_round_ad_bonus(
        session,
        user,
        round_id=round_id,
        ad_event_id=str(slot["ad_event_id"]),
    )
    _assert_equal("same ad_event_id rewarded once", second_rewarded, False)
    _assert_equal("same ad_event_id bonus points", int(second_payload["points_added"]), 0)

    next_slot = await GameAdService.select_available_slot(session, user, round_id=round_id)
    await _record_complete_event(
        session,
        user,
        event_id=str(next_slot["ad_event_id"]),
        ad_unit_id=str(next_slot["ad_unit_id"]),
    )
    third_payload, third_rewarded = await GameTaskService.claim_round_ad_bonus(
        session,
        user,
        round_id=round_id,
        ad_event_id=str(next_slot["ad_event_id"]),
    )
    _assert_equal("same round should not reward twice", third_rewarded, False)
    _assert_equal("same round second bonus points", int(third_payload["points_added"]), 0)

    reward_rows = await session.execute(
        select(AdEventRecord).where(
            AdEventRecord.user_id == user.id,
            AdEventRecord.event_type == "reward",
        )
    )
    reward_events = list(reward_rows.scalars().all())
    _assert_equal("reward event count", len(reward_events), 1)

    ledger_rows = await session.execute(
        select(PointsLedger).where(
            PointsLedger.user_id == user.id,
            PointsLedger.change_type == "ad_bonus",
        )
    )
    ledgers = list(ledger_rows.scalars().all())
    _assert_equal("ad bonus ledger count", len(ledgers), 1)
    _assert_equal("ad bonus ledger points", int(ledgers[0].points_delta), first_bonus)


async def _consume_limit(session, user: User, ad_unit_id: str, *, event_id: str) -> None:
    await _record_event(session, user, event_id=event_id, ad_unit_id=ad_unit_id, event_type="show")
    await _record_event(
        session,
        user,
        event_id=event_id,
        ad_unit_id=ad_unit_id,
        event_type="complete",
        is_completed=True,
    )


async def _record_complete_event(session, user: User, *, event_id: str, ad_unit_id: str) -> None:
    await _record_event(session, user, event_id=event_id, ad_unit_id=ad_unit_id, event_type="show")
    await _record_event(
        session,
        user,
        event_id=event_id,
        ad_unit_id=ad_unit_id,
        event_type="complete",
        is_completed=True,
    )


async def _record_event(
    session,
    user: User,
    *,
    event_id: str,
    ad_unit_id: str,
    event_type: str,
    is_completed: bool = False,
) -> None:
    date_key, week_key, month_key = now_keys()
    session.add(
        AdEventRecord(
            event_id=event_id,
            user_id=user.id,
            openid=user.openid,
            module="game",
            section="bonus",
            scene="game_bonus",
            ad_unit_id=ad_unit_id,
            event_type=event_type,
            is_completed=is_completed,
            reward_points=0,
            reward_amount=0,
            date_key=date_key,
            week_key=week_key,
            month_key=month_key,
            created_at=datetime.now(timezone.utc),
        )
    )
    await session.flush()


async def _assert_required_tables(session) -> None:
    connection = await session.connection()
    table_names = await connection.run_sync(lambda sync_conn: set(inspect(sync_conn).get_table_names()))
    missing = sorted(REQUIRED_TABLES - table_names)
    if missing:
        raise RuntimeError(
            "Missing required tables for Stage 2 game ad verification: "
            + ", ".join(missing)
            + ". Run the Stage 2 Alembic migrations against the intended database first."
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify Stage 2 game ad rotation and idempotency.")
    parser.add_argument("--execute", action="store_true", help="run verification against the configured database")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.execute:
        print("Dry run only. Re-run with --execute to verify against the configured database.")
        print("Checks: slot rotation, all-slot exhaustion, ad_event_id idempotency, round idempotency.")
        return

    try:
        asyncio.run(verify())
    except RuntimeError as exc:
        print(f"Verification blocked: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
