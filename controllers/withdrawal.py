import base64
import json
import logging
import os

from Crypto.Cipher import AES
from fastapi import APIRouter, Depends, Query, Request
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.certKey import verify_signature
from core.response import response
from jwt_create import get_current_user
from models.base import get_session, get_session_ctx
from models.equity_ledger import EquityLedger
from models.user import User
from schemas.points import (
    PointsWithdrawalApplyRequest,
    PointsWithdrawalApplyResponse,
    PointsWithdrawalSummaryResponse,
)
from schemas.user import PaginatedResponse, WithdrawalApplyRequest, WithdrawalConfigResponse
from services.config_service import ConfigService
from services.withdrawal_service import PENDING_TRANSFER_STATES, WithdrawalService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/withdrawal", tags=["withdrawal"])


@router.get("/config", summary="withdrawal config")
async def get_config(session: AsyncSession = Depends(get_session)):
    config = await ConfigService.get_withdrawal_config(session)
    return response(
        data=WithdrawalConfigResponse(
            min_amount=float(config.get("min_amount", 0.01)),
            max_amount=float(config.get("max_amount", 100.00)),
            daily_limit=float(config.get("daily_limit", 100.00)),
            daily_count_limit=int(config.get("daily_count_limit", 1) or 1),
            service_time=str(config.get("service_time", "每日00:00-24:00可提交提现申请")),
            arrival_time=str(config.get("arrival_time", "预计24小时内到账，具体以微信支付到账时间为准")),
            tips=str(config.get("tips", "")),
        ).model_dump()
    )


@router.post("/apply", summary="apply withdrawal")
async def apply_withdrawal(
    req: WithdrawalApplyRequest,
    request: Request,
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).where(User.openid == openid))
    user = result.scalar_one_or_none()
    if not user:
        return response([], 404, "user not found")

    record, error = await WithdrawalService.apply_withdrawal(
        session,
        user.id,
        req.amount,
        openid=openid,
        ip=request.client.host if request.client else None,
    )
    if error:
        return response([], 400, error)

    return response(
        data={
            "record_id": str(record.id),
            "amount": float(record.amount),
            "status": record.status,
            "batch_no": record.batch_no,
            "transfer_bill_no": record.transfer_bill_no or "",
            "created_at": record.created_at.isoformat() if record.created_at else None,
        },
        msg="withdrawal submitted",
    )


@router.get("/points/summary", summary="points withdrawal summary")
async def get_points_withdrawal_summary(
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).where(User.openid == openid))
    user = result.scalar_one_or_none()
    if not user:
        return response([], 404, "user not found")

    payload = await WithdrawalService.get_points_withdrawal_summary(session, user.id)
    return response(data=PointsWithdrawalSummaryResponse(**payload).model_dump(mode="json"))


@router.post("/points/apply", summary="apply points withdrawal")
async def apply_points_withdrawal(
    req: PointsWithdrawalApplyRequest,
    request: Request,
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).where(User.openid == openid))
    user = result.scalar_one_or_none()
    if not user:
        return response([], 404, "user not found")

    record, account, error = await WithdrawalService.apply_points_withdrawal(
        session,
        user.id,
        req.points_amount,
        openid=openid,
        ip=request.client.host if request.client else None,
    )
    if error or not record or not account:
        return response([], 400, error or "withdrawal failed")

    return response(
        data=PointsWithdrawalApplyResponse(
            record_id=str(record.id),
            points_amount=req.points_amount,
            amount=float(record.amount),
            status=record.status,
            batch_no=record.batch_no,
            transfer_bill_no=record.transfer_bill_no or "",
            created_at=record.created_at.isoformat() if record.created_at else None,
            account=account,
        ).model_dump(mode="json"),
        msg="points withdrawal submitted",
    )


@router.get("/records", summary="withdrawal records")
async def get_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).where(User.openid == openid))
    user = result.scalar_one_or_none()
    if not user:
        return response([], 404, "user not found")

    records, total = await WithdrawalService.get_records(session, user.id, page, page_size)
    items = [
        {
            "id": str(record.id),
            "amount": float(record.amount),
            "status": record.status,
            "batch_no": record.batch_no,
            "transfer_bill_no": record.transfer_bill_no,
            "fail_reason": record.fail_reason,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "completed_at": record.completed_at.isoformat() if record.completed_at else None,
        }
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
    )


@router.get("/equity-ledger", summary="equity cash ledger")
async def get_equity_ledger(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).where(User.openid == openid))
    user = result.scalar_one_or_none()
    if not user:
        return response([], 404, "user not found")

    total_result = await session.execute(
        select(func.count()).select_from(EquityLedger).where(EquityLedger.user_id == user.id)
    )
    total = int(total_result.scalar() or 0)
    rows_result = await session.execute(
        select(EquityLedger)
        .where(EquityLedger.user_id == user.id)
        .order_by(EquityLedger.created_at.desc(), EquityLedger.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = list(rows_result.scalars().all())
    items = [
        {
            "id": str(item.id),
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
            "remark": item.remark,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }
        for item in rows
    ]
    return response(
        data=PaginatedResponse(
            list=items,
            total=total,
            page=page,
            page_size=page_size,
            has_more=((page - 1) * page_size + len(items)) < total,
        ).model_dump()
    )


@router.post("/release-frozen", summary="release frozen amount")
async def release_frozen(
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).where(User.openid == openid))
    user = result.scalar_one_or_none()
    if not user:
        return response([], 404, "user not found")

    released, cleared_nos, error = await WithdrawalService.release_frozen_amount(session, user.id)
    if error:
        return response(data={"released": 0, "frozen": float(user.frozen_balance)}, code=400, msg=error)

    return response(
        data={
            "released": released,
            "cleared_batch_nos": cleared_nos,
            "remaining_frozen": round(float(user.frozen_balance), 2),
            "balance": round(float(user.balance), 2),
        },
        msg="frozen amount released",
    )


@router.post("/transfer/notify", summary="wechat transfer callback")
async def transfer_notify(request: Request):
    try:
        body = await request.body()
        body_str = body.decode("utf-8")
        headers = request.headers

        timestamp = headers.get("wechatpay-timestamp")
        nonce = headers.get("wechatpay-nonce")
        signature = headers.get("wechatpay-signature")
        serial = headers.get("wechatpay-serial")
        if not all([timestamp, nonce, signature, serial]):
            logger.error("[TransferNotify] missing signature headers")
            return {"code": "FAIL", "message": "missing signature headers"}

        sign_str = f"{timestamp}\n{nonce}\n{body_str}\n"
        if not await verify_signature(sign_str, signature, serial):
            logger.error("[TransferNotify] invalid signature")
            return {"code": "FAIL", "message": "invalid signature"}

        notify_data = json.loads(body_str)
        resource = notify_data.get("resource", {})
        if resource.get("ciphertext"):
            decrypted = _decrypt_transfer_resource(
                resource["ciphertext"],
                resource.get("nonce", ""),
                os.getenv("APIv3", ""),
                resource.get("associated_data", ""),
            )
            transfer_data = json.loads(decrypted)
        else:
            transfer_data = notify_data

        batch_no = transfer_data.get("out_bill_no") or transfer_data.get("batch_no")
        transfer_bill_no = transfer_data.get("transfer_bill_no") or ""
        state = transfer_data.get("state") or transfer_data.get("batch_status") or ""
        fail_reason = transfer_data.get("fail_reason") or transfer_data.get("message") or "transfer_failed"
        if not batch_no:
            return {"code": "FAIL", "message": "missing out_bill_no"}

        async with get_session_ctx() as session:
            if state in {"SUCCESS", "FINISHED"}:
                await WithdrawalService.handle_transfer_success(session, batch_no, transfer_bill_no or batch_no)
            elif state in {"FAIL", "CLOSED"}:
                await WithdrawalService.handle_transfer_failed(session, batch_no, fail_reason)
            elif state in PENDING_TRANSFER_STATES:
                logger.info("[TransferNotify] pending batch=%s state=%s", batch_no, state)
            else:
                logger.warning("[TransferNotify] unknown state batch=%s state=%s", batch_no, state)

        return {"code": "SUCCESS", "message": "processed"}
    except Exception as exc:
        logger.error("[TransferNotify] callback failed: %s", exc, exc_info=True)
        return {"code": "SUCCESS", "message": "processed"}


def _decrypt_transfer_resource(ciphertext: str, nonce: str, key: str, associated_data: str) -> str:
    cipher = AES.new(key.encode("utf-8"), AES.MODE_GCM, nonce=nonce.encode("utf-8"))
    cipher.update(associated_data.encode("utf-8"))
    ciphertext_bytes = base64.b64decode(ciphertext)
    tag = ciphertext_bytes[-16:]
    encrypted_data = ciphertext_bytes[:-16]
    return cipher.decrypt_and_verify(encrypted_data, tag).decode("utf-8")
