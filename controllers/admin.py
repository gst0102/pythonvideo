import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlmodel import and_, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.response import response
from models.base import get_session
from models.chat import ChatMessage
from models.user import User
from models.withdrawal import WithdrawalRecord
from schemas.admin_settlement import AdminGameSettlementTriggerRequest, AdminGameSettlementUpsertRequest
from schemas.user import AdminReplyRequest, AdminUserVipUpdateRequest, ConfigUpdateRequest, PaginatedResponse
from services.chat_service import ChatService
from services.config_service import ConfigService
from services.game_ad_service import build_game_bonus_ad_config_payload, normalize_game_bonus_ad_config
from services.game_settlement_service import GameSettlementService
from services.withdrawal_service import WithdrawalService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/dashboard", summary="dashboard")
async def get_dashboard(session: AsyncSession = Depends(get_session)):
    user_count = (await session.execute(select(func.count()).select_from(User))).scalar() or 0
    total_vip_count = (
        await session.execute(select(func.count()).select_from(User).where(User.is_vip == True))  # noqa: E712
    ).scalar() or 0
    vip_count = (
        await session.execute(
            select(func.count()).select_from(User).where(
                and_(User.is_vip == True, User.vip_expire_at > datetime.utcnow())  # noqa: E712
            )
        )
    ).scalar() or 0
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_new = (
        await session.execute(select(func.count()).select_from(User).where(User.created_at >= today_start))
    ).scalar() or 0
    pending_count = (
        await session.execute(
            select(func.count()).select_from(WithdrawalRecord).where(WithdrawalRecord.status == "processing")
        )
    ).scalar() or 0
    success_amount = (
        await session.execute(
            select(func.coalesce(func.sum(WithdrawalRecord.amount), 0.0))
            .select_from(WithdrawalRecord)
            .where(WithdrawalRecord.status == "success")
        )
    ).scalar() or 0.0
    pending_amount = (
        await session.execute(
            select(func.coalesce(func.sum(WithdrawalRecord.amount), 0.0))
            .select_from(WithdrawalRecord)
            .where(WithdrawalRecord.status == "processing")
        )
    ).scalar() or 0.0
    total_income = (
        await session.execute(select(func.coalesce(func.sum(User.total_income), 0.0)).select_from(User))
    ).scalar() or 0.0

    return response(
        data={
            "user_count": user_count,
            "total_vip_count": total_vip_count,
            "vip_count": vip_count,
            "today_new_users": today_new,
            "total_income": float(total_income),
            "pending_withdrawals": pending_count,
            "success_withdrawal_amount": float(success_amount),
            "pending_withdrawal_amount": float(pending_amount),
        }
    )


@router.get("/users", summary="user list")
async def get_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = Query(None),
    is_vip: Optional[bool] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    query = select(User)
    if keyword and keyword.strip():
        kw = keyword.strip()
        query = query.where(
            (User.nickname.ilike(f"%{kw}%"))
            | (User.invite_code.ilike(f"%{kw}%"))
            | (User.openid.ilike(f"%{kw}%"))
        )
    if is_vip is not None:
        query = query.where(User.is_vip == is_vip)

    total = (await session.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
    users = (
        await session.execute(query.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()

    items = [_user_to_dict(user) for user in users]
    return response(
        data=PaginatedResponse(
            list=items,
            total=total,
            page=page,
            page_size=page_size,
            has_more=((page - 1) * page_size + len(items)) < total,
        ).model_dump()
    )


@router.get("/users/{user_id}", summary="user detail")
async def get_user_detail(user_id: str, session: AsyncSession = Depends(get_session)):
    try:
        uid = UUID(user_id)
    except ValueError:
        return response([], 400, "invalid user id")

    user = await session.get(User, uid)
    if not user:
        return response([], 404, "user not found")
    withdrawals = (
        await session.execute(
            select(WithdrawalRecord)
            .where(WithdrawalRecord.user_id == uid)
            .order_by(WithdrawalRecord.created_at.desc())
            .limit(50)
        )
    ).scalars().all()
    return response(
        data={
            **_user_to_dict(user),
            "withdrawals": [_withdrawal_to_dict(record, user) for record in withdrawals],
        }
    )


@router.put("/users/{user_id}/vip", summary="update user vip")
async def update_user_vip(
    user_id: str,
    req: AdminUserVipUpdateRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        uid = UUID(user_id)
    except ValueError:
        return response([], 400, "invalid user id")

    user = await session.get(User, uid)
    if not user:
        return response([], 404, "user not found")

    user.is_vip = req.is_vip
    user.vip_expire_at = req.vip_expire_at if req.is_vip else None
    user.updated_at = datetime.utcnow()
    await session.flush()
    return response(data=_user_to_dict(user), msg="vip updated")


@router.get("/configs", summary="get config")
async def get_config(type: Optional[str] = Query(None), session: AsyncSession = Depends(get_session)):
    if type:
        return response(data=await ConfigService.get(session, type))

    configs = await ConfigService.get_all_config_types(session)
    return response(data={config.type: config.config_data for config in configs})


@router.put("/configs", summary="update config")
async def update_config(req: ConfigUpdateRequest, session: AsyncSession = Depends(get_session)):
    config = await ConfigService.set(session, req.type, req.config_data)
    return response(data={"type": config.type, "updated_at": config.updated_at.isoformat()}, msg="config updated")


@router.get("/ad/game-bonus-config", summary="get stage2 game bonus ad config")
async def get_game_bonus_ad_config(session: AsyncSession = Depends(get_session)):
    config = await ConfigService.get(session, "stage2_game_bonus_ad_config")
    return response(data=build_game_bonus_ad_config_payload(config))


@router.put("/ad/game-bonus-config", summary="update stage2 game bonus ad config")
async def update_game_bonus_ad_config(req: ConfigUpdateRequest, session: AsyncSession = Depends(get_session)):
    normalized = normalize_game_bonus_ad_config(req.config_data)
    config = await ConfigService.set(session, "stage2_game_bonus_ad_config", normalized)
    return response(
        data=build_game_bonus_ad_config_payload(config.config_data),
        msg="game bonus ad config updated",
    )


@router.get("/game-settlements/daily", summary="get stage2 game settlement detail")
async def get_game_settlement_detail(
    settlement_date: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    target_day = _parse_settlement_date_or_default(settlement_date)
    if not target_day:
        return response([], 400, "invalid settlement_date")
    data = await GameSettlementService.get_daily_detail(session, target_day)
    return response(data=data)


@router.put("/game-settlements/daily", summary="upsert stage2 game settlement input")
async def upsert_game_settlement_input(
    req: AdminGameSettlementUpsertRequest,
    session: AsyncSession = Depends(get_session),
):
    data = await GameSettlementService.save_daily_input(
        session,
        settlement_day=req.settlement_date,
        ecpm_value=req.ecpm_value,
        ad_pv=req.ad_pv,
        valid_clicks=req.valid_clicks,
        total_revenue=req.total_revenue,
        note=req.note,
    )
    return response(data=data, msg="game settlement input updated")


@router.post("/game-settlements/daily/trigger", summary="trigger stage2 game settlement")
async def trigger_game_settlement(
    req: AdminGameSettlementTriggerRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        data = await GameSettlementService.trigger_daily_settlement(
            session,
            settlement_day=req.settlement_date,
            allow_fallback=req.allow_fallback,
            force_recalculate=req.force_recalculate,
        )
    except ValueError as exc:
        return response([], 400, str(exc))
    return response(data=data, msg="game settlement triggered")


@router.get("/withdrawals", summary="withdrawal list")
async def get_withdrawals(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    query = select(WithdrawalRecord)
    if status:
        query = query.where(WithdrawalRecord.status == status)

    total = (await session.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
    records = (
        await session.execute(
            query.order_by(WithdrawalRecord.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )
    ).scalars().all()

    user_ids = {record.user_id for record in records}
    user_map = {}
    if user_ids:
        users = (await session.execute(select(User).where(User.id.in_(list(user_ids))))).scalars().all()
        user_map = {user.id: user for user in users}

    items = [_withdrawal_to_dict(record, user_map.get(record.user_id)) for record in records]
    return response(
        data=PaginatedResponse(
            list=items,
            total=total,
            page=page,
            page_size=page_size,
            has_more=((page - 1) * page_size + len(items)) < total,
        ).model_dump()
    )


@router.post("/withdrawals/{record_id}/approve", summary="submit transfer")
async def approve_withdrawal(record_id: str, session: AsyncSession = Depends(get_session)):
    try:
        rid = UUID(record_id)
    except ValueError:
        return response([], 400, "invalid withdrawal id")

    record, error = await WithdrawalService.submit_processing_withdrawal(session, rid)
    if error:
        return response([], 400, error)
    return response(
        data={
            "id": str(record.id),
            "status": record.status,
            "batch_no": record.batch_no,
            "transfer_bill_no": record.transfer_bill_no,
        },
        msg="transfer submitted",
    )


@router.post("/withdrawals/{record_id}/reject", summary="reject withdrawal")
async def reject_withdrawal(
    record_id: str,
    reason: Optional[str] = Query("admin_rejected"),
    session: AsyncSession = Depends(get_session),
):
    try:
        rid = UUID(record_id)
    except ValueError:
        return response([], 400, "invalid withdrawal id")

    record = await session.get(WithdrawalRecord, rid)
    if not record:
        return response([], 404, "withdrawal not found")
    if record.status != "processing":
        return response([], 400, "withdrawal is not in processing state")
    if record.transfer_bill_no:
        return response([], 400, "transfer already submitted, wait for callback")

    await WithdrawalService.handle_transfer_failed(session, record.batch_no, reason or "admin_rejected")
    return response(msg="withdrawal rejected")


@router.get("/chat/messages", summary="chat messages")
async def get_chat_messages(
    user_id: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    query = select(ChatMessage)
    if user_id:
        try:
            uid = UUID(user_id)
        except ValueError:
            return response([], 400, "invalid user id")
        query = query.where(ChatMessage.user_id == uid)

    messages = (await session.execute(query.order_by(ChatMessage.created_at.asc()).limit(500))).scalars().all()
    return response(
        data=[
            {
                "id": str(msg.id),
                "user_id": str(msg.user_id),
                "sender": msg.sender,
                "content": msg.content,
                "msg_type": msg.msg_type,
                "is_read": msg.is_read,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
            }
            for msg in messages
        ]
    )


@router.post("/chat/reply", summary="admin reply")
async def admin_reply(req: AdminReplyRequest, session: AsyncSession = Depends(get_session)):
    try:
        uid = UUID(req.user_id)
    except ValueError:
        return response([], 400, "invalid user id")

    msg = await ChatService.admin_reply(session, uid, req.content)
    return response(
        data={"id": str(msg.id), "content": msg.content, "created_at": msg.created_at.isoformat()},
        msg="reply sent",
    )


def _user_to_dict(user: User) -> dict:
    return {
        "id": str(user.id),
        "openid": user.openid,
        "nickname": user.nickname,
        "avatar": user.avatar,
        "invite_code": user.invite_code,
        "is_vip": user.is_vip,
        "vip_expire_at": user.vip_expire_at.isoformat() if user.vip_expire_at else None,
        "balance": float(user.balance),
        "frozen_balance": float(user.frozen_balance),
        "total_income": float(user.total_income),
        "total_withdrawn": float(user.total_withdrawn),
        "invite_count": user.invite_count,
        "team_count": user.team_count,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def _withdrawal_to_dict(record: WithdrawalRecord, user: Optional[User] = None) -> dict:
    return {
        "id": str(record.id),
        "user_id": str(record.user_id),
        "nickname": user.nickname if user else "",
        "avatar": user.avatar if user else "",
        "amount": float(record.amount),
        "status": record.status,
        "batch_no": record.batch_no,
        "transfer_bill_no": record.transfer_bill_no,
        "fail_reason": record.fail_reason,
        "ip": record.ip,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "completed_at": record.completed_at.isoformat() if record.completed_at else None,
    }


def _parse_settlement_date_or_default(raw: Optional[str]):
    if not raw:
        return (datetime.utcnow() - timedelta(days=1)).date()
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None
