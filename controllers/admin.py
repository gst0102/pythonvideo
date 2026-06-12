import csv
import io
import logging
import os
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, Response
from fastapi.encoders import jsonable_encoder
from sqlmodel import and_, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.response import response
from models.base import get_session
from models.chat import ChatMessage
from models.netdisk_audit_log import NetdiskAuditLog
from models.netdisk_repair import NetdiskRepair
from models.netdisk_resource import NetdiskResource as NetdiskResourceModel
from models.netdisk_risk_record import NetdiskRiskRecord
from models.netdisk_upload import NetdiskUpload
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
    session: AsyncSession = Depends(get_session),
):
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
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    payload = await NetdiskResourceService.list_admin_repairs(
        session=session,
        status=status,
        mode=mode,
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
    session: AsyncSession = Depends(get_session),
):
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
async def admin_netdisk_ops_dashboard(session: AsyncSession = Depends(get_session)):
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

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
    point_sources = await _build_point_source_distribution(session, today_start)

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
            },
            "today_activity": {
                "uploads": int(today_uploads),
                "repairs": int(today_repairs),
                "reports": int(today_reports),
            },
            "trends": trends,
            "point_sources": point_sources,
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
    session: AsyncSession = Depends(get_session),
):
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


async def _build_point_source_distribution(session: AsyncSession, today_start: datetime) -> list[dict]:
    rows = (
        await session.execute(
            select(
                PointsLedger.source,
                PointsLedger.change_type,
                func.coalesce(func.sum(PointsLedger.points_delta), 0),
                func.count(),
            )
            .where(PointsLedger.created_at >= today_start, PointsLedger.points_delta != 0)
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
