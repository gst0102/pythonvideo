"""
聊天接口 — /chat

MVC 架构中的 Controller 层。
用户 ↔ 管理员在线客服聊天。
"""

from fastapi import APIRouter, Depends, Query
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.response import response
from models.base import get_session
from models.user import User
from schemas.user import ChatSendRequest, PaginatedResponse
from services.chat_service import ChatService
from jwt_create import get_current_user

router = APIRouter(prefix="/chat", tags=["在线客服"])


@router.post("/send", summary="发送消息")
async def send_message(
    req: ChatSendRequest,
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """用户发送消息给客服"""
    stmt = select(User).where(User.openid == openid)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        return response([], 404, "用户不存在")

    msg = await ChatService.send_message(
        session, user.id, req.content, sender="user", msg_type=req.msg_type,
    )

    return response(data={
        "id": str(msg.id),
        "content": msg.content,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }, msg="发送成功")


@router.get("/history", summary="聊天历史")
async def get_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """获取当前用户的聊天记录"""
    stmt = select(User).where(User.openid == openid)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        return response([], 404, "用户不存在")

    messages, total, has_more = await ChatService.get_history(
        session, user.id, page, page_size,
    )

    items = [{
        "id": str(m.id),
        "sender": m.sender,
        "content": m.content,
        "msg_type": m.msg_type,
        "is_self": m.sender == "user",
        "is_read": m.is_read,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    } for m in messages]

    return response(data=PaginatedResponse(
        list=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=has_more,
    ).model_dump())


@router.post("/read", summary="标记已读")
async def mark_read(
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """将客服发来的消息标记为已读"""
    stmt = select(User).where(User.openid == openid)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        return response([], 404, "用户不存在")

    count = await ChatService.mark_as_read(session, user.id)
    return response(data={"marked_count": count}, msg="已标记")
