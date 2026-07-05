import csv
import io
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, Header, Query, Response, UploadFile
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlmodel import and_, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.timezone import bj_day_bounds_utc, today_bj
from core.response import response
from models.base import get_session
from models.chat import ChatMessage
from models.equity_ledger import EquityLedger
from models.netdisk_audit_log import NetdiskAuditLog
from models.netdisk_crawler_run import NetdiskCrawlerRun
from models.netdisk_collected_resource import NetdiskCollectedResource
from models.netdisk_import_batch import NetdiskImportBatch
from models.netdisk_official_access_record import NetdiskOfficialAccessRecord
from models.netdisk_quality_alert import NetdiskQualityAlert
from models.netdisk_quality_daily_stat import NetdiskQualityDailyStat
from models.netdisk_repair import NetdiskRepair
from models.netdisk_request import NetdiskRequest
from models.netdisk_resource import NetdiskResource as NetdiskResourceModel
from models.netdisk_transfer_task import NetdiskTransferTask
from models.netdisk_risk_record import NetdiskRiskRecord
from models.netdisk_upload import NetdiskUpload
from models.netdisk_user_notification import NetdiskUserNotification
from models.invite_relation import InviteRelation
from models.order import Order
from models.points_ledger import PointsLedger
from models.user import User
from models.user_account import UserAccount
from models.withdrawal import WithdrawalRecord
from schemas.admin_settlement import AdminGameSettlementTriggerRequest, AdminGameSettlementUpsertRequest
from schemas.netdisk import NetdiskAdminAuditRequest, NetdiskCollectedBulkActionRequest
from schemas.user import AdminReplyRequest, AdminUserVipUpdateRequest, ConfigUpdateRequest, PaginatedResponse
from services.chat_service import ChatService
from services.config_service import ConfigService
from services.game_ad_service import build_game_bonus_ad_config_payload, normalize_game_bonus_ad_config
from services.game_settlement_service import GameSettlementService
from services.netdisk_quality_stat_service import build_resource_quality_day_stat, refresh_netdisk_quality_daily_stats
from services.netdisk_resource_service import NetdiskResourceService
from services.points_account_service import PointsAccountService
from services.withdrawal_service import WithdrawalService
from controllers.vip import sync_recent_pending_virtual_pay_orders

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


class AdminPointsAdjustRequest(BaseModel):
    action: str = Field(pattern="^(add|consume)$")
    points: int = Field(gt=0, le=10000000)
    note: str = Field(default="", max_length=300)


class AdminPaymentReconcileRequest(BaseModel):
    lookback_minutes: int = Field(default=180, ge=1, le=1440)
    limit: int = Field(default=50, ge=1, le=200)


class NetdiskFrontendCategoriesUpdateRequest(BaseModel):
    categories: list[str] = Field(default_factory=list)


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
    today_start, _ = bj_day_bounds_utc()
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


@router.get("/payments/orders", summary="payment order list")
async def admin_payment_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, pattern="^(pending|paid|closed|refunded)$"),
    keyword: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    query = select(Order).where(Order.period.startswith("points_"))
    if status:
        query = query.where(Order.status == status)
    if keyword and keyword.strip():
        kw = keyword.strip()
        user_sq = select(User.id).where((User.openid.ilike(f"%{kw}%")) | (User.nickname.ilike(f"%{kw}%")))
        query = query.where((Order.out_trade_no.ilike(f"%{kw}%")) | (Order.user_id.in_(user_sq)))

    total = (await session.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
    orders = (
        await session.execute(query.order_by(Order.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()
    user_map = await _get_user_map(session, [item.user_id for item in orders])
    ledger_map = await _get_recharge_ledger_map(session, [item.id for item in orders])
    items = [_payment_order_to_dict(item, user_map.get(item.user_id), ledger_map.get(str(item.id))) for item in orders]
    return response(
        data=PaginatedResponse(
            list=items,
            total=total,
            page=page,
            page_size=page_size,
            has_more=((page - 1) * page_size + len(items)) < total,
        ).model_dump()
    )


@router.post("/payments/reconcile", summary="reconcile pending virtual payment orders")
async def admin_reconcile_payment_orders(
    req: AdminPaymentReconcileRequest,
    x_admin_role: str = Header("operator"),
    session: AsyncSession = Depends(get_session),
):
    if not _is_quality_supervisor(x_admin_role):
        return response([], 403, "仅主管可执行支付补单")
    result = await sync_recent_pending_virtual_pay_orders(
        session,
        redis=None,
        lookback_minutes=req.lookback_minutes,
        limit=req.limit,
    )
    await _record_netdisk_audit_log(
        session,
        "payment_reconcile",
        "payment",
        "virtual_pay",
        "虚拟支付补单",
        f"检查 {result.get('checked', 0)} 单，补到账 {result.get('paid', 0)} 单",
    )
    return response(data=result, msg="支付补单完成")


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

    account_map = await _get_user_account_map(session, [user.id for user in users])
    items = [_user_to_dict(user, account_map.get(user.id)) for user in users]
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
    account, _ = await PointsAccountService.ensure_user_account(session, user.id)
    ledgers = (
        await session.execute(
            select(PointsLedger)
            .where(PointsLedger.user_id == uid)
            .order_by(PointsLedger.created_at.desc(), PointsLedger.id.desc())
            .limit(50)
        )
    ).scalars().all()
    return response(
        data={
            **_user_to_dict(user, account),
            "withdrawals": [_withdrawal_to_dict(record, user) for record in withdrawals],
            "points_ledger": [_points_ledger_to_dict(item) for item in ledgers],
        }
    )


@router.post("/users/{user_id}/points-adjust", summary="adjust user points")
async def adjust_user_points(
    user_id: str,
    req: AdminPointsAdjustRequest,
    x_admin_role: str = Header("operator"),
    session: AsyncSession = Depends(get_session),
):
    if not _is_quality_supervisor(x_admin_role):
        return response([], 403, "仅主管可调整用户积分")
    try:
        uid = UUID(user_id)
    except ValueError:
        return response([], 400, "invalid user id")

    user = await session.get(User, uid)
    if not user:
        return response([], 404, "user not found")

    safe_note = (req.note or "").strip() or ("后台增加积分" if req.action == "add" else "后台消耗积分")
    idempotency_key = f"admin_points_adjust:{req.action}:{user.id}:{uuid4()}"
    try:
        if req.action == "add":
            ledger, account, _ = await PointsAccountService.add_points(
                session=session,
                user_id=user.id,
                points=int(req.points),
                source="admin_adjust",
                change_type="admin_points_adjust",
                availability="consumable",
                idempotency_key=idempotency_key,
                related_type="admin_user_points",
                related_id=str(user.id),
                remark=safe_note,
            )
        else:
            ledger, account, _ = await PointsAccountService.consume_consumable_points(
                session=session,
                user_id=user.id,
                points=int(req.points),
                source="admin_adjust",
                change_type="admin_points_adjust",
                idempotency_key=idempotency_key,
                related_type="admin_user_points",
                related_id=str(user.id),
                remark=safe_note,
            )
    except ValueError as exc:
        return response([], 400, str(exc))

    await _record_netdisk_audit_log(
        session,
        f"user_points_{req.action}",
        "user",
        str(user.id),
        user.nickname or user.openid,
        safe_note,
    )
    return response(
        data={
            "user": _user_to_dict(user, account),
            "account": _account_to_dict(account),
            "ledger": _points_ledger_to_dict(ledger),
        },
        msg="用户积分已调整",
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


def _normalize_category_names(categories: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for item in categories:
        value = str(item or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value[:32])
    return normalized


@router.get("/netdisk/frontend-categories", summary="get netdisk frontend categories")
async def get_netdisk_frontend_categories(session: AsyncSession = Depends(get_session)):
    config = await ConfigService.get(session, "netdisk_frontend_categories_config")
    configured = _normalize_category_names(config.get("categories") or [])
    return response(data={"categories": configured})


@router.put("/netdisk/frontend-categories", summary="update netdisk frontend categories")
async def update_netdisk_frontend_categories(
    req: NetdiskFrontendCategoriesUpdateRequest,
    session: AsyncSession = Depends(get_session),
):
    categories = _normalize_category_names(req.categories)
    config = await ConfigService.set(session, "netdisk_frontend_categories_config", {"categories": categories})
    return response(data={"categories": categories, "updated_at": config.updated_at.isoformat()}, msg="categories updated")


@router.get("/netdisk/transfer-tasks", summary="admin netdisk transfer tasks")
async def admin_netdisk_transfer_tasks(
    status: Optional[str] = Query(None),
    pan: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    query = select(NetdiskTransferTask)
    if status:
        query = query.where(NetdiskTransferTask.status == status)
    if pan:
        query = query.where((NetdiskTransferTask.source_pan == pan) | (NetdiskTransferTask.target_pan == pan))
    if keyword and keyword.strip():
        kw = keyword.strip()
        query = query.where(
            or_(
                NetdiskTransferTask.title.ilike(f"%{kw}%"),
                NetdiskTransferTask.source_link.ilike(f"%{kw}%"),
                NetdiskTransferTask.target_link.ilike(f"%{kw}%"),
                NetdiskTransferTask.resource_id.ilike(f"%{kw}%"),
                NetdiskTransferTask.source_ref.ilike(f"%{kw}%"),
            )
        )

    total = (await session.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
    rows = (
        await session.execute(
            query.order_by(NetdiskTransferTask.created_at.desc(), NetdiskTransferTask.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return response(
        data=PaginatedResponse(
            list=[_transfer_task_to_dict(item) for item in rows],
            total=total,
            page=page,
            page_size=page_size,
            has_more=((page - 1) * page_size + len(rows)) < total,
        ).model_dump()
    )


@router.get("/netdisk/new-official-access-records", summary="admin netdisk new official access records")
async def admin_netdisk_new_official_access_records(
    settlement_status: Optional[str] = Query(None),
    pan: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    query = select(NetdiskOfficialAccessRecord)
    if settlement_status:
        query = query.where(NetdiskOfficialAccessRecord.settlement_status == settlement_status)
    if pan:
        query = query.where(NetdiskOfficialAccessRecord.pan == pan)
    if keyword and keyword.strip():
        kw = keyword.strip()
        query = query.where(
            or_(
                NetdiskOfficialAccessRecord.resource_id.ilike(f"%{kw}%"),
                NetdiskOfficialAccessRecord.unlock_ledger_id.ilike(f"%{kw}%"),
                NetdiskOfficialAccessRecord.idempotency_key.ilike(f"%{kw}%"),
                NetdiskOfficialAccessRecord.remark.ilike(f"%{kw}%"),
            )
        )

    total = (await session.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
    rows = (
        await session.execute(
            query.order_by(NetdiskOfficialAccessRecord.created_at.desc(), NetdiskOfficialAccessRecord.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    user_ids = [item.user_id for item in rows] + [item.level1_user_id for item in rows if item.level1_user_id] + [item.level2_user_id for item in rows if item.level2_user_id]
    user_map = await _get_user_map(session, user_ids)
    return response(
        data=PaginatedResponse(
            list=[_new_official_access_to_dict(item, user_map) for item in rows],
            total=total,
            page=page,
            page_size=page_size,
            has_more=((page - 1) * page_size + len(rows)) < total,
        ).model_dump()
    )


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
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    query = select(WithdrawalRecord)
    if status:
        query = query.where(WithdrawalRecord.status == status)
    if keyword and keyword.strip():
        kw = keyword.strip()
        user_sq = select(User.id).where(
            (User.openid.ilike(f"%{kw}%"))
            | (User.nickname.ilike(f"%{kw}%"))
            | (User.invite_code.ilike(f"%{kw}%"))
        )
        keyword_filters = [
            WithdrawalRecord.batch_no.ilike(f"%{kw}%"),
            WithdrawalRecord.transfer_bill_no.ilike(f"%{kw}%"),
            WithdrawalRecord.fail_reason.ilike(f"%{kw}%"),
            WithdrawalRecord.user_id.in_(user_sq),
        ]
        try:
            keyword_filters.append(WithdrawalRecord.id == UUID(kw))
        except ValueError:
            pass
        query = query.where(or_(*keyword_filters))

    stats_sq = query.subquery()
    total = (await session.execute(select(func.count()).select_from(stats_sq))).scalar() or 0
    total_amount = (
        await session.execute(select(func.coalesce(func.sum(stats_sq.c.amount), 0.0)).select_from(stats_sq))
    ).scalar() or 0.0
    processing_amount = (
        await session.execute(
            select(func.coalesce(func.sum(stats_sq.c.amount), 0.0)).select_from(stats_sq).where(stats_sq.c.status == "processing")
        )
    ).scalar() or 0.0
    success_amount = (
        await session.execute(
            select(func.coalesce(func.sum(stats_sq.c.amount), 0.0)).select_from(stats_sq).where(stats_sq.c.status == "success")
        )
    ).scalar() or 0.0
    failed_amount = (
        await session.execute(
            select(func.coalesce(func.sum(stats_sq.c.amount), 0.0)).select_from(stats_sq).where(stats_sq.c.status.in_(["failed", "rejected"]))
        )
    ).scalar() or 0.0
    records = (
        await session.execute(
            query.order_by(WithdrawalRecord.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )
    ).scalars().all()

    user_ids = [record.user_id for record in records]
    user_map = await _get_user_map(session, user_ids)
    account_map = await _get_user_account_map(session, user_ids)
    ledger_map = await _get_withdrawal_equity_ledger_map(session, [record.id for record in records])

    items = [
        _withdrawal_to_dict(
            record,
            user_map.get(record.user_id),
            account_map.get(record.user_id),
            ledger_map.get(str(record.id), []),
        )
        for record in records
    ]
    return response(
        data=PaginatedResponse(
            list=items,
            total=total,
            page=page,
            page_size=page_size,
            has_more=((page - 1) * page_size + len(items)) < total,
        ).model_dump()
        | {
            "stats": {
                "total_amount": round(float(total_amount), 2),
                "processing_amount": round(float(processing_amount), 2),
                "success_amount": round(float(success_amount), 2),
                "failed_amount": round(float(failed_amount), 2),
            }
        }
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


@router.get("/equity-ledger", summary="admin equity cash ledger")
async def admin_equity_ledger(
    keyword: Optional[str] = Query(None),
    change_type: Optional[str] = Query(None),
    related_type: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    query = select(EquityLedger)
    if change_type:
        query = query.where(EquityLedger.change_type == change_type)
    if related_type:
        query = query.where(EquityLedger.related_type == related_type)

    start_dt = _parse_admin_datetime(start_date, end_of_day=False)
    end_dt = _parse_admin_datetime(end_date, end_of_day=True)
    if start_dt:
        query = query.where(EquityLedger.created_at >= start_dt)
    if end_dt:
        query = query.where(EquityLedger.created_at <= end_dt)

    if keyword and keyword.strip():
        kw = keyword.strip()
        user_sq = select(User.id).where(
            (User.openid.ilike(f"%{kw}%"))
            | (User.nickname.ilike(f"%{kw}%"))
            | (User.invite_code.ilike(f"%{kw}%"))
        )
        keyword_filters = [
            EquityLedger.related_id.ilike(f"%{kw}%"),
            EquityLedger.idempotency_key.ilike(f"%{kw}%"),
            EquityLedger.remark.ilike(f"%{kw}%"),
            EquityLedger.user_id.in_(user_sq),
        ]
        try:
            keyword_filters.append(EquityLedger.id == UUID(kw))
        except ValueError:
            pass
        query = query.where(or_(*keyword_filters))

    stats_sq = query.subquery()
    total = (await session.execute(select(func.count()).select_from(stats_sq))).scalar() or 0
    amount_in = (
        await session.execute(
            select(func.coalesce(func.sum(stats_sq.c.amount_delta), 0.0)).select_from(stats_sq).where(stats_sq.c.amount_delta > 0)
        )
    ).scalar() or 0.0
    amount_out = (
        await session.execute(
            select(func.coalesce(func.sum(stats_sq.c.amount_delta), 0.0)).select_from(stats_sq).where(stats_sq.c.amount_delta < 0)
        )
    ).scalar() or 0.0
    frozen_delta = (
        await session.execute(select(func.coalesce(func.sum(stats_sq.c.frozen_delta), 0.0)).select_from(stats_sq))
    ).scalar() or 0.0
    rows = (
        await session.execute(
            query.order_by(EquityLedger.created_at.desc(), EquityLedger.id.desc()).offset((page - 1) * page_size).limit(page_size)
        )
    ).scalars().all()

    user_map = await _get_user_map(session, [row.user_id for row in rows])
    return response(
        data=PaginatedResponse(
            list=[_equity_ledger_to_dict(item, user_map.get(item.user_id)) for item in rows],
            total=total,
            page=page,
            page_size=page_size,
            has_more=((page - 1) * page_size + len(rows)) < total,
        ).model_dump()
        | {
            "stats": {
                "amount_in": round(float(amount_in), 2),
                "amount_out": round(float(amount_out), 2),
                "net_amount": round(float(amount_in) + float(amount_out), 2),
                "frozen_delta": round(float(frozen_delta), 2),
            }
        }
    )


@router.get("/netdisk/uploads", summary="admin netdisk upload list")
async def admin_list_netdisk_uploads(
    status: Optional[str] = Query(None),
    upload_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    payload = await NetdiskResourceService.list_admin_uploads(
        session=session,
        status=status,
        upload_id=upload_id,
        page=page,
        page_size=page_size,
    )
    return response(data=jsonable_encoder(payload))


@router.post("/netdisk/uploads/{upload_id}/approve", summary="admin approve netdisk upload")
async def admin_approve_netdisk_upload(
    upload_id: str,
    req: NetdiskAdminAuditRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        payload = await NetdiskResourceService.approve_upload(
            session,
            upload_id,
            req.note,
            resource_level=req.resource_level,
            cost_points=req.cost_points,
        )
    except ValueError as exc:
        return response([], 400, str(exc))
    await _record_netdisk_audit_log(session, "upload_approve", "netdisk_upload", upload_id, payload["upload"].get("title", ""), req.note)
    return response(data=jsonable_encoder(payload), msg="netdisk upload approved")


@router.post("/netdisk/uploads/{upload_id}/reject", summary="admin reject netdisk upload")
async def admin_reject_netdisk_upload(
    upload_id: str,
    req: NetdiskAdminAuditRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        payload = await NetdiskResourceService.reject_upload(session, upload_id, req.note)
    except ValueError as exc:
        return response([], 400, str(exc))
    await _record_netdisk_audit_log(session, "upload_reject", "netdisk_upload", upload_id, payload["upload"].get("title", ""), req.note)
    return response(data=jsonable_encoder(payload), msg="netdisk upload rejected")


@router.post("/netdisk/uploads/{upload_id}/confirm-invalid", summary="admin confirm invalid netdisk upload")
async def admin_confirm_invalid_netdisk_upload(
    upload_id: str,
    req: NetdiskAdminAuditRequest,
    x_admin_role: str = Header("operator"),
    session: AsyncSession = Depends(get_session),
):
    if not _is_quality_supervisor(x_admin_role):
        return response([], 403, "仅主管可确认资源失效")
    try:
        payload = await NetdiskResourceService.confirm_upload_invalid(session, upload_id, req.note)
    except ValueError as exc:
        return response([], 400, str(exc))
    await _record_netdisk_audit_log(session, "upload_confirm_invalid", "netdisk_upload", upload_id, payload["upload"].get("title", ""), req.note)
    return response(data=jsonable_encoder(payload), msg="netdisk upload invalid confirmed")


@router.get("/netdisk/repairs", summary="admin netdisk repair/report list")
async def admin_list_netdisk_repairs(
    status: Optional[str] = Query(None),
    mode: Optional[str] = Query(None),
    repair_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    payload = await NetdiskResourceService.list_admin_repairs(
        session=session,
        status=status,
        mode=mode,
        repair_id=repair_id,
        page=page,
        page_size=page_size,
    )
    return response(data=jsonable_encoder(payload))


@router.get("/netdisk/feedbacks", summary="admin netdisk feedback ticket list")
async def admin_list_netdisk_feedbacks(
    status: Optional[str] = Query(None),
    feedback_type: Optional[str] = Query(None),
    feedback_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    payload = await NetdiskResourceService.list_admin_feedbacks(
        session=session,
        status=status,
        feedback_type=feedback_type,
        feedback_id=feedback_id,
        page=page,
        page_size=page_size,
    )
    return response(data=jsonable_encoder(payload))


@router.post("/netdisk/feedbacks/{feedback_id}/reply", summary="admin reply netdisk feedback ticket")
async def admin_reply_netdisk_feedback(
    feedback_id: str,
    req: NetdiskAdminAuditRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        payload = await NetdiskResourceService.update_admin_feedback(
            session=session,
            feedback_id=feedback_id,
            status=req.result_action or "processing",
            admin_reply=req.note,
            reward_points=req.reward_points,
        )
    except ValueError as exc:
        return response([], 400, str(exc))
    await _record_netdisk_audit_log(session, "feedback_reply", "netdisk_feedback", feedback_id, "用户反馈", req.note)
    return response(data=jsonable_encoder(payload), msg="netdisk feedback replied")


@router.post("/netdisk/feedbacks/{feedback_id}/appeal-approve", summary="approve netdisk invalid penalty appeal")
async def admin_approve_netdisk_feedback_appeal(
    feedback_id: str,
    req: NetdiskAdminAuditRequest,
    x_admin_role: str = Header("operator"),
    session: AsyncSession = Depends(get_session),
):
    if not _is_quality_supervisor(x_admin_role):
        return response([], 403, "仅主管可通过申诉并返还扣罚")
    try:
        payload = await NetdiskResourceService.approve_feedback_appeal(session, feedback_id, req.note)
    except ValueError as exc:
        return response([], 400, str(exc))
    await _record_netdisk_audit_log(
        session,
        "feedback_appeal_approved",
        "netdisk_feedback",
        feedback_id,
        "申诉通过",
        req.note,
    )
    return response(data=jsonable_encoder(payload), msg="申诉已通过，扣罚已处理")


@router.get("/netdisk/resources", summary="admin netdisk resource list")
async def admin_list_netdisk_resources(
    active: Optional[bool] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    payload = await NetdiskResourceService.list_admin_resources(
        session=session,
        active=active,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    total_all = (await session.execute(select(func.count()).select_from(NetdiskResourceModel))).scalar() or 0
    active_total = (
        await session.execute(
            select(func.count()).select_from(NetdiskResourceModel).where(NetdiskResourceModel.is_active == True)  # noqa: E712
        )
    ).scalar() or 0
    hidden_total = (
        await session.execute(
            select(func.count()).select_from(NetdiskResourceModel).where(NetdiskResourceModel.is_active == False)  # noqa: E712
        )
    ).scalar() or 0
    payload["stats"] = {
        "total": int(total_all),
        "active": int(active_total),
        "hidden": int(hidden_total),
    }
    return response(data=jsonable_encoder(payload))


@router.post("/netdisk/resources/{resource_id}/restore", summary="admin restore netdisk resource")
async def admin_restore_netdisk_resource(
    resource_id: str,
    req: NetdiskAdminAuditRequest,
    x_admin_role: str = Header("operator"),
    session: AsyncSession = Depends(get_session),
):
    if not _is_quality_supervisor(x_admin_role):
        return response([], 403, "仅主管可恢复资源上架")
    try:
        payload = await NetdiskResourceService.restore_resource(session, resource_id, req.note)
    except ValueError as exc:
        return response([], 400, str(exc))
    await _record_netdisk_audit_log(
        session,
        "resource_restore",
        "netdisk_resource",
        resource_id,
        payload["resource"].get("title", ""),
        req.note,
    )
    return response(data=jsonable_encoder(payload), msg="netdisk resource restored")


@router.post("/netdisk/resources/{resource_id}/hide", summary="admin hide netdisk resource")
async def admin_hide_netdisk_resource(
    resource_id: str,
    req: NetdiskAdminAuditRequest,
    x_admin_role: str = Header("operator"),
    session: AsyncSession = Depends(get_session),
):
    if not _is_quality_supervisor(x_admin_role):
        return response([], 403, "仅主管可删除资源")
    try:
        payload = await NetdiskResourceService.hide_resource(session, resource_id, req.note)
    except ValueError as exc:
        return response([], 400, str(exc))
    await _record_netdisk_audit_log(
        session,
        "resource_hide",
        "netdisk_resource",
        resource_id,
        payload["resource"].get("title", ""),
        req.note,
    )
    return response(data=jsonable_encoder(payload), msg="netdisk resource hidden")


@router.get("/netdisk/requests", summary="admin netdisk request bounty list")
async def admin_list_netdisk_requests(
    status: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    payload = await NetdiskResourceService.list_admin_requests(
        session=session,
        status=status,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    status_counts = (
        await session.execute(
            select(NetdiskRequest.status, func.count()).group_by(NetdiskRequest.status)
        )
    ).all()
    payload["stats"] = {str(status): int(count or 0) for status, count in status_counts}
    return response(data=jsonable_encoder(payload))


@router.post("/netdisk/requests/{request_id}/delete", summary="admin delete netdisk request bounty")
async def admin_delete_netdisk_request(
    request_id: str,
    req: NetdiskAdminAuditRequest,
    x_admin_role: str = Header("operator"),
    session: AsyncSession = Depends(get_session),
):
    if not _is_quality_supervisor(x_admin_role):
        return response([], 403, "仅主管可删除悬赏")
    try:
        payload = await NetdiskResourceService.admin_delete_request(session, request_id, req.note)
    except ValueError as exc:
        return response([], 400, str(exc))
    await _record_netdisk_audit_log(
        session,
        "request_delete",
        "netdisk_request",
        request_id,
        payload["request"].get("title", ""),
        req.note,
    )
    return response(data=jsonable_encoder(payload), msg="netdisk request deleted")


@router.post("/netdisk/requests/{request_id}/approve", summary="admin approve netdisk request bounty")
async def admin_approve_netdisk_request(
    request_id: str,
    req: NetdiskAdminAuditRequest,
    x_admin_role: str = Header("operator"),
    session: AsyncSession = Depends(get_session),
):
    if not _is_quality_supervisor(x_admin_role):
        return response([], 403, "仅主管可审核悬赏")
    try:
        payload = await NetdiskResourceService.admin_approve_request(session, request_id, req.note)
    except ValueError as exc:
        return response([], 400, str(exc))
    await _record_netdisk_audit_log(
        session,
        "request_approve",
        "netdisk_request",
        request_id,
        payload["request"].get("title", ""),
        req.note,
    )
    return response(data=jsonable_encoder(payload), msg="netdisk request approved")


@router.post("/netdisk/requests/{request_id}/reject", summary="admin reject netdisk request bounty")
async def admin_reject_netdisk_request(
    request_id: str,
    req: NetdiskAdminAuditRequest,
    x_admin_role: str = Header("operator"),
    session: AsyncSession = Depends(get_session),
):
    if not _is_quality_supervisor(x_admin_role):
        return response([], 403, "仅主管可审核悬赏")
    if not (req.note or "").strip():
        return response([], 400, "拒绝原因必填")
    try:
        payload = await NetdiskResourceService.admin_reject_request(session, request_id, req.note)
    except ValueError as exc:
        return response([], 400, str(exc))
    await _record_netdisk_audit_log(
        session,
        "request_reject",
        "netdisk_request",
        request_id,
        payload["request"].get("title", ""),
        req.note,
    )
    return response(data=jsonable_encoder(payload), msg="netdisk request rejected")


@router.get("/netdisk/resource-subscriptions", summary="admin netdisk resource subscription list")
async def admin_list_netdisk_resource_subscriptions(
    status: Optional[str] = Query(None),
    wx_subscribe_status: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    payload = await NetdiskResourceService.list_admin_resource_subscriptions(
        session=session,
        status=status,
        wx_subscribe_status=wx_subscribe_status,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return response(data=jsonable_encoder(payload))


@router.get("/netdisk/resource-subscription-push-logs", summary="admin netdisk resource subscription push logs")
async def admin_list_netdisk_resource_subscription_push_logs(
    subscription_id: Optional[str] = Query(None),
    resource_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    payload = await NetdiskResourceService.list_admin_subscription_push_logs(
        session=session,
        subscription_id=subscription_id,
        resource_id=resource_id,
        status=status,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return response(data=jsonable_encoder(payload))


@router.post("/netdisk/resources/restore-hidden-kdocs", summary="admin restore hidden kdocs resources")
async def admin_restore_hidden_kdocs_resources(
    req: NetdiskAdminAuditRequest,
    x_admin_role: str = Header("operator"),
    session: AsyncSession = Depends(get_session),
):
    if not _is_quality_supervisor(x_admin_role):
        return response([], 403, "仅主管可批量恢复资源")
    payload = await NetdiskResourceService.restore_hidden_kdocs_resources(session, req.note)
    await _record_netdisk_audit_log(
        session,
        "resource_bulk_restore_kdocs",
        "netdisk_resource",
        "kdocs:hidden",
        "批量恢复 KDocs 历史资源",
        f"{req.note}；恢复 {payload.get('restored_count', 0)} 条",
    )
    return response(data=jsonable_encoder(payload), msg="hidden kdocs resources restored")


@router.get("/netdisk/resources/cleanup-hidden-duplicates/preview", summary="preview hidden duplicate resource cleanup")
async def admin_preview_hidden_duplicate_cleanup(
    session: AsyncSession = Depends(get_session),
):
    payload = await NetdiskResourceService.cleanup_hidden_duplicate_resources(session, execute=False)
    return response(data=jsonable_encoder(payload))


@router.post("/netdisk/resources/cleanup-hidden-duplicates", summary="cleanup hidden duplicate resources")
async def admin_cleanup_hidden_duplicate_resources(
    req: NetdiskAdminAuditRequest,
    x_admin_role: str = Header("operator"),
    session: AsyncSession = Depends(get_session),
):
    if not _is_quality_supervisor(x_admin_role):
        return response([], 403, "仅主管可清理隐藏重复资源")
    payload = await NetdiskResourceService.cleanup_hidden_duplicate_resources(session, execute=True, note=req.note)
    await _record_netdisk_audit_log(
        session,
        "resource_cleanup_hidden_duplicates",
        "netdisk_resource",
        "hidden:duplicates",
        "清理隐藏重复资源",
        f"{req.note}；删除 {payload.get('deleted_count', 0)} 条，保护 {payload.get('protected_count', 0)} 条",
    )
    return response(data=jsonable_encoder(payload), msg="hidden duplicate resources cleaned")


@router.post("/netdisk/resources/{resource_id}/confirm-invalid", summary="admin confirm invalid netdisk resource")
async def admin_confirm_netdisk_resource_invalid(
    resource_id: str,
    req: NetdiskAdminAuditRequest,
    x_admin_role: str = Header("operator"),
    session: AsyncSession = Depends(get_session),
):
    if not _is_quality_supervisor(x_admin_role):
        return response([], 403, "仅主管可确认资源失效")
    try:
        payload = await NetdiskResourceService.confirm_resource_invalid(session, resource_id, req.note)
    except ValueError as exc:
        return response([], 400, str(exc))
    await _record_netdisk_audit_log(
        session,
        "resource_confirm_invalid",
        "netdisk_resource",
        resource_id,
        payload["resource"].get("title", ""),
        req.note,
    )
    return response(data=jsonable_encoder(payload), msg="netdisk resource invalid confirmed")


@router.get("/netdisk/risk-records", summary="admin netdisk pending recovery list")
async def admin_list_netdisk_risk_records(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    payload = await NetdiskResourceService.list_risk_records(
        session=session,
        status=status,
        page=page,
        page_size=page_size,
    )
    return response(data=jsonable_encoder(payload))


@router.post("/netdisk/uploads/release-valid-7d-rewards", summary="release valid 7d upload rewards")
async def admin_release_netdisk_valid_7d_rewards(
    limit: int = Query(200, ge=1, le=1000),
    x_admin_role: str = Header("operator"),
    session: AsyncSession = Depends(get_session),
):
    if not _is_quality_supervisor(x_admin_role):
        return response([], 403, "仅主管可释放长期有效奖励")
    payload = await NetdiskResourceService.release_valid_7d_upload_rewards(session, limit)
    await _record_netdisk_audit_log(
        session,
        "upload_valid_7d_rewards_release",
        "netdisk_upload",
        "batch",
        "7天有效奖励释放",
        f"释放 {payload.get('released_count', 0)} 条，{payload.get('released_points', 0)} 分",
    )
    return response(data=jsonable_encoder(payload), msg="netdisk valid 7d rewards released")


@router.get("/netdisk/risk-records/{record_id}", summary="admin netdisk pending recovery detail")
async def admin_get_netdisk_risk_record_detail(
    record_id: str,
    session: AsyncSession = Depends(get_session),
):
    try:
        uid = UUID(record_id)
    except ValueError:
        return response([], 400, "invalid risk record id")
    item = await session.get(NetdiskRiskRecord, uid)
    if not item:
        return response([], 404, "risk record not found")
    account, _ = await PointsAccountService.ensure_user_account(session, item.user_id)
    related = await _build_netdisk_risk_related_detail(session, item)
    notifications = (
        await session.execute(
            select(NetdiskUserNotification)
            .where(
                NetdiskUserNotification.user_id == item.user_id,
                NetdiskUserNotification.related_type == item.related_type,
                NetdiskUserNotification.related_id == item.related_id,
            )
            .order_by(NetdiskUserNotification.created_at.desc())
            .limit(20)
        )
    ).scalars().all()
    consumable_points = int(account.consumable_points or 0)
    points_due = int(item.points_due or 0)
    return response(
        data={
            "risk_record": _netdisk_risk_record_to_dict(item),
            "account": {
                "consumable_points": consumable_points,
                "frozen_points": int(account.frozen_points or 0),
                "total_points": int(account.total_points or 0),
            },
            "collect_preview": {
                "will_collect": min(points_due, consumable_points),
                "shortfall_after_collect": max(points_due - consumable_points, 0),
            },
            "related": related,
            "notifications": [_netdisk_user_notification_to_dict(row) for row in notifications],
        }
    )


@router.post("/netdisk/risk-records/{record_id}/collect", summary="collect netdisk pending recovery points")
async def admin_collect_netdisk_risk_record(
    record_id: str,
    req: NetdiskAdminAuditRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        payload = await _collect_netdisk_risk_record(session, record_id, req.note)
    except ValueError as exc:
        return response([], 400, str(exc))
    await _record_netdisk_audit_log(
        session,
        "risk_collect",
        "netdisk_risk_record",
        record_id,
        payload["risk_record"].get("related_id", ""),
        req.note,
    )
    return response(data=jsonable_encoder(payload), msg="netdisk risk record collected")


@router.post("/netdisk/risk-records/{record_id}/waive", summary="waive netdisk pending recovery points")
async def admin_waive_netdisk_risk_record(
    record_id: str,
    req: NetdiskAdminAuditRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        payload = await _waive_netdisk_risk_record(session, record_id, req.note)
    except ValueError as exc:
        return response([], 400, str(exc))
    await _record_netdisk_audit_log(
        session,
        "risk_waive",
        "netdisk_risk_record",
        record_id,
        payload["risk_record"].get("related_id", ""),
        req.note,
    )
    return response(data=jsonable_encoder(payload), msg="netdisk risk record waived")


@router.get("/netdisk/audit-logs", summary="admin netdisk audit operation logs")
async def admin_list_netdisk_audit_logs(
    action: Optional[str] = Query(None),
    target_type: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    try:
        start_dt, end_dt = _parse_date_range(start_date, end_date)
    except ValueError:
        return response([], 400, "invalid date format, expected YYYY-MM-DD")
    query = _build_netdisk_audit_log_query(action, target_type, start_dt, end_dt)

    total = (await session.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
    items = (
        await session.execute(
            query.order_by(NetdiskAuditLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return response(
        data={
            "logs": [_netdisk_audit_log_to_dict(item) for item in items],
            "total": int(total),
            "page": page,
            "page_size": page_size,
            "has_more": ((page - 1) * page_size + len(items)) < total,
        }
    )


@router.get("/netdisk/audit-logs/export", summary="export netdisk audit operation logs")
async def admin_export_netdisk_audit_logs(
    action: Optional[str] = Query(None),
    target_type: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    try:
        start_dt, end_dt = _parse_date_range(start_date, end_date)
    except ValueError:
        return response([], 400, "invalid date format, expected YYYY-MM-DD")
    query = _build_netdisk_audit_log_query(action, target_type, start_dt, end_dt)
    items = (await session.execute(query.order_by(NetdiskAuditLog.created_at.desc()).limit(5000))).scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["时间", "管理员", "动作", "对象类型", "对象ID", "标题", "备注", "结果"])
    for item in items:
        writer.writerow(
            [
                item.created_at.isoformat() if item.created_at else "",
                item.admin_name,
                item.action,
                item.target_type,
                item.target_id,
                item.target_title,
                item.note,
                item.result,
            ]
        )
    filename = f"netdisk-audit-logs-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.csv"
    return Response(
        content="\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/netdisk/audit-config", summary="get netdisk audit config")
async def admin_get_netdisk_audit_config(session: AsyncSession = Depends(get_session)):
    config = await ConfigService.get(session, "netdisk_audit_config")
    return response(data=config)


@router.get("/netdisk/ops-dashboard", summary="netdisk operations dashboard")
async def admin_netdisk_ops_dashboard(
    points_range: str = Query("today", pattern="^(today|7d)$"),
    quality_range: str = Query("7d", pattern="^(today|7d|all)$"),
    session: AsyncSession = Depends(get_session),
):
    today_start, _ = bj_day_bounds_utc()
    point_source_start = today_start - timedelta(days=6) if points_range == "7d" else today_start

    total_users = (await session.execute(select(func.count()).select_from(User))).scalar() or 0
    today_new_users = (
        await session.execute(select(func.count()).select_from(User).where(User.created_at >= today_start))
    ).scalar() or 0
    total_share_friends = (
        await session.execute(select(func.count()).select_from(InviteRelation))
    ).scalar() or 0
    today_share_friends = (
        await session.execute(select(func.count()).select_from(InviteRelation).where(InviteRelation.created_at >= today_start))
    ).scalar() or 0

    business_points_filter = or_(PointsLedger.source.is_(None), PointsLedger.source != "admin_adjust")
    points_gain = (
        await session.execute(
            select(
                func.count(func.distinct(PointsLedger.user_id)),
                func.coalesce(func.sum(PointsLedger.points_delta), 0),
            ).where(PointsLedger.created_at >= today_start, PointsLedger.points_delta > 0, business_points_filter)
        )
    ).one()
    points_spend = (
        await session.execute(
            select(
                func.count(func.distinct(PointsLedger.user_id)),
                func.coalesce(func.sum(PointsLedger.points_delta), 0),
            ).where(PointsLedger.created_at >= today_start, PointsLedger.points_delta < 0, business_points_filter)
        )
    ).one()
    admin_adjust_gain = (
        await session.execute(
            select(
                func.count(func.distinct(PointsLedger.user_id)),
                func.coalesce(func.sum(PointsLedger.points_delta), 0),
            ).where(
                PointsLedger.created_at >= today_start,
                PointsLedger.points_delta > 0,
                PointsLedger.source == "admin_adjust",
            )
        )
    ).one()
    admin_adjust_spend = (
        await session.execute(
            select(
                func.count(func.distinct(PointsLedger.user_id)),
                func.coalesce(func.sum(PointsLedger.points_delta), 0),
            ).where(
                PointsLedger.created_at >= today_start,
                PointsLedger.points_delta < 0,
                PointsLedger.source == "admin_adjust",
            )
        )
    ).one()

    account_totals = (
        await session.execute(
            select(
                func.coalesce(func.sum(UserAccount.consumable_points), 0),
                func.coalesce(func.sum(UserAccount.frozen_points), 0),
            )
        )
    ).one()

    pending_uploads = (
        await session.execute(
            select(func.count()).select_from(NetdiskUpload).where(NetdiskUpload.status == "pending")
        )
    ).scalar() or 0
    pending_repairs = (
        await session.execute(
            select(func.count()).select_from(NetdiskRepair).where(
                NetdiskRepair.status == "pending",
                NetdiskRepair.mode == "repair",
            )
        )
    ).scalar() or 0
    pending_reports = (
        await session.execute(
            select(func.count()).select_from(NetdiskRepair).where(
                NetdiskRepair.status == "pending",
                NetdiskRepair.mode == "report",
            )
        )
    ).scalar() or 0
    hidden_resources = (
        await session.execute(
            select(func.count()).select_from(NetdiskResourceModel).where(NetdiskResourceModel.is_active == False)  # noqa: E712
        )
    ).scalar() or 0
    total_resources = (
        await session.execute(
            select(func.count()).select_from(NetdiskResourceModel)
        )
    ).scalar() or 0
    risk_totals = (
        await session.execute(
            select(
                func.count(),
                func.coalesce(func.sum(NetdiskRiskRecord.points_due), 0),
            )
            .select_from(NetdiskRiskRecord)
            .where(NetdiskRiskRecord.status == "open")
        )
    ).one()
    today_uploads = (
        await session.execute(
            select(func.count()).select_from(NetdiskUpload).where(NetdiskUpload.created_at >= today_start)
        )
    ).scalar() or 0
    today_repairs = (
        await session.execute(
            select(func.count()).select_from(NetdiskRepair).where(
                NetdiskRepair.created_at >= today_start,
                NetdiskRepair.mode == "repair",
            )
        )
    ).scalar() or 0
    today_reports = (
        await session.execute(
            select(func.count()).select_from(NetdiskRepair).where(
                NetdiskRepair.created_at >= today_start,
                NetdiskRepair.mode == "report",
            )
        )
    ).scalar() or 0
    today_resources = (
        await session.execute(
            select(func.count()).select_from(NetdiskResourceModel).where(NetdiskResourceModel.created_at >= today_start)
        )
    ).scalar() or 0
    resource_update_stats = (
        await session.execute(
            select(
                func.count(),
                func.max(NetdiskResourceModel.verified_at),
            )
            .select_from(NetdiskResourceModel)
            .where(NetdiskResourceModel.verified_at >= today_start)
        )
    ).one()
    trends = await _build_netdisk_ops_trends(session, today_start)
    point_sources = await _build_point_source_distribution(session, point_source_start)
    point_spend_users = await _build_today_point_spend_users(session, today_start)
    resource_quality_rankings = await _build_resource_quality_rankings(session, range_mode=quality_range)
    quality_alerts = await _build_resource_quality_alerts(session)
    quality_review_pool_count = (
        await session.execute(
            select(func.count())
            .select_from(NetdiskQualityAlert)
            .where(NetdiskQualityAlert.status.in_(["open", "read"]))
        )
    ).scalar() or 0
    quality_runtime = await ConfigService.get(session, "netdisk_quality_stats_runtime")

    return response(
        data={
            "users": {
                "total": int(total_users),
                "today_new": int(today_new_users),
            },
            "invites": {
                "today_share_friends": int(today_share_friends),
                "total_share_friends": int(total_share_friends),
            },
            "resources": {
                "today_new": int(today_resources),
                "today_updated": int(resource_update_stats[0] or 0),
                "total": int(total_resources),
                "latest_verified_at": resource_update_stats[1].isoformat() if resource_update_stats[1] else None,
            },
            "points": {
                "today_gain_users": int(points_gain[0] or 0),
                "today_gain_points": int(points_gain[1] or 0),
                "today_spend_users": int(points_spend[0] or 0),
                "today_spend_points": abs(int(points_spend[1] or 0)),
                "admin_adjust_gain_users": int(admin_adjust_gain[0] or 0),
                "admin_adjust_gain_points": int(admin_adjust_gain[1] or 0),
                "admin_adjust_spend_users": int(admin_adjust_spend[0] or 0),
                "admin_adjust_spend_points": abs(int(admin_adjust_spend[1] or 0)),
                "consumable_total": int(account_totals[0] or 0),
                "frozen_total": int(account_totals[1] or 0),
                "risk_due_total": int(risk_totals[1] or 0),
            },
            "workbench": {
                "pending_uploads": int(pending_uploads),
                "pending_repairs": int(pending_repairs),
                "pending_reports": int(pending_reports),
                "hidden_resources": int(hidden_resources),
                "open_risk_records": int(risk_totals[0] or 0),
                "quality_alerts": len(quality_alerts),
                "quality_review_pool": int(quality_review_pool_count),
            },
            "today_activity": {
                "resources": int(today_resources),
                "resource_updates": int(resource_update_stats[0] or 0),
                "uploads": int(today_uploads),
                "repairs": int(today_repairs),
                "reports": int(today_reports),
            },
            "trends": trends,
            "point_source_range": points_range,
            "point_sources": point_sources,
            "point_spend_users": point_spend_users,
            "quality_range": quality_range,
            "resource_quality_rankings": resource_quality_rankings,
            "resource_quality_alerts": quality_alerts,
            "quality_stats_runtime": quality_runtime,
            "generated_at": datetime.utcnow().isoformat(),
        }
    )


@router.get("/netdisk/crawlers/status", summary="netdisk crawler rules and status")
async def admin_netdisk_crawler_status(session: AsyncSession = Depends(get_session)):
    kdocs_limit = int(os.getenv("KDOCS_SYNC_LIMIT_PER_TYPE", "20"))
    linuxdo_limit = int(os.getenv("LINUXDO_SYNC_LIMIT", "20"))
    anime_interval = int(os.getenv("ANIME_SYNC_INTERVAL", "60"))
    linuxdo_interval = int(os.getenv("LINUXDO_SYNC_INTERVAL_HOURS", "12"))

    kdocs_count = (
        await session.execute(
            select(func.count()).select_from(NetdiskResourceModel).where(NetdiskResourceModel.source_type == "kdocs")
        )
    ).scalar() or 0
    linuxdo_count = (
        await session.execute(
            select(func.count()).select_from(NetdiskResourceModel).where(NetdiskResourceModel.source_type == "linuxdo")
        )
    ).scalar() or 0
    linuxdo_pending = (
        await session.execute(
            select(func.count())
            .select_from(NetdiskCollectedResource)
            .where(NetdiskCollectedResource.source_type == "linuxdo", NetdiskCollectedResource.status == "pending")
        )
    ).scalar() or 0

    crawlers = [
        {
            "key": "kdocs_anime",
            "name": "KDocs 影视剧",
            "source": "kdocs",
            "schedule": "每小时 30 分" if anime_interval == 60 else f"每 {anime_interval} 分钟",
            "limit_text": f"最新日期分组最多 {kdocs_limit} 条",
            "enabled": os.getenv("ANIME_SYNC_ENABLED", "true").lower() == "true",
            "published_count": int(kdocs_count),
            "pending_count": 0,
            "note": "只取最新日期分组，不足 20 条不补旧数据",
        },
        {
            "key": "kdocs_movie",
            "name": "KDocs 电影",
            "source": "kdocs",
            "schedule": "每天 00:00",
            "limit_text": f"最新日期分组最多 {kdocs_limit} 条",
            "enabled": os.getenv("ANIME_SYNC_ENABLED", "true").lower() == "true",
            "published_count": int(kdocs_count),
            "pending_count": 0,
            "note": "与 4K 同一批定时任务",
        },
        {
            "key": "kdocs_4k",
            "name": "KDocs 4K影视",
            "source": "kdocs",
            "schedule": "每天 00:00",
            "limit_text": f"最新日期分组最多 {kdocs_limit} 条",
            "enabled": os.getenv("ANIME_SYNC_ENABLED", "true").lower() == "true",
            "published_count": int(kdocs_count),
            "pending_count": 0,
            "note": "与电影同一批定时任务",
        },
        {
            "key": "linuxdo",
            "name": "LinuxDo 云资产",
            "source": "linuxdo",
            "schedule": f"每 {linuxdo_interval} 小时",
            "limit_text": f"最新 {linuxdo_limit} 条",
            "enabled": os.getenv("LINUXDO_SYNC_ENABLED", "true").lower() == "true",
            "published_count": int(linuxdo_count),
            "pending_count": int(linuxdo_pending),
            "note": "高置信自动入库，低置信进入待审核",
        },
    ]
    worker_status = await _fetch_crawler_worker_status()
    return response(
        data={
            "crawlers": crawlers,
            "worker": {
                "mode": "independent",
                "url": os.getenv("CRAWLER_WORKER_URL", "http://crawler-worker:8010"),
                "note": "浏览器采集运行在独立 worker，主 API 不安装 Chromium",
                **worker_status,
            },
            "browser_guard": {
                "concurrency": int(os.getenv("BROWSER_AUTOMATION_CONCURRENCY", "1")),
                "force_cleanup": os.getenv("BROWSER_FORCE_CLEANUP", "true").lower() != "false",
                "browser_processes": int(worker_status.get("browser_processes") or 0),
                "browser_process_limit": int(worker_status.get("browser_process_limit") or 0),
                "browser_stale_seconds": int(worker_status.get("browser_stale_seconds") or 0),
            },
            "generated_at": datetime.utcnow().isoformat(),
        }
    )


async def _fetch_crawler_worker_status() -> dict:
    worker_url = os.getenv("CRAWLER_WORKER_URL", "http://crawler-worker:8010").rstrip("/")
    try:
        import httpx

        async with httpx.AsyncClient(timeout=5) as client:
            worker_resp = await client.get(f"{worker_url}/status")
            worker_resp.raise_for_status()
        payload = worker_resp.json()
        return {
            "reachable": True,
            "status": payload.get("status", "ok"),
            "service": payload.get("service", "crawler-worker"),
            "chromium": payload.get("chromium", ""),
            "browser_processes": payload.get("browser_processes", 0),
            "browser_process_limit": payload.get("browser_process_limit", 0),
            "browser_stale_seconds": payload.get("browser_stale_seconds", 0),
            "auto_cleaned": payload.get("auto_cleaned", 0),
            "task_timeout_seconds": payload.get("task_timeout_seconds", 0),
            "failure_breaker_threshold": payload.get("failure_breaker_threshold", 0),
            "failure_breaker_cooldown_seconds": payload.get("failure_breaker_cooldown_seconds", 0),
            "running_tasks": payload.get("running_tasks", []),
            "blocked_tasks": payload.get("blocked_tasks", []),
            "tasks": payload.get("tasks", []),
            "recent_runs": payload.get("recent_runs", []),
            "scheduler_jobs": payload.get("scheduler_jobs", []),
        }
    except Exception as exc:
        logger.warning("crawler worker status unavailable: %s", exc)
        fallback = await _build_crawler_worker_fallback_status()
        return {
            "reachable": False,
            **fallback,
            "service": "crawler-worker",
            "error": str(exc),
            "browser_processes": 0,
            "browser_process_limit": 0,
            "browser_stale_seconds": 0,
        }


@router.post("/netdisk/crawlers/maintenance/cleanup-browsers", summary="cleanup crawler worker browser processes")
async def admin_cleanup_crawler_browsers(x_admin_role: str = Header("operator")):
    if not _is_quality_supervisor(x_admin_role):
        return response([], 403, "需要主管权限才能清理浏览器进程")

    try:
        import httpx

        worker_url = os.getenv("CRAWLER_WORKER_URL", "http://crawler-worker:8010").rstrip("/")
        async with httpx.AsyncClient(timeout=30) as client:
            worker_resp = await client.post(f"{worker_url}/maintenance/cleanup-browsers")
            worker_resp.raise_for_status()
        worker_payload = worker_resp.json()
        if worker_payload.get("code") not in {0, 200, None}:
            return response(worker_payload.get("data", []), 500, worker_payload.get("msg") or "清理失败")
        return response(data=worker_payload.get("data", worker_payload), msg=worker_payload.get("msg") or "浏览器进程清理完成")
    except Exception as exc:
        logger.error("crawler browser cleanup failed: %s", exc, exc_info=True)
        return response([], 500, f"清理失败：{exc}")


@router.post("/netdisk/crawlers/{crawler_key}/run", summary="run one netdisk crawler latest batch")
async def admin_run_netdisk_crawler(
    crawler_key: str,
    x_admin_role: str = Header("operator"),
):
    if not _is_quality_supervisor(x_admin_role):
        return response([], 403, "需要主管权限才能手动触发采集")

    try:
        if crawler_key not in {"kdocs_anime", "kdocs_movie", "kdocs_4k", "linuxdo"}:
            return response([], 400, "未知采集任务")
        import httpx

        worker_url = os.getenv("CRAWLER_WORKER_URL", "http://crawler-worker:8010").rstrip("/")
        async with httpx.AsyncClient(timeout=300) as client:
            worker_resp = await client.post(f"{worker_url}/run/{crawler_key}")
            worker_resp.raise_for_status()
        worker_payload = worker_resp.json()
        if worker_payload.get("code") not in {0, 200, None}:
            return response(worker_payload.get("data", []), 500, worker_payload.get("msg") or "采集失败")
        result = worker_payload.get("data", worker_payload)
    except Exception as exc:
        logger.error("manual crawler run failed: %s", exc, exc_info=True)
        return response([], 500, f"采集失败：{exc}")

    return response(data=result, msg="采集任务已完成")


@router.get("/netdisk/collected-resources", summary="admin collected resource review pool")
async def admin_list_netdisk_collected_resources(
    status: str = Query("pending"),
    bucket: str = Query("all"),
    keyword: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    payload = await NetdiskResourceService.list_admin_collected_resources(
        session,
        status=status,
        bucket=bucket,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return response(data=jsonable_encoder(payload), msg="采集待审核池")


@router.post("/netdisk/collected-resources/{candidate_id}/{action}", summary="handle collected resource candidate")
async def admin_handle_netdisk_collected_resource(
    candidate_id: str,
    action: str,
    req: NetdiskAdminAuditRequest,
    x_admin_role: str = Header("operator"),
    session: AsyncSession = Depends(get_session),
):
    if not _is_quality_supervisor(x_admin_role):
        return response([], 403, "需要主管权限才能处理采集候选")
    if action not in {"approve", "skip", "merge"}:
        return response([], 400, "未知处理动作")
    try:
        payload = await NetdiskResourceService.handle_admin_collected_resource(
            session,
            candidate_id,
            action,  # type: ignore[arg-type]
            note=req.note,
        )
    except ValueError as exc:
        return response([], 400, str(exc))
    await _record_netdisk_audit_log(
        session,
        f"collected_{action}",
        "netdisk_collected_resource",
        candidate_id,
        payload.get("candidate", {}).get("title", "采集候选"),
        req.note,
    )
    return response(data=jsonable_encoder(payload), msg="采集候选已处理")


@router.post("/netdisk/collected-resources/bulk-action", summary="bulk handle collected resource candidates")
async def admin_bulk_handle_netdisk_collected_resources(
    req: NetdiskCollectedBulkActionRequest,
    x_admin_role: str = Header("operator"),
    session: AsyncSession = Depends(get_session),
):
    if not _is_quality_supervisor(x_admin_role):
        return response([], 403, "需要主管权限才能批量处理采集候选")
    if req.action not in {"approve", "skip", "merge"}:
        return response([], 400, "未知处理动作")
    try:
        payload = await NetdiskResourceService.bulk_handle_admin_collected_resources(
            session=session,
            action=req.action,  # type: ignore[arg-type]
            ids=req.ids,
            all_matching=req.all_matching,
            status=req.status,
            bucket=req.bucket,
            keyword=req.keyword,
            note=req.note,
        )
    except ValueError as exc:
        return response([], 400, str(exc))
    await _record_netdisk_audit_log(
        session,
        f"collected_bulk_{req.action}",
        "netdisk_collected_resource",
        "bulk",
        f"批量处理 {payload.get('handled', 0)} 条采集候选",
        req.note,
    )
    return response(data=jsonable_encoder(payload), msg="批量处理完成")


@router.post("/netdisk/collected-resources/import", summary="import collected resources from file")
async def admin_import_netdisk_collected_resources(
    file: UploadFile = File(...),
    source_type: str = Query("manual"),
    x_admin_role: str = Header("operator"),
    session: AsyncSession = Depends(get_session),
):
    if not _is_quality_supervisor(x_admin_role):
        return response([], 403, "需要主管权限才能导入资源文件")
    filename = file.filename or ""
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix not in {"json", "csv"}:
        return response([], 400, "只支持 JSON 或 CSV 文件")
    raw = await file.read()
    if len(raw) > 2 * 1024 * 1024:
        return response([], 400, "文件不能超过 2MB")
    try:
        rows, parse_failed_rows = _parse_netdisk_import_file(raw, suffix, source_type)
        if not rows:
            batch = _create_import_batch(
                filename,
                source_type,
                x_admin_role,
                total_rows=0,
                payload={"failed": len(parse_failed_rows), "failed_rows": parse_failed_rows, "error": "文件里没有可导入的数据"},
            )
            session.add(batch)
            await session.commit()
            return response([], 400, "文件里没有可导入的数据")
        from services.linuxdo_resource_service import ingest_linuxdo_rows

        payload = await ingest_linuxdo_rows(session, rows)
        failed_rows = [*parse_failed_rows, *payload.get("failed_rows", [])]
        payload["failed"] = len(failed_rows)
        payload["failed_rows"] = failed_rows
        batch = _create_import_batch(
            filename,
            source_type,
            x_admin_role,
            total_rows=len(rows) + len(parse_failed_rows),
            payload=payload,
        )
        session.add(batch)
        await _record_netdisk_audit_log(
            session,
            "collected_file_import",
            "netdisk_collected_resource",
            filename,
            "批量导入资源",
            f"来源 {source_type}，导入 {len(rows)} 条",
        )
        await session.commit()
    except Exception as exc:
        logger.error("netdisk collected import failed: %s", exc, exc_info=True)
        await session.rollback()
        batch = _create_import_batch(
            filename,
            source_type,
            x_admin_role,
            total_rows=0,
            payload={"failed": 1, "failed_rows": [{"row_index": 0, "reason": str(exc), "title": "", "link": "", "raw": {}}], "error": str(exc)},
        )
        batch.status = "failed"
        session.add(batch)
        await session.commit()
        return response([], 400, f"导入失败：{exc}")

    return response(data=jsonable_encoder({"batch": _build_import_batch_payload(batch), "filename": filename, "source_type": source_type, **payload}), msg="文件导入完成")


@router.get("/netdisk/collected-resources/import-batches", summary="list collected resource import batches")
async def admin_list_netdisk_import_batches(
    source_type: str = Query("all"),
    status: str = Query("all"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    query = select(NetdiskImportBatch)
    if source_type and source_type != "all":
        query = query.where(NetdiskImportBatch.source_type == source_type)
    if status and status != "all":
        query = query.where(NetdiskImportBatch.status == status)
    total = (await session.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
    items = (
        await session.execute(
            query.order_by(NetdiskImportBatch.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return response(
        data=jsonable_encoder(
            {
                "import_batches": [_build_import_batch_payload(item) for item in items],
                "total": int(total),
                "page": page,
                "page_size": page_size,
                "has_more": page * page_size < int(total),
            }
        ),
        msg="导入记录列表",
    )


@router.get("/netdisk/collected-resources/import-batches/{batch_id}/failed.csv", summary="download import failed rows")
async def admin_download_netdisk_import_failed_rows(
    batch_id: str,
    x_admin_role: str = Header("operator"),
    session: AsyncSession = Depends(get_session),
):
    if not _is_quality_supervisor(x_admin_role):
        return response([], 403, "需要主管权限才能下载失败明细")
    try:
        item_id = UUID(batch_id)
    except ValueError:
        return response([], 400, "导入记录不存在")
    batch = await session.get(NetdiskImportBatch, item_id)
    if not batch:
        return response([], 404, "导入记录不存在")
    failed_rows = _parse_failed_rows(batch.failed_rows)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["row_index", "reason", "title", "link", "raw"])
    writer.writeheader()
    for row in failed_rows:
        writer.writerow(
            {
                "row_index": row.get("row_index", ""),
                "reason": row.get("reason", ""),
                "title": row.get("title", ""),
                "link": row.get("link", ""),
                "raw": json.dumps(row.get("raw", {}), ensure_ascii=False),
            }
        )
    content = "\ufeff" + output.getvalue()
    filename = f"netdisk-import-failed-{str(batch.id)[:8]}.csv"
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/netdisk/resource-quality", summary="netdisk resource quality ranking")
async def admin_list_netdisk_resource_quality(
    filter: str = Query("all", pattern="^(all|hidden|high_report|high_unlock)$"),
    range: str = Query("7d", pattern="^(today|7d|all)$"),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    thresholds = await _get_resource_quality_thresholds(session)
    rankings = await _build_resource_quality_rankings(
        session,
        filter_mode=filter,
        range_mode=range,
        limit=page_size,
        thresholds=thresholds,
    )
    return response(data={"rankings": rankings, "filter": filter, "range": range, "thresholds": thresholds})


@router.get("/netdisk/quality-alerts", summary="netdisk quality alert list")
async def admin_list_netdisk_quality_alerts(
    status: Optional[str] = Query(None),
    review_pool: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    query = select(NetdiskQualityAlert)
    if review_pool:
        query = query.where(NetdiskQualityAlert.status.in_(["open", "read"]))
    elif status:
        query = query.where(NetdiskQualityAlert.status == status)
    total = (await session.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
    items = (
        await session.execute(
            query.order_by(NetdiskQualityAlert.last_triggered_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return response(
        data={
            "alerts": [_quality_alert_to_dict(item) for item in items],
            "total": int(total),
            "page": page,
            "page_size": page_size,
            "has_more": ((page - 1) * page_size + len(items)) < total,
        }
    )


@router.get("/netdisk/quality-review-pool", summary="netdisk quality review pool")
async def admin_list_netdisk_quality_review_pool(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    return await admin_list_netdisk_quality_alerts(
        status=None,
        review_pool=True,
        page=page,
        page_size=page_size,
        session=session,
    )


@router.get("/netdisk/resource-quality/stats-runtime", summary="netdisk quality stats runtime")
async def admin_get_netdisk_resource_quality_stats_runtime(session: AsyncSession = Depends(get_session)):
    runtime = await ConfigService.get(session, "netdisk_quality_stats_runtime")
    return response(data=runtime)


@router.post("/netdisk/resource-quality/stats-runtime/dev-simulate-failure", summary="simulate netdisk quality stats failure")
async def admin_simulate_netdisk_resource_quality_stats_failure(session: AsyncSession = Depends(get_session)):
    if os.getenv("ENABLE_DEV_LOGIN", "false").lower() != "true":
        return response([], 403, "dev simulate disabled")
    now = datetime.utcnow().isoformat()
    config = await ConfigService.set(
        session,
        "netdisk_quality_stats_runtime",
        {
            "status": "failed",
            "last_started_at": now,
            "last_finished_at": now,
            "last_rows": 0,
            "days": 7,
            "last_error": "开发自测：模拟质量统计任务失败",
            "duration_ms": 0,
            "schedule": {
                "enabled": True,
                "hour": int(os.getenv("NETDISK_QUALITY_STATS_CRON_HOUR", "3")),
                "minute": int(os.getenv("NETDISK_QUALITY_STATS_CRON_MINUTE", "20")),
            },
        },
    )
    return response(data=config.config_data, msg="netdisk quality stats runtime simulated failed")


@router.post("/netdisk/resource-quality/stats-runtime/dev-recover", summary="recover netdisk quality stats runtime")
async def admin_recover_netdisk_resource_quality_stats_runtime(session: AsyncSession = Depends(get_session)):
    if os.getenv("ENABLE_DEV_LOGIN", "false").lower() != "true":
        return response([], 403, "dev recover disabled")
    rows = await refresh_netdisk_quality_daily_stats(session)
    runtime = await ConfigService.get(session, "netdisk_quality_stats_runtime")
    return response(data={**runtime, "rows": rows}, msg="netdisk quality stats runtime recovered")


@router.get("/netdisk/resource-quality/{resource_id}", summary="netdisk resource quality detail")
async def admin_get_netdisk_resource_quality_detail(
    resource_id: str,
    session: AsyncSession = Depends(get_session),
):
    resource = await session.get(NetdiskResourceModel, resource_id)
    if not resource:
        return response([], 404, "resource not found")

    stat = await _build_resource_quality_stat(session, resource)
    reports = (
        await session.execute(
            select(NetdiskRepair)
            .where(NetdiskRepair.resource_id == resource_id, NetdiskRepair.mode == "report")
            .order_by(NetdiskRepair.created_at.desc())
            .limit(30)
        )
    ).scalars().all()
    restore_logs = (
        await session.execute(
            select(NetdiskAuditLog)
            .where(
                NetdiskAuditLog.target_type == "netdisk_resource",
                NetdiskAuditLog.target_id == resource_id,
                NetdiskAuditLog.action == "resource_restore",
            )
            .order_by(NetdiskAuditLog.created_at.desc())
            .limit(20)
        )
    ).scalars().all()
    unlocks = (
        await session.execute(
            select(PointsLedger)
            .where(
                PointsLedger.source == "netdisk",
                PointsLedger.change_type == "resource_unlock",
                PointsLedger.related_type == "netdisk_resource",
                PointsLedger.related_id == resource_id,
            )
            .order_by(PointsLedger.created_at.desc())
            .limit(30)
        )
    ).scalars().all()
    report_ids = [str(item.id) for item in reports]
    log_filters = [and_(NetdiskAuditLog.target_type == "netdisk_resource", NetdiskAuditLog.target_id == resource_id)]
    if report_ids:
        log_filters.append(and_(NetdiskAuditLog.target_type == "netdisk_repair", NetdiskAuditLog.target_id.in_(report_ids)))
    recent_logs = (
        await session.execute(
            select(NetdiskAuditLog)
            .where(or_(*log_filters))
            .order_by(NetdiskAuditLog.created_at.desc())
            .limit(30)
        )
    ).scalars().all()

    return response(
        data={
            "resource": _resource_quality_resource_to_dict(resource),
            "stats": stat,
            "alerts": await _list_resource_quality_alerts(session, resource_id),
            "trends": await _build_resource_quality_trends(session, resource_id),
            "reports": [_netdisk_repair_to_dict(item) for item in reports],
            "restore_logs": [_netdisk_audit_log_to_dict(item) for item in restore_logs],
            "unlocks": [_netdisk_unlock_ledger_to_dict(item) for item in unlocks],
            "recent_logs": [_netdisk_audit_log_to_dict(item) for item in recent_logs],
        }
    )


@router.post("/netdisk/resource-quality/alerts/{alert_id}/{action}", summary="handle netdisk quality alert")
async def admin_handle_netdisk_resource_quality_alert(
    alert_id: str,
    action: str,
    req: NetdiskAdminAuditRequest,
    x_admin_role: str = Header("operator"),
    session: AsyncSession = Depends(get_session),
):
    if action not in {"read", "resolve", "ignore", "reopen"}:
        return response([], 400, "invalid alert action")
    if action in {"resolve", "ignore"} and not _is_quality_supervisor(x_admin_role):
        return response([], 403, "仅主管可执行高风险预警处理")
    try:
        uid = UUID(alert_id)
    except ValueError:
        return response([], 400, "invalid alert id")
    item = await session.get(NetdiskQualityAlert, uid)
    if not item:
        return response([], 404, "quality alert not found")

    status_map = {"read": "read", "resolve": "resolved", "ignore": "ignored", "reopen": "open"}
    item.status = status_map[action]
    item.note = _append_note(item.note, req.note.strip() or _quality_alert_action_note(action))
    item.handled_at = None if action == "reopen" else datetime.utcnow()
    item.updated_at = datetime.utcnow()
    await session.flush()
    await session.refresh(item)
    await _record_netdisk_audit_log(
        session,
        f"quality_alert_{action}",
        "netdisk_quality_alert",
        alert_id,
        item.title,
        req.note,
    )
    return response(data=_quality_alert_to_dict(item), msg="quality alert updated")


@router.post("/netdisk/resource-quality/alerts-action/{alert_id}/resolve", summary="resolve quality alert with resource action")
async def admin_resolve_netdisk_resource_quality_alert_with_action(
    alert_id: str,
    req: NetdiskAdminAuditRequest,
    x_admin_role: str = Header("operator"),
    session: AsyncSession = Depends(get_session),
):
    if not _is_quality_supervisor(x_admin_role):
        return response([], 403, "仅主管可执行资源复核结果处理")
    if req.result_action not in {"restore", "confirm_invalid", "keep_hidden"}:
        return response([], 400, "invalid result action")
    try:
        uid = UUID(alert_id)
    except ValueError:
        return response([], 400, "invalid alert id")
    item = await session.get(NetdiskQualityAlert, uid)
    if not item:
        return response([], 404, "quality alert not found")
    try:
        result_payload = await _apply_quality_alert_result_action(session, item, req.result_action, req.note)
    except ValueError as exc:
        return response([], 400, str(exc))
    item.status = "resolved"
    item.note = _append_note(item.note, req.note.strip() or _quality_alert_result_action_note(req.result_action))
    item.handled_at = datetime.utcnow()
    item.updated_at = datetime.utcnow()
    await session.flush()
    await session.refresh(item)
    await _record_netdisk_audit_log(
        session,
        f"quality_alert_resolve_{req.result_action}",
        "netdisk_quality_alert",
        str(item.id),
        item.title,
        req.note,
    )
    return response(
        data={
            "alert": _quality_alert_to_dict(item),
            "result_action": req.result_action,
            "result": result_payload,
        },
        msg="quality alert resolved",
    )


@router.post("/netdisk/resource-quality/alerts-batch/{action}", summary="batch handle netdisk quality alerts")
async def admin_batch_handle_netdisk_resource_quality_alerts(
    action: str,
    payload: dict,
    x_admin_role: str = Header("operator"),
    session: AsyncSession = Depends(get_session),
):
    if action not in {"read", "resolve", "ignore"}:
        return response([], 400, "invalid batch alert action")
    if action in {"resolve", "ignore"} and not _is_quality_supervisor(x_admin_role):
        return response([], 403, "仅主管可执行高风险预警批量处理")
    ids = payload.get("ids") or []
    note = str(payload.get("note") or "").strip()
    if not ids:
        return response([], 400, "ids required")

    handled = []
    for alert_id in ids:
        try:
            uid = UUID(str(alert_id))
        except ValueError:
            continue
        item = await session.get(NetdiskQualityAlert, uid)
        if not item:
            continue
        status_map = {"read": "read", "resolve": "resolved", "ignore": "ignored"}
        item.status = status_map[action]
        item.note = _append_note(item.note, note or _quality_alert_action_note(action))
        item.handled_at = datetime.utcnow()
        item.updated_at = datetime.utcnow()
        handled.append(item)
        await _record_netdisk_audit_log(
            session,
            f"quality_alert_batch_{action}",
            "netdisk_quality_alert",
            str(item.id),
            item.title,
            note,
        )
    await session.flush()
    return response(data={"handled": len(handled), "alerts": [_quality_alert_to_dict(item) for item in handled]})


@router.post("/netdisk/resource-quality/refresh-stats", summary="refresh netdisk quality daily stats")
async def admin_refresh_netdisk_resource_quality_stats(session: AsyncSession = Depends(get_session)):
    rows = await refresh_netdisk_quality_daily_stats(session)
    return response(data={"rows": rows}, msg="netdisk quality daily stats refreshed")


@router.put("/netdisk/audit-config", summary="update netdisk audit config")
async def admin_update_netdisk_audit_config(req: ConfigUpdateRequest, session: AsyncSession = Depends(get_session)):
    config = await ConfigService.set(session, "netdisk_audit_config", req.config_data)
    return response(data=config.config_data, msg="netdisk audit config updated")


@router.post("/netdisk/repairs/{repair_id}/approve", summary="admin approve netdisk repair/report")
async def admin_approve_netdisk_repair(
    repair_id: str,
    req: NetdiskAdminAuditRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        payload = await NetdiskResourceService.approve_repair(session, repair_id, req.note)
    except ValueError as exc:
        return response([], 400, str(exc))
    repair = payload["repair"]
    action = "report_confirm" if repair.get("mode") == "report" else "repair_approve"
    await _record_netdisk_audit_log(session, action, "netdisk_repair", repair_id, repair.get("resource_title", ""), req.note)
    return response(data=jsonable_encoder(payload), msg="netdisk repair approved")


@router.post("/netdisk/repairs/{repair_id}/reject", summary="admin reject netdisk repair/report")
async def admin_reject_netdisk_repair(
    repair_id: str,
    req: NetdiskAdminAuditRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        payload = await NetdiskResourceService.reject_repair(session, repair_id, req.note)
    except ValueError as exc:
        return response([], 400, str(exc))
    repair = payload["repair"]
    action = "report_reject" if repair.get("mode") == "report" else "repair_reject"
    await _record_netdisk_audit_log(session, action, "netdisk_repair", repair_id, repair.get("resource_title", ""), req.note)
    return response(data=jsonable_encoder(payload), msg="netdisk repair rejected")


@router.post("/netdisk/repairs/{repair_id}/confirm-invalid", summary="admin confirm invalid netdisk repair/report")
async def admin_confirm_invalid_netdisk_repair(
    repair_id: str,
    req: NetdiskAdminAuditRequest,
    x_admin_role: str = Header("operator"),
    session: AsyncSession = Depends(get_session),
):
    if not _is_quality_supervisor(x_admin_role):
        return response([], 403, "仅主管可确认资源失效")
    try:
        payload = await NetdiskResourceService.confirm_repair_invalid(session, repair_id, req.note)
    except ValueError as exc:
        return response([], 400, str(exc))
    repair = payload["repair"]
    action = "report_confirm" if repair.get("mode") == "report" else "repair_confirm_invalid"
    await _record_netdisk_audit_log(session, action, "netdisk_repair", repair_id, repair.get("resource_title", ""), req.note)
    return response(data=jsonable_encoder(payload), msg="netdisk repair invalid confirmed")


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


def _parse_netdisk_import_file(raw: bytes, suffix: str, source_type: str) -> tuple[list[dict], list[dict]]:
    text = raw.decode("utf-8-sig").strip()
    if not text:
        return [], []
    if suffix == "json":
        payload = json.loads(text)
        if isinstance(payload, dict):
            rows = payload.get("rows") or payload.get("items") or payload.get("resources") or payload.get("data") or []
        else:
            rows = payload
        if not isinstance(rows, list):
            raise ValueError("JSON 文件应为数组，或包含 rows/items/resources/data 数组")
        normalized = []
        failed_rows = []
        for index, item in enumerate(rows, start=1):
            if isinstance(item, dict):
                normalized.append(dict(item))
            else:
                failed_rows.append({"row_index": index, "reason": "该行不是对象", "title": "", "link": "", "raw": {"value": str(item)}})
    else:
        reader = csv.DictReader(io.StringIO(text))
        normalized = [dict(row) for row in reader]
        failed_rows = []
    for index, row in enumerate(normalized, start=1):
        row.setdefault("source_type", source_type or "manual")
        row.setdefault("source_id", row.get("source_id") or row.get("topic_id") or row.get("id") or f"file-row-{index}")
    return normalized, failed_rows


def _create_import_batch(filename: str, source_type: str, operator_role: str, total_rows: int, payload: dict) -> NetdiskImportBatch:
    failed_rows = payload.get("failed_rows") or []
    failed_count = int(payload.get("failed") or len(failed_rows))
    error = str(payload.get("error") or "")
    if error:
        status = "failed"
    elif failed_count:
        status = "partial_failed"
    else:
        status = "success"
    return NetdiskImportBatch(
        filename=(filename or "未命名文件")[:180],
        source_type=(source_type or "manual")[:32],
        operator_role=(operator_role or "operator")[:32],
        status=status,
        total_rows=int(total_rows or 0),
        synced_count=int(payload.get("synced") or 0),
        auto_published_count=int(payload.get("auto_published") or 0),
        review_required_count=int(payload.get("review_required") or 0),
        skipped_count=int(payload.get("skipped") or 0),
        failed_count=failed_count,
        failed_rows=json.dumps(failed_rows, ensure_ascii=False),
        error=error[:800],
    )


def _build_import_batch_payload(item: NetdiskImportBatch) -> dict:
    return {
        "id": str(item.id),
        "filename": item.filename,
        "source_type": item.source_type,
        "operator_role": item.operator_role,
        "status": item.status,
        "status_text": _import_batch_status_text(item.status),
        "total_rows": int(item.total_rows or 0),
        "synced_count": int(item.synced_count or 0),
        "auto_published_count": int(item.auto_published_count or 0),
        "review_required_count": int(item.review_required_count or 0),
        "skipped_count": int(item.skipped_count or 0),
        "failed_count": int(item.failed_count or 0),
        "error": item.error,
        "created_at": item.created_at,
    }


def _import_batch_status_text(status: str) -> str:
    if status == "success":
        return "成功"
    if status == "partial_failed":
        return "部分失败"
    if status == "failed":
        return "失败"
    return "未知"


def _parse_failed_rows(raw: str | None) -> list[dict]:
    try:
        parsed = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


async def _record_netdisk_audit_log(
    session: AsyncSession,
    action: str,
    target_type: str,
    target_id: str,
    target_title: str,
    note: str = "",
) -> None:
    session.add(
        NetdiskAuditLog(
            admin_name="admin",
            action=action,
            target_type=target_type,
            target_id=target_id,
            target_title=(target_title or "")[:200],
            note=(note or "").strip(),
            result="success",
        )
    )
    await session.flush()


async def _build_netdisk_ops_trends(session: AsyncSession, today_start: datetime) -> list[dict]:
    start_day = today_start - timedelta(days=6)
    business_points_filter = or_(PointsLedger.source.is_(None), PointsLedger.source != "admin_adjust")
    trends: list[dict] = []
    for index in range(7):
        day_start = start_day + timedelta(days=index)
        day_end = day_start + timedelta(days=1)

        new_users = (
            await session.execute(
                select(func.count()).select_from(User).where(
                    User.created_at >= day_start,
                    User.created_at < day_end,
                )
            )
        ).scalar() or 0
        gain = (
            await session.execute(
                select(
                    func.count(func.distinct(PointsLedger.user_id)),
                    func.coalesce(func.sum(PointsLedger.points_delta), 0),
                ).where(
                    PointsLedger.created_at >= day_start,
                    PointsLedger.created_at < day_end,
                    PointsLedger.points_delta > 0,
                    business_points_filter,
                )
            )
        ).one()
        spend = (
            await session.execute(
                select(
                    func.count(func.distinct(PointsLedger.user_id)),
                    func.coalesce(func.sum(PointsLedger.points_delta), 0),
                ).where(
                    PointsLedger.created_at >= day_start,
                    PointsLedger.created_at < day_end,
                    PointsLedger.points_delta < 0,
                    business_points_filter,
                )
            )
        ).one()
        uploads = (
            await session.execute(
                select(func.count()).select_from(NetdiskUpload).where(
                    NetdiskUpload.created_at >= day_start,
                    NetdiskUpload.created_at < day_end,
                )
            )
        ).scalar() or 0
        reports = (
            await session.execute(
                select(func.count()).select_from(NetdiskRepair).where(
                    NetdiskRepair.created_at >= day_start,
                    NetdiskRepair.created_at < day_end,
                    NetdiskRepair.mode == "report",
                )
            )
        ).scalar() or 0

        trends.append(
            {
                "date": day_start.strftime("%Y-%m-%d"),
                "new_users": int(new_users),
                "gain_users": int(gain[0] or 0),
                "gain_points": int(gain[1] or 0),
                "spend_users": int(spend[0] or 0),
                "spend_points": abs(int(spend[1] or 0)),
                "uploads": int(uploads),
                "reports": int(reports),
            }
        )
    return trends


async def _build_crawler_worker_fallback_status() -> dict:
    fallback_tasks = {
        "kdocs_anime": _empty_crawler_task("kdocs_anime"),
        "kdocs_movie": _empty_crawler_task("kdocs_movie"),
        "kdocs_4k": _empty_crawler_task("kdocs_4k"),
        "linuxdo": _empty_crawler_task("linuxdo"),
    }

    try:
        from models.base import get_session_ctx

        async with get_session_ctx() as session:
            recent_rows = (
                await session.execute(
                    select(NetdiskCrawlerRun)
                    .order_by(NetdiskCrawlerRun.started_at.desc(), NetdiskCrawlerRun.created_at.desc())
                    .limit(8)
                )
            ).scalars().all()

            for crawler_key in fallback_tasks.keys():
                latest_row = (
                    await session.execute(
                        select(NetdiskCrawlerRun)
                        .where(NetdiskCrawlerRun.crawler_key == crawler_key)
                        .order_by(NetdiskCrawlerRun.started_at.desc(), NetdiskCrawlerRun.created_at.desc())
                        .limit(1)
                    )
                ).scalars().first()
                latest_success_row = (
                    await session.execute(
                        select(NetdiskCrawlerRun)
                        .where(NetdiskCrawlerRun.crawler_key == crawler_key, NetdiskCrawlerRun.status == "success")
                        .order_by(NetdiskCrawlerRun.finished_at.desc(), NetdiskCrawlerRun.created_at.desc())
                        .limit(1)
                    )
                ).scalars().first()
                if latest_row:
                    fallback_tasks[crawler_key].update(_crawler_task_from_run(latest_row, latest_success_row))
    except Exception:
        logger.error("failed to build crawler worker fallback status", exc_info=True)
        recent_rows = []

    return {
        "status": "offline",
        "task_timeout_seconds": int(os.getenv("CRAWLER_TASK_TIMEOUT_SECONDS", "900")),
        "failure_breaker_threshold": int(os.getenv("CRAWLER_FAILURE_BREAKER_THRESHOLD", "3")),
        "failure_breaker_cooldown_seconds": int(os.getenv("CRAWLER_FAILURE_BREAKER_COOLDOWN_SECONDS", "1800")),
        "running_tasks": [],
        "blocked_tasks": [],
        "tasks": list(fallback_tasks.values()),
        "recent_runs": [_crawler_recent_run_to_dict(item) for item in recent_rows],
        "scheduler_jobs": _build_crawler_scheduler_jobs_fallback(recent_rows),
    }


def _empty_crawler_task(crawler_key: str) -> dict:
    return {
        "key": crawler_key,
        "running": False,
        "last_started_at": "",
        "last_finished_at": "",
        "last_success_at": "",
        "last_error": "",
        "last_result": {},
        "consecutive_failures": 0,
        "breaker_until": "",
    }


def _crawler_task_from_run(row: NetdiskCrawlerRun, latest_success_row: NetdiskCrawlerRun | None) -> dict:
    task = _empty_crawler_task(row.crawler_key)
    task["last_started_at"] = row.started_at.isoformat() if row.started_at else ""
    task["last_finished_at"] = row.finished_at.isoformat() if row.finished_at else ""
    task["last_success_at"] = latest_success_row.finished_at.isoformat() if latest_success_row and latest_success_row.finished_at else ""
    task["last_error"] = row.error_text or (row.status if row.status != "success" else "")
    task["last_result"] = _parse_crawler_result_payload(row.result_payload)
    task["consecutive_failures"] = int(row.consecutive_failures or 0)
    return task


def _crawler_recent_run_to_dict(row: NetdiskCrawlerRun) -> dict:
    return {
        "id": str(row.id),
        "crawler_key": row.crawler_key,
        "trigger_source": row.trigger_source,
        "status": row.status,
        "started_at": row.started_at.isoformat() if row.started_at else "",
        "finished_at": row.finished_at.isoformat() if row.finished_at else "",
        "duration_seconds": int(row.duration_seconds or 0),
        "synced_count": int(row.synced_count or 0),
        "inactive_count": int(row.inactive_count or 0),
        "auto_published_count": int(row.auto_published_count or 0),
        "review_required_count": int(row.review_required_count or 0),
        "skipped_count": int(row.skipped_count or 0),
        "failed_count": int(row.failed_count or 0),
        "netdisk_inactive_count": int(row.netdisk_inactive_count or 0),
        "consecutive_failures": int(row.consecutive_failures or 0),
        "error_text": row.error_text or "",
        "result_payload": _parse_crawler_result_payload(row.result_payload),
    }


def _parse_crawler_result_payload(payload_text: str) -> dict:
    if not payload_text:
        return {}
    try:
        payload = json.loads(payload_text)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _build_crawler_scheduler_jobs_fallback(recent_rows: list[NetdiskCrawlerRun]) -> list[dict]:
    now_bj = datetime.now(ZoneInfo("Asia/Shanghai"))
    rows_by_key: dict[str, NetdiskCrawlerRun] = {}
    for row in recent_rows:
        rows_by_key.setdefault(row.crawler_key, row)

    jobs = []
    anime_interval = int(os.getenv("ANIME_SYNC_INTERVAL", "60"))
    if os.getenv("ANIME_SYNC_ENABLED", "true").lower() == "true":
        if anime_interval == 60:
            next_run = now_bj.replace(minute=30, second=0, microsecond=0)
            if next_run <= now_bj:
                next_run = next_run + timedelta(hours=1)
            name = "影视剧数据每小时30分同步(金山文档)"
        else:
            anchor = _row_finished_time_bj(rows_by_key.get("kdocs_anime")) or now_bj
            next_run = anchor + timedelta(minutes=anime_interval)
            name = "影视剧数据定时间隔同步(金山文档)"
        jobs.append({"id": "sync_anime_job", "name": name, "next_run_time": next_run.isoformat()})

    next_midnight = (now_bj + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    jobs.append(
        {
            "id": "sync_movie_4k_job",
            "name": "电影/4K数据每日凌晨同步(金山文档)",
            "next_run_time": next_midnight.isoformat(),
        }
    )

    if os.getenv("LINUXDO_SYNC_ENABLED", "true").lower() == "true":
        linuxdo_hours = int(os.getenv("LINUXDO_SYNC_INTERVAL_HOURS", "12"))
        anchor = _row_finished_time_bj(rows_by_key.get("linuxdo")) or now_bj
        jobs.append(
            {
                "id": "linuxdo_netdisk_12h_sync",
                "name": "LinuxDo云资产每12小时同步",
                "next_run_time": (anchor + timedelta(hours=linuxdo_hours)).isoformat(),
            }
        )
    return jobs


def _row_finished_time_bj(row: NetdiskCrawlerRun | None) -> datetime | None:
    if not row or not row.finished_at:
        return None
    dt = row.finished_at
    if dt.tzinfo is None:
        return dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Asia/Shanghai"))
    return dt.astimezone(ZoneInfo("Asia/Shanghai"))


async def _build_point_source_distribution(session: AsyncSession, start_dt: datetime) -> list[dict]:
    business_points_filter = or_(PointsLedger.source.is_(None), PointsLedger.source != "admin_adjust")
    rows = (
        await session.execute(
            select(
                PointsLedger.source,
                PointsLedger.change_type,
                func.coalesce(func.sum(PointsLedger.points_delta), 0),
                func.count(),
            )
            .where(PointsLedger.created_at >= start_dt, PointsLedger.points_delta != 0, business_points_filter)
            .group_by(PointsLedger.source, PointsLedger.change_type)
            .order_by(func.abs(func.coalesce(func.sum(PointsLedger.points_delta), 0)).desc())
            .limit(12)
        )
    ).all()
    return [
        {
            "source": row[0],
            "change_type": row[1],
            "points": int(row[2] or 0),
            "count": int(row[3] or 0),
        }
        for row in rows
    ]


async def _build_today_point_spend_users(session: AsyncSession, today_start: datetime) -> list[dict]:
    business_points_filter = or_(PointsLedger.source.is_(None), PointsLedger.source != "admin_adjust")
    rows = (
        await session.execute(
            select(
                User.id,
                User.nickname,
                User.openid,
                func.coalesce(func.sum(PointsLedger.points_delta), 0).label("spend_points"),
                func.count(PointsLedger.id).label("spend_count"),
                func.max(PointsLedger.created_at).label("last_spend_at"),
            )
            .select_from(PointsLedger)
            .join(User, User.id == PointsLedger.user_id)
            .where(
                PointsLedger.created_at >= today_start,
                PointsLedger.points_delta < 0,
                business_points_filter,
            )
            .group_by(User.id, User.nickname, User.openid)
            .order_by(func.abs(func.coalesce(func.sum(PointsLedger.points_delta), 0)).desc())
            .limit(30)
        )
    ).all()

    details: list[dict] = []
    for row in rows:
        user_id = row[0]
        latest = (
            await session.execute(
                select(PointsLedger)
                .where(
                    PointsLedger.user_id == user_id,
                    PointsLedger.created_at >= today_start,
                    PointsLedger.points_delta < 0,
                    business_points_filter,
                )
                .order_by(PointsLedger.created_at.desc(), PointsLedger.id.desc())
                .limit(1)
            )
        ).scalars().first()
        details.append(
            {
                "user_id": str(user_id),
                "nickname": row[1] or "",
                "openid": row[2] or "",
                "spend_points": abs(int(row[3] or 0)),
                "spend_count": int(row[4] or 0),
                "last_spend_at": row[5].isoformat() if row[5] else None,
                "latest_source": latest.source if latest else "",
                "latest_change_type": latest.change_type if latest else "",
                "latest_remark": latest.remark if latest else "",
            }
        )
    return details


async def _build_resource_quality_rankings(
    session: AsyncSession,
    filter_mode: str = "all",
    range_mode: str = "7d",
    limit: int = 10,
    thresholds: dict | None = None,
) -> list[dict]:
    thresholds = thresholds or await _get_resource_quality_thresholds(session)
    stat_rankings = await _build_resource_quality_rankings_from_stats(session, filter_mode, range_mode, limit, thresholds)
    if stat_rankings:
        return stat_rankings

    reports_sq, restores_sq, unlocks_sq, recent_reports_sq, recent_unlocks_sq = _resource_quality_subqueries()
    report_count = func.coalesce(reports_sq.c.reports, 0)
    restore_count = func.coalesce(restores_sq.c.restores, 0)
    unlock_count = func.coalesce(unlocks_sq.c.unlocks, 0)
    score_expr = report_count * 3 + restore_count * 2 + unlock_count
    query = (
        select(
            NetdiskResourceModel,
            report_count.label("reports"),
            restore_count.label("restores"),
            unlock_count.label("unlocks"),
            func.coalesce(unlocks_sq.c.unlock_users, 0).label("unlock_users"),
            func.coalesce(recent_reports_sq.c.recent_reports, 0).label("recent_reports_24h"),
            func.coalesce(recent_unlocks_sq.c.recent_unlocks, 0).label("recent_unlocks_24h"),
            score_expr.label("score"),
        )
        .select_from(NetdiskResourceModel)
        .outerjoin(reports_sq, reports_sq.c.resource_id == NetdiskResourceModel.id)
        .outerjoin(restores_sq, restores_sq.c.resource_id == NetdiskResourceModel.id)
        .outerjoin(unlocks_sq, unlocks_sq.c.resource_id == NetdiskResourceModel.id)
        .outerjoin(recent_reports_sq, recent_reports_sq.c.resource_id == NetdiskResourceModel.id)
        .outerjoin(recent_unlocks_sq, recent_unlocks_sq.c.resource_id == NetdiskResourceModel.id)
    )
    if filter_mode == "hidden":
        query = query.where(NetdiskResourceModel.is_active == False)  # noqa: E712
    elif filter_mode == "high_report":
        query = query.where(report_count >= thresholds["high_report_threshold"])
    elif filter_mode == "high_unlock":
        query = query.where(unlock_count >= thresholds["high_unlock_threshold"])
    else:
        query = query.where(score_expr > 0)

    rows = (
        await session.execute(
            query.order_by(score_expr.desc(), report_count.desc(), unlock_count.desc(), NetdiskResourceModel.updated_at.desc())
            .limit(limit)
        )
    ).all()
    return [_resource_quality_row_to_dict(row) for row in rows]


async def _build_resource_quality_rankings_from_stats(
    session: AsyncSession,
    filter_mode: str,
    range_mode: str,
    limit: int,
    thresholds: dict,
) -> list[dict]:
    today = today_bj()
    if range_mode == "today":
        start_day = today
    elif range_mode == "all":
        start_day = None
    else:
        start_day = today - timedelta(days=6)
    conditions = [NetdiskQualityDailyStat.stat_date <= today]
    if start_day:
        conditions.append(NetdiskQualityDailyStat.stat_date >= start_day)
    stats = (
        await session.execute(
            select(NetdiskQualityDailyStat)
            .where(*conditions)
            .order_by(NetdiskQualityDailyStat.stat_date.desc())
        )
    ).scalars().all()
    if not stats:
        return []

    resource_ids = list({item.resource_id for item in stats})
    resources = (
        await session.execute(select(NetdiskResourceModel).where(NetdiskResourceModel.id.in_(resource_ids)))
    ).scalars().all()
    resource_map = {item.id: item for item in resources}
    grouped: dict[str, dict] = {}
    for item in stats:
        row = grouped.setdefault(
            item.resource_id,
            {
                "resource_id": item.resource_id,
                "id": item.resource_id,
                "title": item.title,
                "category": item.category,
                "pan": item.pan,
                "level": resource_map.get(item.resource_id).level if resource_map.get(item.resource_id) else "",
                "cost_points": int(resource_map.get(item.resource_id).cost_points or 0) if resource_map.get(item.resource_id) else 0,
                "is_active": bool(item.is_active),
                "downloads": int(resource_map.get(item.resource_id).downloads or 0) if resource_map.get(item.resource_id) else 0,
                "favorites": int(resource_map.get(item.resource_id).favorites or 0) if resource_map.get(item.resource_id) else 0,
                "description": resource_map.get(item.resource_id).description if resource_map.get(item.resource_id) else "",
                "reports": 0,
                "restores": 0,
                "unlocks": 0,
                "unlock_users": 0,
                "recent_reports_24h": 0,
                "recent_unlocks_24h": 0,
                "score": 0,
                "stat_source": "daily_stats",
                "range": range_mode,
            },
        )
        row["reports"] += int(item.reports or 0)
        row["restores"] += int(item.restores or 0)
        row["unlocks"] += int(item.unlocks or 0)
        row["unlock_users"] += int(item.unlock_users or 0)
        row["score"] += int(item.score or 0)
        if item.stat_date == today:
            row["recent_reports_24h"] = int(item.reports or 0)
            row["recent_unlocks_24h"] = int(item.unlocks or 0)
            row["is_active"] = bool(item.is_active)
            row["title"] = item.title
            row["category"] = item.category
            row["pan"] = item.pan

    rankings = list(grouped.values())
    if filter_mode == "hidden":
        rankings = [item for item in rankings if not item["is_active"]]
    elif filter_mode == "high_report":
        rankings = [item for item in rankings if item["reports"] >= thresholds["high_report_threshold"]]
    elif filter_mode == "high_unlock":
        rankings = [item for item in rankings if item["unlocks"] >= thresholds["high_unlock_threshold"]]
    else:
        rankings = [item for item in rankings if item["score"] > 0]

    rankings.sort(key=lambda row: (row["score"], row["reports"], row["unlocks"]), reverse=True)
    return rankings[:limit]


async def _build_resource_quality_alerts(session: AsyncSession) -> list[dict]:
    thresholds = await _get_resource_quality_thresholds(session)
    rankings = await _build_resource_quality_rankings(session, limit=30, thresholds=thresholds)
    alerts = []
    for item in rankings:
        if item["reports"] >= thresholds["high_report_threshold"]:
            alert = await _upsert_quality_alert(
                session=session,
                item=item,
                alert_type="high_report",
                level="danger",
                message=f"投诉 {item['reports']} 次，达到高投诉阈值",
                auto_review_pool=thresholds["auto_review_pool"],
            )
            if alert:
                await _apply_quality_auto_action(session, item, alert, "high_report", thresholds)
            if alert and alert.status in {"open", "read"}:
                alerts.append(_quality_alert_to_dict(alert, level="danger"))
        if (
            item["recent_reports_24h"] >= thresholds["burst_report_threshold"]
            and item["recent_unlocks_24h"] >= thresholds["burst_unlock_threshold"]
        ):
            alert = await _upsert_quality_alert(
                session=session,
                item=item,
                alert_type="unlock_report_burst",
                level="warning",
                message=f"24小时内解锁 {item['recent_unlocks_24h']} 次且投诉 {item['recent_reports_24h']} 次",
                auto_review_pool=thresholds["auto_review_pool"],
            )
            if alert:
                await _apply_quality_auto_action(session, item, alert, "unlock_report_burst", thresholds)
            if alert and alert.status in {"open", "read"}:
                alerts.append(_quality_alert_to_dict(alert, level="warning"))
    return alerts[:6]


async def _upsert_quality_alert(
    session: AsyncSession,
    item: dict,
    alert_type: str,
    level: str,
    message: str,
    auto_review_pool: bool = True,
) -> NetdiskQualityAlert | None:
    result = await session.execute(
        select(NetdiskQualityAlert).where(
            NetdiskQualityAlert.resource_id == item["resource_id"],
            NetdiskQualityAlert.alert_type == alert_type,
        )
    )
    alert = result.scalar_one_or_none()
    now = datetime.utcnow()
    if alert:
        alert.title = item["title"]
        alert.message = message
        alert.last_triggered_at = now
        alert.updated_at = now
        if auto_review_pool and alert.status == "resolved":
            alert.status = "open"
            alert.handled_at = None
        await session.flush()
        return alert
    alert = NetdiskQualityAlert(
        resource_id=item["resource_id"],
        alert_type=alert_type,
        status="open" if auto_review_pool else "ignored",
        title=item["title"],
        message=message,
        last_triggered_at=now,
        note="" if auto_review_pool else "规则配置关闭自动进入待复核池",
        handled_at=None if auto_review_pool else now,
    )
    session.add(alert)
    await session.flush()
    return alert


async def _apply_quality_auto_action(
    session: AsyncSession,
    item: dict,
    alert: NetdiskQualityAlert,
    alert_type: str,
    thresholds: dict,
) -> None:
    should_hide = (
        (alert_type == "high_report" and thresholds["auto_hide_high_report"])
        or (alert_type == "unlock_report_burst" and thresholds["auto_hide_burst"])
    )
    if not should_hide:
        return
    resource = await session.get(NetdiskResourceModel, item["resource_id"])
    if not resource or not resource.is_active:
        return
    resource.is_active = False
    resource.updated_at = datetime.utcnow()
    note = f"质量规则自动隐藏：{alert.message}"
    alert.note = _append_note(alert.note, note)
    await _record_netdisk_audit_log(
        session,
        "resource_quality_auto_hide",
        "netdisk_resource",
        resource.id,
        resource.title,
        note,
    )
    await session.flush()


async def _apply_quality_alert_result_action(
    session: AsyncSession,
    alert: NetdiskQualityAlert,
    result_action: str,
    note: str = "",
) -> dict:
    resource = await session.get(NetdiskResourceModel, alert.resource_id)
    if not resource:
        raise ValueError("resource not found")
    clean_note = note.strip() or _quality_alert_result_action_note(result_action)
    if result_action == "restore":
        payload = await NetdiskResourceService.restore_resource(session, alert.resource_id, clean_note)
        await _record_netdisk_audit_log(
            session,
            "resource_restore",
            "netdisk_resource",
            alert.resource_id,
            payload["resource"].get("title", ""),
            clean_note,
        )
        return payload

    if result_action == "confirm_invalid":
        payload = await NetdiskResourceService.confirm_resource_invalid(session, alert.resource_id, clean_note)
        await _record_netdisk_audit_log(
            session,
            "resource_quality_confirm_invalid",
            "netdisk_resource",
            alert.resource_id,
            payload["resource"].get("title", ""),
            clean_note,
        )
        return payload

    resource.is_active = False
    resource.updated_at = datetime.utcnow()
    await _record_netdisk_audit_log(
        session,
        "resource_quality_keep_hidden",
        "netdisk_resource",
        resource.id,
        resource.title,
        clean_note,
    )
    await session.flush()
    return {"resource": _resource_quality_resource_to_dict(resource)}


async def _list_resource_quality_alerts(session: AsyncSession, resource_id: str) -> list[dict]:
    rows = (
        await session.execute(
            select(NetdiskQualityAlert)
            .where(NetdiskQualityAlert.resource_id == resource_id)
            .order_by(NetdiskQualityAlert.last_triggered_at.desc())
        )
    ).scalars().all()
    return [_quality_alert_to_dict(item) for item in rows]


async def _build_resource_quality_stat(session: AsyncSession, resource: NetdiskResourceModel) -> dict:
    reports = (
        await session.execute(
            select(func.count(), func.max(NetdiskRepair.created_at)).where(
                NetdiskRepair.resource_id == resource.id,
                NetdiskRepair.mode == "report",
            )
        )
    ).one()
    restores = (
        await session.execute(
            select(func.count(), func.max(NetdiskAuditLog.created_at)).where(
                NetdiskAuditLog.target_type == "netdisk_resource",
                NetdiskAuditLog.target_id == resource.id,
                NetdiskAuditLog.action == "resource_restore",
            )
        )
    ).one()
    unlocks = (
        await session.execute(
            select(
                func.count(),
                func.count(func.distinct(PointsLedger.user_id)),
                func.max(PointsLedger.created_at),
            ).where(
                PointsLedger.source == "netdisk",
                PointsLedger.change_type == "resource_unlock",
                PointsLedger.related_type == "netdisk_resource",
                PointsLedger.related_id == resource.id,
            )
        )
    ).one()
    recent_start = datetime.utcnow() - timedelta(hours=24)
    recent_reports = (
        await session.execute(
            select(func.count()).select_from(NetdiskRepair).where(
                NetdiskRepair.resource_id == resource.id,
                NetdiskRepair.mode == "report",
                NetdiskRepair.created_at >= recent_start,
            )
        )
    ).scalar() or 0
    recent_unlocks = (
        await session.execute(
            select(func.count()).select_from(PointsLedger).where(
                PointsLedger.source == "netdisk",
                PointsLedger.change_type == "resource_unlock",
                PointsLedger.related_type == "netdisk_resource",
                PointsLedger.related_id == resource.id,
                PointsLedger.created_at >= recent_start,
            )
        )
    ).scalar() or 0
    report_count = int(reports[0] or 0)
    restore_count = int(restores[0] or 0)
    unlock_count = int(unlocks[0] or 0)
    return {
        "reports": report_count,
        "restores": restore_count,
        "unlocks": unlock_count,
        "unlock_users": int(unlocks[1] or 0),
        "recent_reports_24h": int(recent_reports),
        "recent_unlocks_24h": int(recent_unlocks),
        "score": report_count * 3 + restore_count * 2 + unlock_count,
        "last_report_at": reports[1].isoformat() if reports[1] else None,
        "last_restore_at": restores[1].isoformat() if restores[1] else None,
        "last_unlock_at": unlocks[2].isoformat() if unlocks[2] else None,
    }


async def _build_resource_quality_trends(session: AsyncSession, resource_id: str) -> list[dict]:
    today = today_bj()
    start_day = today - timedelta(days=6)
    stats = (
        await session.execute(
            select(NetdiskQualityDailyStat)
            .where(
                NetdiskQualityDailyStat.resource_id == resource_id,
                NetdiskQualityDailyStat.stat_date >= start_day,
                NetdiskQualityDailyStat.stat_date <= today,
            )
            .order_by(NetdiskQualityDailyStat.stat_date.asc())
        )
    ).scalars().all()
    stat_map = {item.stat_date: item for item in stats}
    trends = []
    for offset in range(7):
        day = start_day + timedelta(days=offset)
        item = stat_map.get(day)
        if item:
            trends.append(_quality_daily_stat_to_dict(item))
        else:
            trends.append(await build_resource_quality_day_stat(session, resource_id, day))
    return trends


async def _get_resource_quality_thresholds(session: AsyncSession) -> dict:
    config = await ConfigService.get(session, "netdisk_audit_config")
    return {
        "high_report_threshold": int(config.get("quality_high_report_threshold") or config.get("report_hide_threshold") or 3),
        "high_unlock_threshold": int(config.get("quality_high_unlock_threshold") or 5),
        "burst_report_threshold": int(config.get("quality_burst_report_threshold") or 1),
        "burst_unlock_threshold": int(config.get("quality_burst_unlock_threshold") or 3),
        "auto_review_pool": bool(config.get("quality_auto_review_pool", True)),
        "auto_hide_high_report": bool(config.get("quality_auto_hide_high_report", False)),
        "auto_hide_burst": bool(config.get("quality_auto_hide_burst", False)),
    }


def _resource_quality_subqueries():
    recent_start = datetime.utcnow() - timedelta(hours=24)
    reports_sq = (
        select(
            NetdiskRepair.resource_id.label("resource_id"),
            func.count(NetdiskRepair.id).label("reports"),
        )
        .where(NetdiskRepair.mode == "report")
        .group_by(NetdiskRepair.resource_id)
        .subquery()
    )
    restores_sq = (
        select(
            NetdiskAuditLog.target_id.label("resource_id"),
            func.count(NetdiskAuditLog.id).label("restores"),
        )
        .where(NetdiskAuditLog.target_type == "netdisk_resource", NetdiskAuditLog.action == "resource_restore")
        .group_by(NetdiskAuditLog.target_id)
        .subquery()
    )
    unlocks_sq = (
        select(
            PointsLedger.related_id.label("resource_id"),
            func.count(PointsLedger.id).label("unlocks"),
            func.count(func.distinct(PointsLedger.user_id)).label("unlock_users"),
        )
        .where(
            PointsLedger.source == "netdisk",
            PointsLedger.change_type == "resource_unlock",
            PointsLedger.related_type == "netdisk_resource",
        )
        .group_by(PointsLedger.related_id)
        .subquery()
    )
    recent_reports_sq = (
        select(
            NetdiskRepair.resource_id.label("resource_id"),
            func.count(NetdiskRepair.id).label("recent_reports"),
        )
        .where(NetdiskRepair.mode == "report", NetdiskRepair.created_at >= recent_start)
        .group_by(NetdiskRepair.resource_id)
        .subquery()
    )
    recent_unlocks_sq = (
        select(
            PointsLedger.related_id.label("resource_id"),
            func.count(PointsLedger.id).label("recent_unlocks"),
        )
        .where(
            PointsLedger.source == "netdisk",
            PointsLedger.change_type == "resource_unlock",
            PointsLedger.related_type == "netdisk_resource",
            PointsLedger.created_at >= recent_start,
        )
        .group_by(PointsLedger.related_id)
        .subquery()
    )
    return reports_sq, restores_sq, unlocks_sq, recent_reports_sq, recent_unlocks_sq


def _resource_quality_row_to_dict(row) -> dict:
    item = row[0]
    return {
        **_resource_quality_resource_to_dict(item),
        "resource_id": item.id,
        "reports": int(row.reports or 0),
        "restores": int(row.restores or 0),
        "unlocks": int(row.unlocks or 0),
        "unlock_users": int(row.unlock_users or 0),
        "recent_reports_24h": int(row.recent_reports_24h or 0),
        "recent_unlocks_24h": int(row.recent_unlocks_24h or 0),
        "score": int(row.score or 0),
    }


def _resource_quality_resource_to_dict(item: NetdiskResourceModel) -> dict:
    return {
        "id": item.id,
        "title": item.title,
        "category": item.category,
        "pan": item.pan,
        "level": item.level,
        "cost_points": int(item.cost_points or 0),
        "is_active": bool(item.is_active),
        "downloads": int(item.downloads or 0),
        "favorites": int(item.favorites or 0),
        "description": item.description,
        "source_upload_id": item.source_upload_id,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        "verified_at": item.verified_at.isoformat() if item.verified_at else None,
    }


def _quality_alert_to_dict(item: NetdiskQualityAlert, level: str | None = None) -> dict:
    level_map = {"high_report": "danger", "unlock_report_burst": "warning"}
    in_review_pool = item.status in {"open", "read"}
    return {
        "id": str(item.id),
        "type": item.alert_type,
        "level": level or level_map.get(item.alert_type, "warning"),
        "review_state": "pending_review" if in_review_pool else "closed",
        "in_review_pool": in_review_pool,
        "resource_id": item.resource_id,
        "title": item.title,
        "message": item.message,
        "status": item.status,
        "note": item.note,
        "last_triggered_at": item.last_triggered_at.isoformat() if item.last_triggered_at else None,
        "handled_at": item.handled_at.isoformat() if item.handled_at else None,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def _quality_daily_stat_to_dict(item: NetdiskQualityDailyStat) -> dict:
    return {
        "date": item.stat_date.isoformat(),
        "resource_id": item.resource_id,
        "title": item.title,
        "category": item.category,
        "pan": item.pan,
        "is_active": bool(item.is_active),
        "reports": int(item.reports or 0),
        "restores": int(item.restores or 0),
        "unlocks": int(item.unlocks or 0),
        "unlock_users": int(item.unlock_users or 0),
        "score": int(item.score or 0),
    }


def _quality_alert_action_note(action: str) -> str:
    return {
        "read": "后台标记已读",
        "resolve": "后台标记已处理",
        "ignore": "后台忽略预警",
        "reopen": "后台重新打开预警",
    }.get(action, "后台处理预警")


def _quality_alert_result_action_note(action: str) -> str:
    return {
        "restore": "复核结果：资源恢复上架",
        "confirm_invalid": "复核结果：确认资源失效",
        "keep_hidden": "复核结果：继续隐藏资源",
    }.get(action, "复核结果处理")


def _is_quality_supervisor(role: str | None) -> bool:
    return (role or "").lower() in {"admin", "supervisor"}


def _parse_date_range(start_date: str | None, end_date: str | None) -> tuple[datetime | None, datetime | None]:
    start_dt = None
    end_dt = None
    if start_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    if end_date:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
    return start_dt, end_dt


def _build_netdisk_audit_log_query(
    action: str | None,
    target_type: str | None,
    start_dt: datetime | None,
    end_dt: datetime | None,
):
    query = select(NetdiskAuditLog)
    if action:
        query = query.where(NetdiskAuditLog.action == action)
    if target_type:
        query = query.where(NetdiskAuditLog.target_type == target_type)
    if start_dt:
        query = query.where(NetdiskAuditLog.created_at >= start_dt)
    if end_dt:
        query = query.where(NetdiskAuditLog.created_at < end_dt)
    return query


async def _collect_netdisk_risk_record(session: AsyncSession, record_id: str, note: str = "") -> dict:
    try:
        uid = UUID(record_id)
    except ValueError:
        raise ValueError("invalid risk record id") from None
    item = await session.get(NetdiskRiskRecord, uid)
    if not item:
        raise ValueError("risk record not found")
    if item.status != "open":
        return {"risk_record": _netdisk_risk_record_to_dict(item), "collected_points": 0}
    account, _ = await PointsAccountService.ensure_user_account(session, item.user_id)
    pending_points = int(item.points_due)
    collect_points = min(pending_points, int(account.consumable_points))
    if collect_points <= 0:
        raise ValueError("用户当前可用积分不足，暂无法追缴")

    await PointsAccountService.consume_consumable_points(
        session=session,
        user_id=item.user_id,
        points=collect_points,
        source="netdisk",
        change_type="risk_recovery_collect",
        idempotency_key=f"netdisk_risk_collect:{item.id}:{int(item.points_collected)}:{collect_points}",
        related_type="netdisk_risk_record",
        related_id=str(item.id),
        remark=note.strip() or f"网盘待追缴扣除：{item.related_type}:{item.related_id}",
    )
    item.points_due = pending_points - collect_points
    item.points_collected = int(item.points_collected) + collect_points
    if int(item.points_due) <= 0:
        item.points_due = 0
        item.status = "cleared"
    item.note = _append_note(item.note, note.strip() or f"后台追缴扣除 {collect_points} 分")
    item.updated_at = datetime.utcnow()
    await session.flush()
    await session.refresh(item)
    return {"risk_record": _netdisk_risk_record_to_dict(item), "collected_points": collect_points}


async def _waive_netdisk_risk_record(session: AsyncSession, record_id: str, note: str = "") -> dict:
    try:
        uid = UUID(record_id)
    except ValueError:
        raise ValueError("invalid risk record id") from None
    item = await session.get(NetdiskRiskRecord, uid)
    if not item:
        raise ValueError("risk record not found")
    item.status = "cleared"
    item.note = _append_note(item.note, note.strip() or "后台人工关闭待追缴")
    item.updated_at = datetime.utcnow()
    await session.flush()
    await session.refresh(item)
    return {"risk_record": _netdisk_risk_record_to_dict(item)}


def _append_note(old_note: str, new_note: str) -> str:
    if not new_note:
        return old_note or ""
    if not old_note:
        return new_note
    return f"{old_note}\n{new_note}"


def _netdisk_audit_log_to_dict(item: NetdiskAuditLog) -> dict:
    return {
        "id": str(item.id),
        "admin_name": item.admin_name,
        "action": item.action,
        "target_type": item.target_type,
        "target_id": item.target_id,
        "target_title": item.target_title,
        "note": item.note,
        "result": item.result,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def _netdisk_repair_to_dict(item: NetdiskRepair) -> dict:
    return {
        "id": str(item.id),
        "user_id": str(item.user_id),
        "resource_id": item.resource_id,
        "resource_title": item.resource_title,
        "mode": item.mode,
        "pan": item.pan,
        "status": item.status,
        "reward_points": int(item.reward_points or 0),
        "note": item.note,
        "audit_note": item.audit_note,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def _netdisk_upload_to_dict(item: NetdiskUpload) -> dict:
    return {
        "id": str(item.id),
        "user_id": str(item.user_id),
        "title": item.title,
        "category": item.category,
        "pan": item.pan,
        "status": item.status,
        "reward_points": int(item.reward_points or 0),
        "audit_note": item.audit_note,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def _netdisk_unlock_ledger_to_dict(item: PointsLedger) -> dict:
    return {
        "id": str(item.id),
        "user_id": str(item.user_id),
        "change_type": item.change_type,
        "source": item.source,
        "availability": item.availability,
        "points_delta": int(item.points_delta or 0),
        "related_type": item.related_type,
        "related_id": item.related_id,
        "remark": item.remark,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def _netdisk_risk_record_to_dict(item: NetdiskRiskRecord) -> dict:
    return {
        "id": str(item.id),
        "user_id": str(item.user_id),
        "related_type": item.related_type,
        "related_id": item.related_id,
        "reason": item.reason,
        "points_due": int(item.points_due),
        "points_collected": int(item.points_collected),
        "status": item.status,
        "note": item.note,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


async def _build_netdisk_risk_related_detail(session: AsyncSession, item: NetdiskRiskRecord) -> dict:
    if item.related_type == "netdisk_upload":
        try:
            upload = await session.get(NetdiskUpload, UUID(item.related_id))
        except ValueError:
            upload = None
        resource = None
        if upload:
            resource = (
                await session.execute(
                    select(NetdiskResourceModel).where(NetdiskResourceModel.source_upload_id == str(upload.id))
                )
            ).scalar_one_or_none()
        return {
            "upload": _netdisk_upload_to_dict(upload) if upload else None,
            "resource": _resource_quality_resource_to_dict(resource) if resource else None,
        }

    if item.related_type == "netdisk_repair":
        try:
            repair = await session.get(NetdiskRepair, UUID(item.related_id))
        except ValueError:
            repair = None
        resource = await session.get(NetdiskResourceModel, repair.resource_id) if repair else None
        return {
            "repair": _netdisk_repair_to_dict(repair) if repair else None,
            "resource": _resource_quality_resource_to_dict(resource) if resource else None,
        }

    resource = await session.get(NetdiskResourceModel, item.related_id)
    return {"resource": _resource_quality_resource_to_dict(resource) if resource else None}


def _netdisk_user_notification_to_dict(item: NetdiskUserNotification) -> dict:
    return {
        "id": str(item.id),
        "user_id": str(item.user_id),
        "notice_type": item.notice_type,
        "title": item.title,
        "content": item.content,
        "related_type": item.related_type,
        "related_id": item.related_id,
        "status": item.status,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


async def _get_user_account_map(session: AsyncSession, user_ids: list[UUID]) -> dict[UUID, UserAccount]:
    if not user_ids:
        return {}
    accounts = (
        await session.execute(select(UserAccount).where(UserAccount.user_id.in_(user_ids)))
    ).scalars().all()
    return {account.user_id: account for account in accounts}


async def _get_user_map(session: AsyncSession, user_ids: list[UUID]) -> dict[UUID, User]:
    if not user_ids:
        return {}
    users = (await session.execute(select(User).where(User.id.in_(user_ids)))).scalars().all()
    return {user.id: user for user in users}


async def _get_recharge_ledger_map(session: AsyncSession, order_ids: list[UUID]) -> dict[str, PointsLedger]:
    if not order_ids:
        return {}
    order_id_texts = [str(item) for item in order_ids]
    ledgers = (
        await session.execute(
            select(PointsLedger).where(
                PointsLedger.change_type == "points_recharge",
                PointsLedger.related_id.in_(order_id_texts),
            )
        )
    ).scalars().all()
    return {str(item.related_id): item for item in ledgers}


async def _get_withdrawal_equity_ledger_map(session: AsyncSession, record_ids: list[UUID]) -> dict[str, list[EquityLedger]]:
    if not record_ids:
        return {}
    record_id_texts = [str(item) for item in record_ids]
    rows = (
        await session.execute(
            select(EquityLedger)
            .where(
                EquityLedger.related_type == "withdraw_record",
                EquityLedger.related_id.in_(record_id_texts),
            )
            .order_by(EquityLedger.created_at.asc(), EquityLedger.id.asc())
        )
    ).scalars().all()
    ledger_map: dict[str, list[EquityLedger]] = {}
    for row in rows:
        ledger_map.setdefault(str(row.related_id), []).append(row)
    return ledger_map


def _payment_order_to_dict(order: Order, user: Optional[User], ledger: Optional[PointsLedger]) -> dict:
    return {
        "id": str(order.id),
        "user_id": str(order.user_id),
        "openid": user.openid if user else "",
        "nickname": user.nickname if user else "",
        "avatar": user.avatar if user else "",
        "out_trade_no": order.out_trade_no,
        "transaction_id": order.transaction_id,
        "status": order.status,
        "amount": float(order.amount),
        "period": order.period,
        "description": order.description,
        "paid_at": order.paid_at.isoformat() if order.paid_at else None,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "updated_at": order.updated_at.isoformat() if order.updated_at else None,
        "ledger": _points_ledger_to_dict(ledger) if ledger else None,
        "points_arrived": bool(ledger),
    }


def _account_to_dict(account: Optional[UserAccount]) -> dict:
    if not account:
        return {
            "total_points": 0,
            "withdrawable_points": 0,
            "frozen_points": 0,
            "consumable_points": 0,
            "consumed_points": 0,
            "locked_withdraw_points": 0,
            "withdrawn_points": 0,
        }
    return {
        "total_points": int(account.total_points),
        "withdrawable_points": int(account.withdrawable_points),
        "frozen_points": int(account.frozen_points),
        "consumable_points": int(account.consumable_points),
        "consumed_points": int(account.consumed_points),
        "locked_withdraw_points": int(account.locked_withdraw_points),
        "withdrawn_points": int(account.withdrawn_points),
    }


def _points_ledger_to_dict(item: PointsLedger) -> dict:
    return {
        "id": str(item.id),
        "user_id": str(item.user_id),
        "change_type": item.change_type,
        "source": item.source,
        "availability": item.availability,
        "points_delta": int(item.points_delta),
        "balance_withdrawable_after": int(item.balance_withdrawable_after),
        "balance_frozen_after": int(item.balance_frozen_after),
        "balance_consumable_after": int(item.balance_consumable_after),
        "related_type": item.related_type,
        "related_id": item.related_id,
        "idempotency_key": item.idempotency_key,
        "remark": item.remark,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def _user_to_dict(user: User, account: Optional[UserAccount] = None) -> dict:
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
        "account": _account_to_dict(account),
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def _withdrawal_to_dict(
    record: WithdrawalRecord,
    user: Optional[User] = None,
    account: Optional[UserAccount] = None,
    equity_ledgers: Optional[list[EquityLedger]] = None,
) -> dict:
    return {
        "id": str(record.id),
        "user_id": str(record.user_id),
        "nickname": user.nickname if user else "",
        "avatar": user.avatar if user else "",
        "openid": user.openid if user else "",
        "invite_code": user.invite_code if user else "",
        "user_balance": float(user.balance) if user else 0.0,
        "user_frozen_balance": float(user.frozen_balance) if user else 0.0,
        "user_total_income": float(user.total_income) if user else 0.0,
        "user_total_withdrawn": float(user.total_withdrawn) if user else 0.0,
        "account": _account_to_dict(account),
        "amount": float(record.amount),
        "status": record.status,
        "batch_no": record.batch_no,
        "transfer_bill_no": record.transfer_bill_no,
        "fail_reason": record.fail_reason,
        "ip": record.ip,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "completed_at": record.completed_at.isoformat() if record.completed_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        "equity_ledgers": [_equity_ledger_to_dict(item, user) for item in (equity_ledgers or [])],
    }


def _equity_ledger_to_dict(item: EquityLedger, user: Optional[User] = None) -> dict:
    return {
        "id": str(item.id),
        "user_id": str(item.user_id),
        "nickname": user.nickname if user else "",
        "openid": user.openid if user else "",
        "invite_code": user.invite_code if user else "",
        "change_type": item.change_type,
        "amount_delta": float(item.amount_delta),
        "frozen_delta": float(item.frozen_delta),
        "total_income_delta": float(item.total_income_delta),
        "total_withdrawn_delta": float(item.total_withdrawn_delta),
        "balance_after": float(item.balance_after),
        "frozen_balance_after": float(item.frozen_balance_after),
        "total_income_after": float(item.total_income_after),
        "total_withdrawn_after": float(item.total_withdrawn_after),
        "related_type": item.related_type,
        "related_id": item.related_id,
        "idempotency_key": item.idempotency_key,
        "remark": item.remark,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def _transfer_task_to_dict(item: NetdiskTransferTask) -> dict:
    return {
        "id": str(item.id),
        "source_type": item.source_type,
        "source_ref": item.source_ref,
        "resource_id": item.resource_id,
        "title": item.title,
        "source_pan": item.source_pan,
        "source_link": item.source_link,
        "source_extract_code": item.source_extract_code,
        "target_pan": item.target_pan,
        "target_link": item.target_link,
        "target_extract_code": item.target_extract_code,
        "target_folder": item.target_folder,
        "tool_name": item.tool_name,
        "status": item.status,
        "error_message": item.error_message,
        "log_summary": item.log_summary,
        "duration_ms": int(item.duration_ms or 0),
        "attempts": int(item.attempts or 0),
        "expected_level1_amount": float(item.expected_level1_amount or 0),
        "expected_level2_amount": float(item.expected_level2_amount or 0),
        "idempotency_key": item.idempotency_key,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def _new_official_access_to_dict(item: NetdiskOfficialAccessRecord, user_map: dict) -> dict:
    user = user_map.get(item.user_id)
    level1_user = user_map.get(item.level1_user_id) if item.level1_user_id else None
    level2_user = user_map.get(item.level2_user_id) if item.level2_user_id else None
    return {
        "id": str(item.id),
        "user_id": str(item.user_id),
        "nickname": user.nickname if user else "",
        "openid": user.openid if user else "",
        "resource_id": item.resource_id,
        "unlock_ledger_id": item.unlock_ledger_id,
        "pan": item.pan,
        "level1_user_id": str(item.level1_user_id) if item.level1_user_id else "",
        "level1_nickname": level1_user.nickname if level1_user else "",
        "level1_amount": float(item.level1_amount or 0),
        "level2_user_id": str(item.level2_user_id) if item.level2_user_id else "",
        "level2_nickname": level2_user.nickname if level2_user else "",
        "level2_amount": float(item.level2_amount or 0),
        "settlement_mode": item.settlement_mode,
        "settlement_status": item.settlement_status,
        "equity_granted": bool(item.equity_granted),
        "idempotency_key": item.idempotency_key,
        "remark": item.remark,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def _parse_admin_datetime(raw: Optional[str], *, end_of_day: bool = False) -> Optional[datetime]:
    if not raw:
        return None
    value = raw.strip()
    if not value:
        return None
    try:
        if len(value) == 10:
            parsed = datetime.strptime(value, "%Y-%m-%d")
            if end_of_day:
                return parsed.replace(hour=23, minute=59, second=59, microsecond=999999)
            return parsed
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _parse_settlement_date_or_default(raw: Optional[str]):
    if not raw:
        return (datetime.utcnow() - timedelta(days=1)).date()
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None
