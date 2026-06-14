"""Helpers for Stage 2 points summary views."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict

from sqlalchemy import and_, func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from models.game_user_settlement import GameUserSettlement
from models.points_ledger import PointsLedger
from core.timezone import bj_day_bounds_utc, today_bj

DAILY_EARN_CAP = 60
DAILY_EARN_EXCLUDED_SOURCES = {"signup", "recharge", "vip", "withdraw", "dev", "admin"}


class PointsSummaryService:
    """Build reusable summary fields for home and mine views."""

    @staticmethod
    async def build_summary(session: AsyncSession, user_id, *, today: date | None = None) -> Dict[str, Any]:
        current_day = today or today_bj()
        yesterday = current_day - timedelta(days=1)
        today_start, today_end = bj_day_bounds_utc(current_day)

        today_estimated_points = await _sum_ledger_points(
            session,
            user_id,
            start=today_start,
            end=today_end,
            source="game",
            availability="consumable",
        )
        today_earned_points = await _sum_ledger_points(
            session,
            user_id,
            start=today_start,
            end=today_end,
            availability="consumable",
            exclude_sources=DAILY_EARN_EXCLUDED_SOURCES,
            positive_only=True,
        )
        yesterday_settled_points = await _sum_positive_points(
            session=session,
            user_id=user_id,
            settlement_day=yesterday,
        )

        return {
            "today_estimated_points": int(today_estimated_points),
            "today_earned_points": min(max(int(today_earned_points), 0), DAILY_EARN_CAP),
            "today_earn_cap": DAILY_EARN_CAP,
            "yesterday_settled_points": int(yesterday_settled_points),
        }


async def _sum_positive_points(
    session: AsyncSession,
    user_id,
    *,
    settlement_day: date,
) -> int:
    settlement_stmt = select(func.coalesce(func.sum(GameUserSettlement.settled_points), 0)).where(
        GameUserSettlement.user_id == user_id,
        GameUserSettlement.settlement_date == settlement_day,
    )
    settlement_result = await session.execute(settlement_stmt)
    return int(settlement_result.scalar_one() or 0)


async def _sum_ledger_points(
    session: AsyncSession,
    user_id,
    *,
    start: datetime,
    end: datetime,
    availability: str,
    source: str | None = None,
    exclude_source: str | None = None,
    exclude_sources: set[str] | None = None,
    positive_only: bool = False,
) -> int:
    filters = [
        PointsLedger.user_id == user_id,
        PointsLedger.availability == availability,
        PointsLedger.created_at >= start,
        PointsLedger.created_at < end,
    ]
    if positive_only:
        filters.append(PointsLedger.points_delta > 0)
    if source:
        filters.append(PointsLedger.source == source)
    if exclude_source:
        filters.append(PointsLedger.source != exclude_source)
    if exclude_sources:
        filters.append(PointsLedger.source.notin_(exclude_sources))

    stmt = select(func.coalesce(func.sum(PointsLedger.points_delta), 0)).where(and_(*filters))
    result = await session.execute(stmt)
    return int(result.scalar_one() or 0)
