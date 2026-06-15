"""Verify netdisk reports auto-confirm invalid resources at 2 distinct users.

Checks:
1. first distinct report only records the report and keeps resource active
2. duplicate report by the same user is blocked
3. second distinct report auto-confirms invalid, hides resource, and penalizes uploader
4. repeated reports after auto-confirm do not double-penalize

By default it only prints the plan. Pass --execute to run against the current
database inside a rollback transaction.
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
from models.netdisk_repair import NetdiskRepair  # noqa: E402
from models.netdisk_resource import NetdiskResource  # noqa: E402
from models.netdisk_risk_record import NetdiskRiskRecord  # noqa: E402
from models.netdisk_audit_log import NetdiskAuditLog  # noqa: E402
from models.netdisk_user_notification import NetdiskUserNotification  # noqa: E402
from models.netdisk_upload import NetdiskUpload  # noqa: E402
from models.points_ledger import PointsLedger  # noqa: E402
from models.user import User  # noqa: E402
from services.config_service import ConfigService  # noqa: E402
from services.netdisk_resource_service import NetdiskResourceService  # noqa: E402
from services.points_account_service import PointsAccountService  # noqa: E402

REQUIRED_TABLES = {
    "users",
    "user_accounts",
    "points_ledger",
    "netdisk_uploads",
    "netdisk_resources",
    "netdisk_repairs",
    "netdisk_risk_records",
    "netdisk_audit_logs",
    "netdisk_user_notifications",
    "user_quality_profiles",
    "system_configs",
}


def _assert_equal(label: str, actual, expected) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


async def verify() -> None:
    marker = f"auto-report-{uuid.uuid4().hex[:10]}"

    async with async_session_factory() as session:
        try:
            await _assert_required_tables(session)
            await ConfigService.set(
                session,
                "netdisk_audit_config",
                {
                    "upload_reward_points": 5,
                    "upload_approved_points": 2,
                    "upload_valid_7d_points": 3,
                    "repair_reward_points": 5,
                    "report_confirm_invalid_threshold": 2,
                    "invalid_penalty_multiplier": 1,
                    "auto_hide_on_report": True,
                },
            )

            uploader = User(openid=f"{marker}-uploader", nickname="Uploader", avatar="", invite_code=f"{marker}u"[-10:])
            reporter_a = User(openid=f"{marker}-report-a", nickname="Reporter A", avatar="", invite_code=f"{marker}a"[-10:])
            reporter_b = User(openid=f"{marker}-report-b", nickname="Reporter B", avatar="", invite_code=f"{marker}b"[-10:])
            reporter_c = User(openid=f"{marker}-report-c", nickname="Reporter C", avatar="", invite_code=f"{marker}c"[-10:])
            session.add(uploader)
            session.add(reporter_a)
            session.add(reporter_b)
            session.add(reporter_c)
            await session.flush()

            upload = NetdiskUpload(
                user_id=uploader.id,
                title=f"{marker} 失效测试资源",
                category="影视剧",
                pan="百度",
                link=f"https://pan.baidu.com/s/{marker}",
                status="approved",
                reward_points=5,
                reward_released_points=5,
                audit_note="verification seed approved upload",
                accepted_at=datetime.utcnow(),
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
                description="verification resource",
                link=upload.link,
                tags="[]",
                source_type="upload",
                source_ref=str(upload.id),
                normalized_title=upload.title.lower(),
                source_upload_id=str(upload.id),
                uploader_user_id=uploader.id,
                is_active=True,
            )
            session.add(resource)
            await session.flush()

            await PointsAccountService.add_points(
                session=session,
                user_id=uploader.id,
                points=5,
                source="netdisk",
                change_type="upload_reward_release",
                availability="consumable",
                idempotency_key=f"{marker}:seed-upload-reward",
                related_type="netdisk_upload",
                related_id=str(upload.id),
                remark="seed released upload reward",
            )

            first = await NetdiskResourceService.create_repair(
                session=session,
                user=reporter_a,
                resource_id=resource.id,
                mode="report",
                pan=resource.pan,
                link="",
                extract_code="",
                unzip_code="",
                note="链接失效，无法打开",
            )
            _assert_equal("first report status", first["repair"]["status"], "pending")
            db_resource = await session.get(NetdiskResource, resource.id)
            _assert_equal("resource active after one report", bool(db_resource.is_active), True)
            _assert_equal("report_count after one report", int(db_resource.report_count), 1)

            duplicate_blocked = False
            try:
                await NetdiskResourceService.create_repair(
                    session=session,
                    user=reporter_a,
                    resource_id=resource.id,
                    mode="report",
                    pan=resource.pan,
                    link="",
                    extract_code="",
                    unzip_code="",
                    note="重复投诉不应计数",
                )
            except ValueError as exc:
                duplicate_blocked = "already reported" in str(exc)
            _assert_equal("duplicate report blocked", duplicate_blocked, True)

            second = await NetdiskResourceService.create_repair(
                session=session,
                user=reporter_b,
                resource_id=resource.id,
                mode="report",
                pan=resource.pan,
                link="",
                extract_code="",
                unzip_code="",
                note="确认链接失效",
            )
            _assert_equal("second report auto status", second["repair"]["status"], "invalid_confirmed")
            _assert_equal("second report auto action", second["auto_action"]["action"], "resource_auto_confirm_invalid")
            _assert_equal("second report auto threshold", second["auto_action"]["threshold"], 2)

            db_resource = await session.get(NetdiskResource, resource.id)
            _assert_equal("resource inactive after two reports", bool(db_resource.is_active), False)
            _assert_equal("resource invalid_count", int(db_resource.invalid_count), 1)
            _assert_equal("resource distinct report_count", int(db_resource.report_count), 2)

            reports = (
                await session.execute(
                    select(NetdiskRepair).where(NetdiskRepair.resource_id == resource.id, NetdiskRepair.mode == "report")
                )
            ).scalars().all()
            _assert_equal("report row count", len(reports), 2)
            _assert_equal("all reports confirmed", {item.status for item in reports}, {"invalid_confirmed"})

            db_upload = await session.get(NetdiskUpload, upload.id)
            _assert_equal("upload invalid confirmed", db_upload.status, "invalid_confirmed")

            penalty_ledgers = (
                await session.execute(
                    select(PointsLedger).where(
                        PointsLedger.user_id == uploader.id,
                        PointsLedger.change_type == "invalid_penalty",
                        PointsLedger.related_type == "netdisk_upload",
                        PointsLedger.related_id == str(upload.id),
                    )
                )
            ).scalars().all()
            _assert_equal("penalty ledger count", len(penalty_ledgers), 1)
            _assert_equal("penalty delta", int(penalty_ledgers[0].points_delta), -5)

            risk_records = (
                await session.execute(
                    select(NetdiskRiskRecord).where(
                        NetdiskRiskRecord.related_type == "netdisk_upload",
                        NetdiskRiskRecord.related_id == str(upload.id),
                    )
                )
            ).scalars().all()
            _assert_equal("risk record count", len(risk_records), 1)
            _assert_equal("risk points due", int(risk_records[0].points_due), 5)

            notifications = (
                await session.execute(
                    select(NetdiskUserNotification).where(
                        NetdiskUserNotification.user_id == uploader.id,
                        NetdiskUserNotification.notice_type == "netdisk_risk_pending",
                        NetdiskUserNotification.related_type == "netdisk_upload",
                        NetdiskUserNotification.related_id == str(upload.id),
                    )
                )
            ).scalars().all()
            _assert_equal("uploader notification count", len(notifications), 1)
            if "问题反馈" not in notifications[0].content or "申诉" not in notifications[0].content or "扣罚 5 积分" not in notifications[0].content:
                raise AssertionError(f"notification content missing appeal path or penalty detail: {notifications[0].content}")

            audit_logs = (
                await session.execute(
                    select(NetdiskAuditLog).where(
                        NetdiskAuditLog.action == "resource_auto_confirm_invalid",
                        NetdiskAuditLog.target_type == "netdisk_resource",
                        NetdiskAuditLog.target_id == resource.id,
                        NetdiskAuditLog.admin_name == "system",
                    )
                )
            ).scalars().all()
            _assert_equal("system audit log count", len(audit_logs), 1)

            await NetdiskResourceService.confirm_resource_invalid(
                session=session,
                resource_id=resource.id,
                note="重复确认失效不应重复扣罚",
            )
            replay_penalties = (
                await session.execute(
                    select(PointsLedger).where(
                        PointsLedger.user_id == uploader.id,
                        PointsLedger.change_type == "invalid_penalty",
                        PointsLedger.related_type == "netdisk_upload",
                        PointsLedger.related_id == str(upload.id),
                    )
                )
            ).scalars().all()
            _assert_equal("no duplicate penalty after repeated confirm", len(replay_penalties), 1)

            print("Netdisk auto report invalid verification passed")
            print("checks=distinct reporters threshold, duplicate block, auto hide, penalty ledger, risk record, no double penalty")
        finally:
            await session.rollback()


async def _assert_required_tables(session) -> None:
    connection = await session.connection()
    table_names = await connection.run_sync(lambda sync_conn: set(inspect(sync_conn).get_table_names()))
    missing = sorted(REQUIRED_TABLES - table_names)
    if missing:
        raise RuntimeError(
            "Missing required tables for netdisk auto report verification: "
            + ", ".join(missing)
            + ". Run Alembic migrations against the intended database first."
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify netdisk auto report invalid flow.")
    parser.add_argument("--execute", action="store_true", help="run verification against the configured database")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.execute:
        print("Dry run only. Re-run with --execute to verify against the configured database.")
        print("Checks: distinct reporters threshold, duplicate block, auto hide, penalty ledger, risk record, no double penalty.")
        return

    try:
        asyncio.run(verify())
    except RuntimeError as exc:
        print(f"Verification blocked: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
