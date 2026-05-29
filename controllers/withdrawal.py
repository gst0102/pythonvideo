"""
提现接口 — /withdrawal

MVC 架构中的 Controller 层。

迁移来源:
  - 云函数 cloudfunctions/merchantTransfer/index.js
  - 云函数 cloudfunctions/transferCallback/index.js
"""

import logging

from fastapi import APIRouter, Depends, Query, Request
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.response import response
from models.base import get_session
from models.user import User
from schemas.user import (
    WithdrawalApplyRequest,
    WithdrawalConfigResponse,
    PaginatedResponse,
)
from services.withdrawal_service import WithdrawalService
from services.config_service import ConfigService
from jwt_create import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/withdrawal", tags=["提现管理"])


@router.get("/config", summary="提现配置")
async def get_config(session: AsyncSession = Depends(get_session)):
    """获取提现规则配置"""
    config = await ConfigService.get_withdrawal_config(session)
    return response(data=WithdrawalConfigResponse(
        min_amount=float(config.get("min_amount", 0.10)),
        max_amount=float(config.get("max_amount", 200.00)),
        tips=config.get("tips", ""),
    ).model_dump())


@router.post("/apply", summary="申请提现")
async def apply_withdrawal(
    req: WithdrawalApplyRequest,
    request: Request,
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """发起提现申请"""
    # 获取用户
    stmt = select(User).where(User.openid == openid)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        return response([], 404, "用户不存在")

    # 执行提现（传入 openid 用于微信商家转账）
    record, error = await WithdrawalService.apply_withdrawal(
        session, user.id, req.amount,
        openid=openid,
        ip=request.client.host if request.client else None,
    )

    if error:
        return response([], 400, error)

    # 构建响应数据（参照云函数返回格式）
    resp_data = {
        "record_id": str(record.id),
        "amount": float(record.amount),
        "status": record.status,
        "batch_no": record.batch_no,
        "transfer_bill_no": record.transfer_bill_no or "",
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }

    return response(data=resp_data, msg="提现申请已提交")


@router.get("/records", summary="提现记录")
async def get_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """获取当前用户的提现记录"""
    stmt = select(User).where(User.openid == openid)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        return response([], 404, "用户不存在")

    records, total = await WithdrawalService.get_records(session, user.id, page, page_size)

    items = [{
        "id": str(r.id),
        "amount": float(r.amount),
        "status": r.status,
        "batch_no": r.batch_no,
        "fail_reason": r.fail_reason,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
    } for r in records]

    has_more = ((page - 1) * page_size + len(items)) < total

    return response(data=PaginatedResponse(
        list=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=has_more,
    ).model_dump())


@router.post("/release-frozen", summary="释放冻结金额（修复上次提现失败余额锁定）")
async def release_frozen(
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    清理因上次提现失败导致被锁定的冻结金额。
    参照云函数 releaseFrozenAmount：
    - 无 processing 记录 → 直接释放所有冻结金额
    - 有 processing 记录但超过24小时 → 标记失败并退回
    - 有 processing 记录且不足24小时 → 不允许强制释放
    """
    stmt = select(User).where(User.openid == openid)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        return response([], 404, "用户不存在")

    released, cleared_nos, error = await WithdrawalService.release_frozen_amount(session, user.id)

    if error:
        return response(data={"released": 0, "frozen": float(user.frozen_balance)}, code=400, msg=error)

    return response(data={
        "released": released,
        "cleared_batch_nos": cleared_nos,
        "remaining_frozen": round(float(user.frozen_balance), 2),
        "balance": round(float(user.balance), 2),
    }, msg=f"已释放 {released:.2f} 元冻结金额")
