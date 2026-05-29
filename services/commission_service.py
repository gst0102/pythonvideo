"""
佣金服务 — commission_service

MVC 架构中的 Service 层，处理分销佣金记录查询。

说明:
  佣金实际计算和发放由 payment_service._calculate_commission() 处理
  本服务仅负责查询展示
"""

import logging
from typing import List, Tuple
from uuid import UUID

from sqlmodel import select, func
from sqlmodel.ext.asyncio.session import AsyncSession

from models.user import User
from models.commission import CommissionRecord

logger = logging.getLogger(__name__)


class CommissionService:
    """佣金查询服务"""

    @staticmethod
    async def get_records(
        session: AsyncSession,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[dict], int]:
        """获取用户的佣金记录（带来源用户信息）"""
        # 总数
        count_stmt = (
            select(func.count())
            .select_from(CommissionRecord)
            .where(CommissionRecord.user_id == user_id)
        )
        result = await session.execute(count_stmt)
        total = result.scalar() or 0

        # 列表
        list_stmt = (
            select(CommissionRecord)
            .where(CommissionRecord.user_id == user_id)
            .order_by(CommissionRecord.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await session.execute(list_stmt)
        records = result.scalars().all()

        # 组装带用户信息的响应
        enriched = []
        for r in records:
            from_user = await session.get(User, r.from_user_id)
            enriched.append({
                "id": str(r.id),
                "from_user_nickname": from_user.nickname if from_user else "已注销",
                "from_user_avatar": from_user.avatar if from_user else "",
                "order_amount": float(r.order_amount),
                "commission_rate": f"{float(r.commission_rate)}%",
                "commission_amount": float(r.commission_amount),
                "level": r.level,
                "type": r.type,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            })

        return enriched, total

    @staticmethod
    async def get_invite_stats(session: AsyncSession, user_id: UUID) -> dict:
        """获取用户的邀请统计"""
        user = await session.get(User, user_id)
        if not user:
            return {}

        return {
            "invite_code": user.invite_code,
            "direct_count": user.invite_count,
            "indirect_count": user.indirect_count,
            "team_count": user.team_count,
            "total_income": float(user.total_income),
            "balance": float(user.balance),
            "total_withdrawn": float(user.total_withdrawn),
            "frozen_balance": float(user.frozen_balance),
        }

    @staticmethod
    async def get_invitees(
        session: AsyncSession,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[dict], int]:
        """获取用户直接邀请的人列表"""
        # 总数
        count_stmt = (
            select(func.count())
            .select_from(User)
            .where(User.parent_id == user_id)
        )
        result = await session.execute(count_stmt)
        total = result.scalar() or 0

        # 列表
        list_stmt = (
            select(User)
            .where(User.parent_id == user_id)
            .order_by(User.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await session.execute(list_stmt)
        invitees = result.scalars().all()

        enriched = [{
            "nickname": u.nickname,
            "avatar": u.avatar,
            "is_vip": u.is_vip,
            "joined_at": u.created_at.isoformat() if u.created_at else None,
        } for u in invitees]

        return enriched, total
