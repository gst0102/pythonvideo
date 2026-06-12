import csv
import io
import logging
import os
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Query, Response
from fastapi.encoders import jsonable_encoder
from sqlalchemy import or_
from sqlmodel import and_, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.response import response
from models.base import get_session
from models.chat import ChatMessage
from models.netdisk_audit_log import NetdiskAuditLog
from models.netdisk_quality_alert import NetdiskQualityAlert
from models.netdisk_quality_daily_stat import NetdiskQualityDailyStat
from models.netdisk_repair import NetdiskRepair
from models.netdisk_resource import NetdiskResource as NetdiskResourceModel
from models.netdisk_risk_record import NetdiskRiskRecord
from models.netdisk_upload import NetdiskUpload
from models.netdisk_user_notification import NetdiskUserNotification
from models.points_ledger import PointsLedger
from models.user import User
from models.user_account import UserAccount
from models.withdrawal import WithdrawalRecord
from schemas.admin_settlement import AdminGameSettlementTriggerRequest, AdminGameSettlementUpsertRequest
from schemas.netdisk import NetdiskAdminAuditRequest
from schemas.user import AdminReplyRequest, AdminUserVipUpdateRequest, ConfigUpdateRequest, PaginatedResponse
from services.chat_service import ChatService
from services.config_service import ConfigService
from services.game_ad_service import build_game_bonus_ad_config_payload, normalize_game_bonus_ad_config
from services.game_settlement_service import GameSettlementService
from services.netdisk_quality_stat_service import build_resource_quality_day_stat, refresh_netdisk_quality_daily_stats
from services.netdisk_resource_service import NetdiskResourceService
from services.points_account_service import PointsAccountService
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


@router.get("/netdisk/uploads", summary="admin netdisk upload list")
async def admin_list_netdisk_uploads(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    payload = await NetdiskResourceService.list_admin_uploads(
        session=session,
        status=status,
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
        payload = await NetdiskResourceService.approve_upload(session, upload_id, req.note)
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
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    point_source_start = today_start - timedelta(days=6) if points_range == "7d" else today_start

    total_users = (await session.execute(select(func.count()).select_from(User))).scalar() or 0
    today_new_users = (
        await session.execute(select(func.count()).select_from(User).where(User.created_at >= today_start))
    ).scalar() or 0

    points_gain = (
        await session.execute(
            select(
                func.count(func.distinct(PointsLedger.user_id)),
                func.coalesce(func.sum(PointsLedger.points_delta), 0),
            ).where(PointsLedger.created_at >= today_start, PointsLedger.points_delta > 0)
        )
    ).one()
    points_spend = (
        await session.execute(
            select(
                func.count(func.distinct(PointsLedger.user_id)),
                func.coalesce(func.sum(PointsLedger.points_delta), 0),
            ).where(PointsLedger.created_at >= today_start, PointsLedger.points_delta < 0)
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
    trends = await _build_netdisk_ops_trends(session, today_start)
    point_sources = await _build_point_source_distribution(session, point_source_start)
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
            "points": {
                "today_gain_users": int(points_gain[0] or 0),
                "today_gain_points": int(points_gain[1] or 0),
                "today_spend_users": int(points_spend[0] or 0),
                "today_spend_points": abs(int(points_spend[1] or 0)),
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
                "uploads": int(today_uploads),
                "repairs": int(today_repairs),
                "reports": int(today_reports),
            },
            "trends": trends,
            "point_source_range": points_range,
            "point_sources": point_sources,
            "quality_range": quality_range,
            "resource_quality_rankings": resource_quality_rankings,
            "resource_quality_alerts": quality_alerts,
            "quality_stats_runtime": quality_runtime,
            "generated_at": datetime.utcnow().isoformat(),
        }
    )


@router.post("/netdisk/dev-seed", summary="seed netdisk review demo data")
async def admin_seed_netdisk_review_demo(session: AsyncSession = Depends(get_session)):
    if os.getenv("ENABLE_DEV_LOGIN", "false").lower() != "true":
        return response([], 403, "dev seed disabled")

    user_result = await session.execute(select(User).where(User.openid == "dev-netdisk-review"))
    user = user_result.scalar_one_or_none()
    if not user:
        user = User(
            openid="dev-netdisk-review",
            nickname="网盘审核演示用户",
            avatar="",
            invite_code=f"ND{uuid4().hex[:8]}",
        )
        session.add(user)
        await session.flush()

    account_result = await session.execute(select(UserAccount).where(UserAccount.user_id == user.id))
    account = account_result.scalar_one_or_none()
    if not account:
        session.add(UserAccount(user_id=user.id, consumable_points=2, total_points=2))

    marker = datetime.utcnow().strftime("%m%d%H%M%S%f")
    uploads = [
        NetdiskUpload(
            user_id=user.id,
            title=f"演示待审核上传 {marker}",
            category="学习办公",
            pan="夸克",
            link="https://pan.quark.cn/s/demo-pending",
            extract_code="demo",
            unzip_code="",
            description="用于后台审核页面验收的待审核上传。",
            status="pending",
            reward_points=5,
            audit_note="待系统/人工确认后释放冻结积分。",
        ),
        NetdiskUpload(
            user_id=user.id,
            title=f"演示已通过上传 {marker}",
            category="自媒体素材",
            pan="百度",
            link="https://pan.baidu.com/s/demo-approved",
            extract_code="yx88",
            unzip_code="yx2026",
            description="用于测试确认失效和处罚动作。",
            status="approved",
            reward_points=5,
            audit_note="已通过，可测试确认失效。",
        ),
    ]
    session.add_all(uploads)

    hidden_resource_id = f"dev-hidden-{marker}"
    session.add(
        NetdiskResourceModel(
            id=hidden_resource_id,
            title=f"演示隐藏资源 {marker}",
            category="办公模板",
            pan="阿里",
            level="featured",
            cost_points=10,
            downloads=18,
            favorites=3,
            description="用于测试后台恢复上架。",
            link="https://www.aliyundrive.com/s/demo-hidden",
            extract_code="demo",
            unzip_code="",
            is_active=False,
        )
    )

    repairs = [
        NetdiskRepair(
            user_id=user.id,
            resource_id=hidden_resource_id,
            mode="repair",
            resource_title=f"演示隐藏资源 {marker}",
            pan="阿里",
            link="https://www.aliyundrive.com/s/demo-repair",
            extract_code="rp88",
            note="演示补链，等待审核。",
            status="pending",
            reward_points=5,
            audit_note="补链通过后释放冻结奖励。",
        ),
        NetdiskRepair(
            user_id=user.id,
            resource_id=hidden_resource_id,
            mode="report",
            resource_title=f"演示隐藏资源 {marker}",
            pan="阿里",
            note="演示投诉：链接疑似失效。",
            status="pending",
            reward_points=0,
            audit_note="投诉待核验，不奖励积分。",
        ),
    ]
    session.add_all(repairs)

    session.add(
        NetdiskRiskRecord(
            user_id=user.id,
            related_type="netdisk_upload",
            related_id=f"demo-upload-{marker}",
            reason="upload_reward_invalid",
            points_due=8,
            points_collected=2,
            status="open",
            note="演示待追缴：用户可用积分不足，剩余 8 分待追缴。",
            idempotency_key=f"dev_netdisk_risk:{marker}",
        )
    )
    await session.flush()
    return response(
        data={
            "uploads": len(uploads),
            "repairs": len(repairs),
            "resources": 1,
            "risk_records": 1,
        },
        msg="netdisk review demo data seeded",
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


async def _build_point_source_distribution(session: AsyncSession, start_dt: datetime) -> list[dict]:
    rows = (
        await session.execute(
            select(
                PointsLedger.source,
                PointsLedger.change_type,
                func.coalesce(func.sum(PointsLedger.points_delta), 0),
                func.count(),
            )
            .where(PointsLedger.created_at >= start_dt, PointsLedger.points_delta != 0)
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
    today = datetime.utcnow().date()
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
    today = datetime.utcnow().date()
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
