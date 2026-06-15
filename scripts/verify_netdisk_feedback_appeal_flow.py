"""Verify netdisk invalid-penalty appeal flow.

Checks:
1. feedback appeal can match a penalty by resource id
2. approved appeal returns deducted points
3. related credit adjustment is restored
4. pending risk record is waived
5. repeated approval is idempotent and does not return points twice

By default this script only prints the plan. Pass --execute to run against the
configured database inside a rollback transaction.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import inspect
from sqlmodel import select

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from models.base import async_session_factory  # noqa: E402
from models.netdisk_feedback import NetdiskFeedback  # noqa: E402
from models.netdisk_resource import NetdiskResource  # noqa: E402
from models.netdisk_risk_record import NetdiskRiskRecord  # noqa: E402
from models.netdisk_upload import NetdiskUpload  # noqa: E402
from models.netdisk_user_notification import NetdiskUserNotification  # noqa: E402
from models.points_ledger import PointsLedger  # noqa: E402
from models.user import User  # noqa: E402
from services.netdisk_resource_service import NetdiskResourceService, _adjust_quality_profile  # noqa: E402
from services.points_account_service import PointsAccountService  # noqa: E402

REQUIRED_TABLES = {
    "users",
    "user_accounts",
    "points_ledger",
    "netdisk_uploads",
    "netdisk_resources",
    "netdisk_feedbacks",
    "netdisk_risk_records",
    "netdisk_user_notifications",
    "user_quality_profiles",
}


def _assert_equal(label: str, actual, expected) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


async def verify() -> None:
    marker = f"appeal-{uuid.uuid4().hex[:10]}"

    async with async_session_factory() as session:
        try:
            await _assert_required_tables(session)

            user = User(openid=f"{marker}-user", nickname="Appeal User", avatar="", invite_code=marker[-10:])
            session.add(user)
            await session.flush()

            upload = NetdiskUpload(
                user_id=user.id,
                title=f"{marker} 申诉资源",
                category="影视剧",
                pan="百度",
                link=f"https://pan.baidu.com/s/{marker}",
                status="invalid_confirmed",
                reward_points=5,
                reward_released_points=5,
                accepted_at=datetime.utcnow(),
                audit_note="seed invalid upload",
            )
            session.add(upload)
            await session.flush()

            resource = NetdiskResource(
                id=f"upload-{str(upload.id).replace('-', '')[:24]}",
                title=upload.title,
                category=upload.category,
                pan=upload.pan,
                level="normal",
                cost_points=5,
                downloads=0,
                favorites=0,
                description="appeal verification resource",
                link=upload.link,
                tags="[]",
                source_type="upload",
                source_ref=str(upload.id),
                normalized_title=upload.title.lower(),
                source_upload_id=str(upload.id),
                uploader_user_id=user.id,
                is_active=False,
                invalid_count=1,
            )
            session.add(resource)
            await session.flush()

            await PointsAccountService.add_points(
                session=session,
                user_id=user.id,
                points=5,
                source="netdisk",
                change_type="upload_reward_release",
                availability="consumable",
                idempotency_key=f"{marker}:seed-upload-reward",
                related_type="netdisk_upload",
                related_id=str(upload.id),
                remark="seed reward",
            )
            penalty_ledger, account_after_penalty, _ = await PointsAccountService.clawback_points(
                session=session,
                user_id=user.id,
                points=5,
                availability="consumable",
                idempotency_key=f"{marker}:invalid-penalty",
                related_type="netdisk_upload",
                related_id=str(upload.id),
                source="netdisk_invalid",
                change_type="invalid_penalty",
                remark="seed invalid penalty",
            )
            _assert_equal("points after penalty", int(account_after_penalty.consumable_points), 0)

            profile_after_penalty = await _adjust_quality_profile(
                session,
                user.id,
                credit_delta=-5,
                contribution_delta=-2,
                short_invalid_delta=1,
                idempotency_key=f"{marker}:quality-penalty",
                related_type="netdisk_upload",
                related_id=str(upload.id),
                remark="seed invalid quality penalty",
            )
            _assert_equal("credit after penalty", int(profile_after_penalty.credit_score), 95)
            _assert_equal("short invalid after penalty", int(profile_after_penalty.short_invalid_count), 1)

            risk = NetdiskRiskRecord(
                user_id=user.id,
                related_type="netdisk_upload",
                related_id=str(upload.id),
                reason="invalid_penalty",
                points_due=5,
                points_collected=5,
                status="open",
                note="seed risk",
                idempotency_key=f"{marker}:risk",
            )
            session.add(risk)
            await session.flush()

            feedback_payload = await NetdiskResourceService.create_feedback(
                session=session,
                user=user,
                feedback_type="resource",
                content=f"这个资源被误判失效，请复核资源ID：{resource.id}",
                contact="appeal-test",
            )
            feedback_id = feedback_payload["feedback"]["id"]

            admin_payload = await NetdiskResourceService.list_admin_feedbacks(
                session=session,
                feedback_id=feedback_id,
                page=1,
                page_size=20,
            )
            admin_feedback = admin_payload["feedbacks"][0]
            _assert_equal("admin appeal context resource id", admin_feedback["appeal_context"]["resource_id"], resource.id)
            _assert_equal("admin appeal preview matched", admin_feedback["appeal_preview"]["match_status"], "matched")
            _assert_equal("admin appeal preview points", int(admin_feedback["appeal_preview"]["return_points"]), 5)

            approved = await NetdiskResourceService.approve_feedback_appeal(
                session=session,
                feedback_id=feedback_id,
                note="申诉通过，恢复扣罚。",
            )
            appeal = approved["appeal"]
            _assert_equal("appeal returned points", int(appeal["returned_points"]), 5)
            _assert_equal("appeal matched penalty", appeal["penalty_ledger_id"], str(penalty_ledger.id))
            _assert_equal("risk waived count", int(appeal["risk_records_waived"]), 1)

            account_after_appeal, _ = await PointsAccountService.ensure_user_account(session, user.id)
            _assert_equal("points after appeal", int(account_after_appeal.consumable_points), 5)

            db_risk = await session.get(NetdiskRiskRecord, risk.id)
            _assert_equal("risk status after appeal", db_risk.status, "waived")

            return_ledgers = (
                await session.execute(
                    select(PointsLedger).where(
                        PointsLedger.user_id == user.id,
                        PointsLedger.change_type == "invalid_penalty_appeal_return",
                        PointsLedger.related_type == "netdisk_upload",
                        PointsLedger.related_id == str(upload.id),
                    )
                )
            ).scalars().all()
            _assert_equal("return ledger count", len(return_ledgers), 1)
            _assert_equal("return ledger delta", int(return_ledgers[0].points_delta), 5)

            quality_restore_ledgers = (
                await session.execute(
                    select(PointsLedger).where(
                        PointsLedger.user_id == user.id,
                        PointsLedger.source == "netdisk_quality",
                        PointsLedger.change_type == "credit_adjustment",
                        PointsLedger.related_type == "netdisk_upload",
                        PointsLedger.related_id == str(upload.id),
                    )
                )
            ).scalars().all()
            _assert_equal("quality ledger count", len(quality_restore_ledgers), 2)
            restored_profile_credit = int(appeal["credit_score"])
            _assert_equal("credit after appeal", restored_profile_credit, 100)

            notifications = (
                await session.execute(
                    select(NetdiskUserNotification).where(
                        NetdiskUserNotification.user_id == user.id,
                        NetdiskUserNotification.notice_type == "netdisk_appeal_approved",
                        NetdiskUserNotification.related_id == feedback_id,
                    )
                )
            ).scalars().all()
            _assert_equal("appeal notification count", len(notifications), 1)

            replay = await NetdiskResourceService.approve_feedback_appeal(
                session=session,
                feedback_id=feedback_id,
                note="重复通过不应重复返还。",
            )
            _assert_equal("replay returned points", int(replay["appeal"]["returned_points"]), 0)
            replay_account, _ = await PointsAccountService.ensure_user_account(session, user.id)
            _assert_equal("replay points unchanged", int(replay_account.consumable_points), 5)

            replay_ledgers = (
                await session.execute(
                    select(PointsLedger).where(
                        PointsLedger.user_id == user.id,
                        PointsLedger.change_type == "invalid_penalty_appeal_return",
                        PointsLedger.related_id == str(upload.id),
                    )
                )
            ).scalars().all()
            _assert_equal("replay return ledger count unchanged", len(replay_ledgers), 1)

            db_feedback = await session.get(NetdiskFeedback, uuid.UUID(feedback_id))
            _assert_equal("feedback resolved", db_feedback.status, "resolved")
            _assert_equal("feedback return points", int(db_feedback.reward_points), 5)

            print("Netdisk feedback appeal verification passed")
            print("checks=admin preview, match by resource id, points return, credit restore, risk waive, idempotent replay")
        finally:
            await session.rollback()


async def _assert_required_tables(session) -> None:
    connection = await session.connection()
    table_names = await connection.run_sync(lambda sync_conn: set(inspect(sync_conn).get_table_names()))
    missing = sorted(REQUIRED_TABLES - table_names)
    if missing:
        raise RuntimeError(
            "Missing required tables for netdisk feedback appeal verification: "
            + ", ".join(missing)
            + ". Run Alembic migrations against the intended database first."
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify netdisk feedback appeal flow.")
    parser.add_argument("--execute", action="store_true", help="run verification against the configured database")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.execute:
        print("Dry run only. Re-run with --execute to verify against the configured database.")
        print("Checks: admin preview, match penalty by resource id, return points, restore credit, waive risk, idempotent replay.")
        return

    try:
        asyncio.run(verify())
    except Exception as exc:
        print(f"Netdisk feedback appeal verification failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
