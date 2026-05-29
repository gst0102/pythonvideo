"""
佣金/分销接口 — /commission

MVC 架构中的 Controller 层。
"""

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from core.response import response
from models.base import get_session
from services.commission_service import CommissionService
from schemas.user import PaginatedResponse
from jwt_create import get_current_user

router = APIRouter(prefix="/commission", tags=["佣金分销"])


@router.get("/records", summary="佣金记录")
async def get_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """获取当前用户的佣金记录"""
    from sqlmodel import select
    from models.user import User

    user = (
        await session.execute(select(User).where(User.openid == openid))
    ).scalar_one_or_none()

    if not user:
        return response([], 404, "用户不存在")

    records, total = await CommissionService.get_records(session, user.id, page, page_size)
    has_more = ((page - 1) * page_size + len(records)) < total

    return response(data=PaginatedResponse(
        list=records,
        total=total,
        page=page,
        page_size=page_size,
        has_more=has_more,
    ).model_dump())


@router.get("/invite-stats", summary="邀请统计")
async def get_invite_stats(
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """获取当前用户的邀请统计数据"""
    from sqlmodel import select
    from models.user import User

    user = (
        await session.execute(select(User).where(User.openid == openid))
    ).scalar_one_or_none()

    if not user:
        return response([], 404, "用户不存在")

    stats = await CommissionService.get_invite_stats(session, user.id)
    return response(data=stats)


@router.get("/invitees", summary="被邀请人列表")
async def get_invitees(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """获取我直接邀请的用户列表"""
    from sqlmodel import select
    from models.user import User

    user = (
        await session.execute(select(User).where(User.openid == openid))
    ).scalar_one_or_none()

    if not user:
        return response([], 404, "用户不存在")

    invitees, total = await CommissionService.get_invitees(session, user.id, page, page_size)
    has_more = ((page - 1) * page_size + len(invitees)) < total

    return response(data=PaginatedResponse(
        list=invitees,
        total=total,
        page=page,
        page_size=page_size,
        has_more=has_more,
    ).model_dump())
