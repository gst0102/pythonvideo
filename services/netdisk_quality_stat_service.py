"""Netdisk quality daily statistic refresh service."""

import os
from datetime import datetime, timedelta

from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from models.netdisk_audit_log import NetdiskAuditLog
from models.netdisk_quality_daily_stat import NetdiskQualityDailyStat
from models.netdisk_repair import NetdiskRepair
from models.netdisk_resource import NetdiskResource as NetdiskResourceModel
from models.points_ledger import PointsLedger

QUALITY_STATS_ENABLED = os.getenv("NETDISK_QUALITY_STATS_ENABLED", "true").lower() == "true"


async def refresh_netdisk_quality_daily_stats(session: AsyncSession, days: int = 7) -> int:
    resources = (await session.execute(select(NetdiskResourceModel))).scalars().all()
    today = datetime.utcnow().date()
    rows = 0
    for resource in resources:
        for offset in range(max(1, days)):
            day = today - timedelta(days=offset)
            stat = await build_resource_quality_day_stat(session, resource.id, day, resource)
            existing = (
                await session.execute(
                    select(NetdiskQualityDailyStat).where(
                        NetdiskQualityDailyStat.resource_id == resource.id,
                        NetdiskQualityDailyStat.stat_date == day,
                    )
                )
            ).scalar_one_or_none()
            if existing:
                existing.title = stat["title"]
                existing.category = stat["category"]
                existing.pan = stat["pan"]
                existing.is_active = stat["is_active"]
                existing.reports = stat["reports"]
                existing.restores = stat["restores"]
                existing.unlocks = stat["unlocks"]
                existing.unlock_users = stat["unlock_users"]
                existing.score = stat["score"]
                existing.updated_at = datetime.utcnow()
            else:
                session.add(
                    NetdiskQualityDailyStat(
                        resource_id=resource.id,
                        stat_date=day,
                        title=stat["title"],
                        category=stat["category"],
                        pan=stat["pan"],
                        is_active=stat["is_active"],
                        reports=stat["reports"],
                        restores=stat["restores"],
                        unlocks=stat["unlocks"],
                        unlock_users=stat["unlock_users"],
                        score=stat["score"],
                    )
                )
            rows += 1
    await session.flush()
    return rows


async def build_resource_quality_day_stat(
    session: AsyncSession,
    resource_id: str,
    day,
    resource: NetdiskResourceModel | None = None,
) -> dict:
    resource = resource or await session.get(NetdiskResourceModel, resource_id)
    day_start = datetime.combine(day, datetime.min.time())
    day_end = day_start + timedelta(days=1)
    reports = (
        await session.execute(
            select(func.count()).select_from(NetdiskRepair).where(
                NetdiskRepair.resource_id == resource_id,
                NetdiskRepair.mode == "report",
                NetdiskRepair.created_at >= day_start,
                NetdiskRepair.created_at < day_end,
            )
        )
    ).scalar() or 0
    restores = (
        await session.execute(
            select(func.count()).select_from(NetdiskAuditLog).where(
                NetdiskAuditLog.target_type == "netdisk_resource",
                NetdiskAuditLog.target_id == resource_id,
                NetdiskAuditLog.action == "resource_restore",
                NetdiskAuditLog.created_at >= day_start,
                NetdiskAuditLog.created_at < day_end,
            )
        )
    ).scalar() or 0
    unlocks = (
        await session.execute(
            select(func.count(), func.count(func.distinct(PointsLedger.user_id))).where(
                PointsLedger.source == "netdisk",
                PointsLedger.change_type == "resource_unlock",
                PointsLedger.related_type == "netdisk_resource",
                PointsLedger.related_id == resource_id,
                PointsLedger.created_at >= day_start,
                PointsLedger.created_at < day_end,
            )
        )
    ).one()
    report_count = int(reports or 0)
    restore_count = int(restores or 0)
    unlock_count = int(unlocks[0] or 0)
    return {
        "date": day.isoformat(),
        "resource_id": resource_id,
        "title": resource.title if resource else "",
        "category": resource.category if resource else "",
        "pan": resource.pan if resource else "",
        "is_active": bool(resource.is_active) if resource else False,
        "reports": report_count,
        "restores": restore_count,
        "unlocks": unlock_count,
        "unlock_users": int(unlocks[1] or 0),
        "score": report_count * 3 + restore_count * 2 + unlock_count,
    }
