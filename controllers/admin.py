"""
管理端接口 — /admin

MVC 架构中的 Controller 层。

迁移来源:
  - 云函数 cloudfunctions/admin-api/index.js
  - controllers/pcRouter.py（代理层，待删除）

鉴权: 管理端需要 Admin Token
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, Request
from sqlmodel import select, func, and_
from sqlmodel.ext.asyncio.session import AsyncSession

from core.response import response
from models.base import get_session
from models.user import User
from models.order import Order
from models.withdrawal import WithdrawalRecord
from models.chat import ChatMessage
from schemas.user import (
    ConfigUpdateRequest,
    AdminReplyRequest,
    PaginatedResponse,
)
from services.config_service import ConfigService
from services.chat_service import ChatService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["管理端"])


# ═══════════════════════════════════════════════════════════════
#  仪表盘
# ═══════════════════════════════════════════════════════════════

@router.get("/dashboard", summary="仪表盘统计")
async def get_dashboard(session: AsyncSession = Depends(get_session)):
    """获取仪表盘关键指标"""
    # 用户总数
    user_count = (await session.execute(
        select(func.count()).select_from(User)
    )).scalar() or 0

    # VIP 数
    vip_count = (await session.execute(
        select(func.count()).select_from(User).where(
            and_(User.is_vip == True, User.vip_expire_at > datetime.utcnow())  # noqa: E712
        )
    )).scalar() or 0

    # 今日新增
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_new = (await session.execute(
        select(func.count()).select_from(User).where(User.created_at >= today_start)
    )).scalar() or 0

    # 提现统计
    pending_count = (await session.execute(
        select(func.count()).select_from(WithdrawalRecord).where(
            WithdrawalRecord.status == "processing"
        )
    )).scalar() or 0

    # 成功提现总额
    success_amount = (await session.execute(
        select(func.coalesce(func.sum(WithdrawalRecord.amount), 0.0))
        .select_from(WithdrawalRecord)
        .where(WithdrawalRecord.status == "success")
    )).scalar() or 0.0

    # 待处理提现总额
    pending_amount = (await session.execute(
        select(func.coalesce(func.sum(WithdrawalRecord.amount), 0.0))
        .select_from(WithdrawalRecord)
        .where(WithdrawalRecord.status == "processing")
    )).scalar() or 0.0

    # 总收益
    total_income = (await session.execute(
        select(func.coalesce(func.sum(User.total_income), 0.0))
        .select_from(User)
    )).scalar() or 0.0

    return response(data={
        "user_count": user_count,
        "vip_count": vip_count,
        "today_new_users": today_new,
        "total_income": float(total_income),
        "pending_withdrawals": pending_count,
        "success_withdrawal_amount": float(success_amount),
        "pending_withdrawal_amount": float(pending_amount),
    })


# ═══════════════════════════════════════════════════════════════
#  用户管理
# ═══════════════════════════════════════════════════════════════

@router.get("/users", summary="用户列表")
async def get_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """获取用户列表（支持关键词搜索）"""
    base_query = select(User)

    if keyword and keyword.strip():
        kw = keyword.strip()
        base_query = base_query.where(
            (User.nickname.ilike(f"%{kw}%")) |
            (User.invite_code.ilike(f"%{kw}%")) |
            (User.openid.ilike(f"%{kw}%"))
        )

    # 总数
    count_query = select(func.count()).select_from(base_query.subquery())
    total = (await session.execute(count_query)).scalar() or 0

    # 列表
    list_query = base_query.order_by(User.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size)
    users = (await session.execute(list_query)).scalars().all()

    items = [_user_to_dict(u) for u in users]
    has_more = ((page - 1) * page_size + len(items)) < total

    return response(data=PaginatedResponse(
        list=items, total=total, page=page, page_size=page_size, has_more=has_more,
    ).model_dump())


@router.get("/users/{user_id}", summary="用户详情")
async def get_user_detail(user_id: str, session: AsyncSession = Depends(get_session)):
    """获取单个用户的详细信息"""
    from uuid import UUID
    try:
        uid = UUID(user_id)
    except ValueError:
        return response([], 400, "无效的用户 ID")

    user = await session.get(User, uid)
    if not user:
        return response([], 404, "用户不存在")

    return response(data=_user_to_dict(user))


# ═══════════════════════════════════════════════════════════════
#  配置管理
# ═══════════════════════════════════════════════════════════════

@router.get("/configs", summary="获取配置")
async def get_config(
    type: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """获取指定类型或所有系统配置"""
    if type:
        data = await ConfigService.get(session, type)
        return response(data=data)

    configs = await ConfigService.get_all_config_types(session)
    result = {c.type: c.config_data for c in configs}
    return response(data=result)


@router.put("/configs", summary="更新配置")
async def update_config(
    req: ConfigUpdateRequest,
    session: AsyncSession = Depends(get_session),
):
    """创建或更新系统配置"""
    config = await ConfigService.set(session, req.type, req.config_data)
    return response(data={"type": config.type, "updated_at": config.updated_at.isoformat()}, msg="配置已保存")


# ═══════════════════════════════════════════════════════════════
#  提现管理
# ═══════════════════════════════════════════════════════════════

@router.get("/withdrawals", summary="提现列表")
async def get_withdrawals(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """查看所有用户的提现记录"""
    base = select(WithdrawalRecord)
    if status:
        base = base.where(WithdrawalRecord.status == status)

    count_q = select(func.count()).select_from(base.subquery())
    total = (await session.execute(count_q)).scalar() or 0

    list_q = base.order_by(WithdrawalRecord.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size)
    records = (await session.execute(list_q)).scalars().all()

    items = [_withdrawal_to_dict(r) for r in records]
    has_more = ((page - 1) * page_size + len(items)) < total

    return response(data=PaginatedResponse(
        list=items, total=total, page=page, page_size=page_size, has_more=has_more,
    ).model_dump())


@router.post("/withdrawals/{record_id}/approve", summary="通过提现")
async def approve_withdrawal(record_id: str, session: AsyncSession = Depends(get_session)):
    """手动通过提现（调用微信转账）"""
    from uuid import UUID
    try:
        rid = UUID(record_id)
    except ValueError:
        return response([], 400, "无效的记录 ID")

    record = await session.get(WithdrawalRecord, rid)
    if not record:
        return response([], 404, "记录不存在")

    # TODO: 实际调用微信商家转账 API
    record.status = "success"
    record.completed_at = datetime.utcnow()
    record.updated_at = datetime.utcnow()
    await session.flush()

    return response(msg="已通过（需集成微信转账 API）")


@router.post("/withdrawals/{record_id}/reject", summary="拒绝提现")
async def reject_withdrawal(
    record_id: str,
    reason: Optional[str] = Query("管理员拒绝"),
    session: AsyncSession = Depends(get_session),
):
    """拒绝提现并退回余额"""
    from uuid import UUID
    try:
        rid = UUID(record_id)
    except ValueError:
        return response([], 400, "无效的记录 ID")

    record = await session.get(WithdrawalRecord, rid)
    if not record:
        return response([], 404, "记录不存在")

    if record.status != "processing":
        return response([], 400, "只能拒绝处理中的提现")

    # 退回余额
    user = await session.get(User, record.user_id)
    if user:
        user.balance += float(record.amount)
        user.frozen_balance -= float(record.amount)
        user.updated_at = datetime.utcnow()

    record.status = "failed"
    record.fail_reason = reason
    record.completed_at = datetime.utcnow()
    record.updated_at = datetime.utcnow()
    await session.flush()

    return response(msg="已拒绝并退回余额")


# ═══════════════════════════════════════════════════════════════
#  客服回复
# ═══════════════════════════════════════════════════════════════

@router.post("/chat/reply", summary="管理员回复")
async def admin_reply(
    req: AdminReplyRequest,
    session: AsyncSession = Depends(get_session),
):
    """管理员回复用户消息"""
    from uuid import UUID
    try:
        uid = UUID(req.user_id)
    except ValueError:
        return response([], 400, "无效的用户 ID")

    msg = await ChatService.admin_reply(session, uid, req.content)

    return response(data={
        "id": str(msg.id),
        "content": msg.content,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }, msg="回复成功")


# ═══════════════════════════════════════════════════════════════
#  工具函数
# ═══════════════════════════════════════════════════════════════

def _user_to_dict(u: User) -> dict:
    return {
        "id": str(u.id),
        "openid": u.openid,
        "nickname": u.nickname,
        "avatar": u.avatar,
        "invite_code": u.invite_code,
        "is_vip": u.is_vip,
        "vip_expire_at": u.vip_expire_at.isoformat() if u.vip_expire_at else None,
        "balance": float(u.balance),
        "frozen_balance": float(u.frozen_balance),
        "total_income": float(u.total_income),
        "total_withdrawn": float(u.total_withdrawn),
        "invite_count": u.invite_count,
        "team_count": u.team_count,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


def _withdrawal_to_dict(r: WithdrawalRecord) -> dict:
    return {
        "id": str(r.id),
        "user_id": str(r.user_id),
        "amount": float(r.amount),
        "status": r.status,
        "batch_no": r.batch_no,
        "transfer_bill_no": r.transfer_bill_no,
        "fail_reason": r.fail_reason,
        "ip": r.ip,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
    }
