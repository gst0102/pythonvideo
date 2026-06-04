"""Stage 2 task overview aggregation service."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from sqlalchemy import desc
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from models.order import Order
from models.user import User
from services.checkin_service import CheckinService
from services.game_task_service import GameTaskService


class TaskOverviewService:
    """Aggregate task status for home and game entry views."""

    @staticmethod
    async def get_overview(session: AsyncSession, user: User) -> Dict[str, Any]:
        checkin_status = await CheckinService.get_status(session, user)
        game_status = await GameTaskService.get_status(session, user)
        member_summary = await _build_member_summary(session, user)

        return {
            "today": game_status["today"],
            "user": {
                "id": str(user.id),
                "nickname": user.nickname,
                "avatar": user.avatar,
                "invite_code": user.invite_code,
            },
            "member": member_summary,
            "account": checkin_status["account"],
            "today_points": int(game_status["today_points"]),
            "checkin": checkin_status,
            "game_task": game_status,
        }


async def _build_member_summary(session: AsyncSession, user: User) -> Dict[str, Any]:
    plan_code = "none"
    if user.is_vip:
        plan_code = await _resolve_latest_plan_code(session, user.id)

    days_remaining = 0
    if user.vip_expire_at:
        now = datetime.utcnow()
        seconds = (user.vip_expire_at - now).total_seconds()
        days_remaining = max(int((seconds + 86399) // 86400), 0)

    return {
        "is_vip": bool(user.is_vip),
        "plan_code": plan_code,
        "vip_expire_at": user.vip_expire_at,
        "days_remaining": days_remaining,
    }


async def _resolve_latest_plan_code(session: AsyncSession, user_id) -> str:
    stmt = (
        select(Order)
        .where(Order.user_id == user_id, Order.status == "paid")
        .order_by(desc(Order.paid_at), desc(Order.created_at))
    )
    result = await session.execute(stmt)
    order = result.scalars().first()
    if not order or not order.period:
        return "month"

    period = str(order.period).strip().lower()
    if period not in {"month", "quarter", "year"}:
        return "month"
    return period
