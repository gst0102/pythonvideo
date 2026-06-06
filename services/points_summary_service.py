"""Helpers for Stage 2 points summary views."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any, Dict

from sqlalchemy import and_, func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from models.points_ledger import PointsLedger


class PointsSummaryService:
    """Build reusable summary fields for home and mine views."""

    @staticmethod
    async def build_summary(session: AsyncSession, user_id, *, today: date | None = None) -> Dict[str, Any]:
        current_day = today or datetime.utcnow().date()
        yesterday = current_day - timedelta(days=1)

        today_estimated_points = await _sum_positive_points(
            session,
            user_id,
            start=_start_of_day(current_day),
            end=_end_of_day(current_day),
            source="game",
            availability="consumable",
        )
        yesterday_settled_points = await _sum_positive_points(
            session,
            user_id,
            start=_start_of_day(yesterday),
            end=_end_of_day(yesterday),
            availability="withdrawable",
            exclude_source="withdraw",
        )

        return {
            "today_estimated_points": int(today_estimated_points),
            "yesterday_settled_points": int(yesterday_settled_points),
        }


def _start_of_day(day: date) -> datetime:
    return datetime.combine(day, time.min)


def _end_of_day(day: date) -> datetime:
    return datetime.combine(day, time.max)


async def _sum_positive_points(
    session: AsyncSession,
    user_id,
    *,
    start: datetime,
    end: datetime,
    availability: str,
    source: str | None = None,
    exclude_source: str | None = None,
) -> int:
    filters = [
        PointsLedger.user_id == user_id,
        PointsLedger.availability == availability,
        PointsLedger.points_delta > 0,
        PointsLedger.created_at >= start,
        PointsLedger.created_at <= end,
    ]
    if source:
        filters.append(PointsLedger.source == source)
    if exclude_source:
        filters.append(PointsLedger.source != exclude_source)

    stmt = select(func.coalesce(func.sum(PointsLedger.points_delta), 0)).where(and_(*filters))
    result = await session.execute(stmt)
    return int(result.scalar_one() or 0)
