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

from sqlalchemy import String, cast
from sqlmodel import select, func
from sqlmodel.ext.asyncio.session import AsyncSession

from models.commission import CommissionRecord
from models.points_ledger import PointsLedger
from models.user import User
from services.points_account_service import PointsAccountService

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
    async def release_commission_points(
        session: AsyncSession,
        record_id: UUID,
    ) -> tuple[CommissionRecord | None, bool]:
        record = await session.get(CommissionRecord, record_id)
        if not record:
            return None, False
        if record.status == "settled":
            return record, False

        ledger_result = await session.execute(
            select(PointsLedger).where(
                PointsLedger.related_type == "commission_record",
                PointsLedger.related_id == str(record.id),
                PointsLedger.change_type == "invite_rebate_frozen",
                PointsLedger.source == "invite",
            )
        )
        frozen_ledger = ledger_result.scalar_one_or_none()
        if not frozen_ledger:
            raise RuntimeError("commission frozen points ledger not found")

        await PointsAccountService.release_frozen_points(
            session=session,
            user_id=record.user_id,
            points=int(frozen_ledger.points_delta),
            idempotency_key=f"invite_rebate_unfreeze:{record.id}",
            related_type="commission_record",
            related_id=str(record.id),
            remark=f"release level {record.level} vip rebate points",
        )
        record.status = "settled"
        await session.flush()
        return record, True

    @staticmethod
    async def get_invite_stats(session: AsyncSession, user_id: UUID) -> dict:
        """获取用户的邀请统计"""
        user = await session.get(User, user_id)
        if not user:
            return {}
        account, _ = await PointsAccountService.ensure_user_account(session, user_id)
        reward_summary = await _build_invite_reward_summary(session, user_id)
        member_count = (
            await session.execute(
                select(func.count())
                .select_from(User)
                .where(User.parent_id == user_id, User.is_vip == True)  # noqa: E712
            )
        ).scalar() or 0

        return {
            "invite_code": user.invite_code,
            "direct_count": user.invite_count,
            "indirect_count": user.indirect_count,
            "team_count": user.team_count,
            "member_count": int(member_count),
            "total_income": float(user.total_income),
            "balance": float(user.balance),
            "total_withdrawn": float(user.total_withdrawn),
            "frozen_balance": float(user.frozen_balance),
            "total_reward_points": int(reward_summary["total_reward_points"]),
            "frozen_reward_points": int(reward_summary["frozen_reward_points"]),
            "available_reward_points": int(reward_summary["available_reward_points"]),
            "latest_reward": reward_summary["latest_reward"],
            "account": {
                "total_points": int(account.total_points),
                "withdrawable_points": int(account.withdrawable_points),
                "frozen_points": int(account.frozen_points),
                "consumable_points": int(account.consumable_points),
            },
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


async def _build_invite_reward_summary(session: AsyncSession, user_id: UUID) -> dict:
    total_reward_points = (
        await session.execute(
            select(func.coalesce(func.sum(PointsLedger.points_delta), 0)).where(
                PointsLedger.user_id == user_id,
                PointsLedger.source == "invite",
                PointsLedger.points_delta > 0,
            )
        )
    ).scalar() or 0
    frozen_reward_points = (
        await session.execute(
            select(func.coalesce(func.sum(PointsLedger.points_delta), 0))
            .select_from(PointsLedger)
            .join(CommissionRecord, PointsLedger.related_id == cast(CommissionRecord.id, String))
            .where(
                PointsLedger.user_id == user_id,
                PointsLedger.source == "invite",
                PointsLedger.change_type == "invite_rebate_frozen",
                PointsLedger.related_type == "commission_record",
                PointsLedger.points_delta > 0,
                CommissionRecord.status == "pending",
            )
        )
    ).scalar() or 0
    latest_reward = await _get_latest_invite_reward(session, user_id)
    return {
        "total_reward_points": int(total_reward_points),
        "frozen_reward_points": int(frozen_reward_points),
        "available_reward_points": max(int(total_reward_points) - int(frozen_reward_points), 0),
        "latest_reward": latest_reward,
    }


async def _get_latest_invite_reward(session: AsyncSession, user_id: UUID) -> dict | None:
    result = await session.execute(
        select(PointsLedger)
        .where(
            PointsLedger.user_id == user_id,
            PointsLedger.source == "invite",
            PointsLedger.points_delta > 0,
        )
        .order_by(PointsLedger.created_at.desc(), PointsLedger.id.desc())
        .limit(1)
    )
    ledger = result.scalar_one_or_none()
    if not ledger:
        return None

    title = _invite_reward_title(ledger.change_type)
    from_user_nickname = ""
    level = None
    if ledger.related_type == "commission_record" and ledger.related_id:
        try:
            record = await session.get(CommissionRecord, UUID(str(ledger.related_id)))
        except ValueError:
            record = None
        if record:
            level = int(record.level)
            from_user = await session.get(User, record.from_user_id)
            from_user_nickname = from_user.nickname if from_user else ""
            title = "好友开通会员奖励" if level == 1 else "团队会员奖励"

    return {
        "id": str(ledger.id),
        "title": title,
        "points": int(ledger.points_delta),
        "availability": ledger.availability,
        "level": level,
        "from_user_nickname": from_user_nickname,
        "created_at": ledger.created_at.isoformat() if ledger.created_at else None,
    }


def _invite_reward_title(change_type: str) -> str:
    mapping = {
        "invite_register": "好友注册奖励",
        "invite_first_resource": "好友首次获取资源奖励",
        "invite_first_recharge": "好友首次充值奖励",
        "invite_rebate_frozen": "好友开通会员奖励",
    }
    return mapping.get(change_type, "邀请奖励")
