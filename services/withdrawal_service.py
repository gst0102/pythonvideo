"""
Withdrawal service.

This keeps the state flow consistent across:
1. mini program apply
2. admin submit/reject
3. WeChat transfer callback
"""

import logging
import os
import random
import string
import time
from datetime import datetime
from typing import List, Optional, Tuple
from uuid import UUID

from dotenv import load_dotenv
from sqlmodel import and_, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.wepay import WeChatPayV3
from models.user import User
from models.withdrawal import WithdrawalRecord
from services.config_service import ConfigService

load_dotenv()
logger = logging.getLogger(__name__)

PENDING_TRANSFER_STATES = {"WAIT_USER_CONFIRM", "ACCEPTED", "PROCESSING"}


def _get_transfer_notify_url() -> str:
    return (os.getenv("WECHAT_TRANSFER_NOTIFY_URL") or os.getenv("TRANSFER_NOTIFY_URL") or "").strip()


def _get_wx_pay() -> WeChatPayV3:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return WeChatPayV3(
        mch_id=os.getenv("mchid", ""),
        app_id=os.getenv("APPID", ""),
        api_v3_key=os.getenv("APIv3", ""),
        private_key_path=os.path.join(base_dir, "certs", "apiclient_key.pem"),
        serial_no=os.getenv("serial_no", ""),
        notify_url=_get_transfer_notify_url(),
    )


class WithdrawalService:
    @staticmethod
    async def apply_withdrawal(
        session: AsyncSession,
        user_id: UUID,
        amount: float,
        ip: Optional[str] = None,
        openid: Optional[str] = None,
    ) -> Tuple[Optional[WithdrawalRecord], Optional[str]]:
        amount = round(float(amount), 2)

        transfer_notify_url = _get_transfer_notify_url()
        if not transfer_notify_url:
            return None, "WECHAT_TRANSFER_NOTIFY_URL is not configured"

        config = await ConfigService.get_withdrawal_config(session)
        if not config.get("enabled", True):
            return None, "withdrawal is disabled"

        min_amount = round(float(config.get("min_amount", 0.10)), 2)
        max_amount = round(float(config.get("max_amount", 200.00)), 2)
        daily_limit = round(float(config.get("daily_limit", 100.00)), 2)

        if amount < min_amount:
            return None, f"minimum amount is {min_amount:.2f}"
        if amount > max_amount:
            return None, f"maximum amount is {max_amount:.2f}"

        user = await session.get(User, user_id)
        if not user:
            return None, "user not found"

        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        daily_result = await session.execute(
            select(func.coalesce(func.sum(WithdrawalRecord.amount), 0)).where(
                and_(
                    WithdrawalRecord.user_id == user_id,
                    WithdrawalRecord.created_at >= today_start,
                    WithdrawalRecord.status.in_(["processing", "success"]),
                )
            )
        )
        daily_total = round(float(daily_result.scalar() or 0), 2)
        if daily_total + amount > daily_limit:
            return None, f"daily limit exceeded, current total {daily_total:.2f}"

        pending_result = await session.execute(
            select(WithdrawalRecord)
            .where(
                and_(
                    WithdrawalRecord.user_id == user_id,
                    WithdrawalRecord.status == "processing",
                )
            )
            .order_by(WithdrawalRecord.created_at.desc())
            .limit(1)
        )
        pending = pending_result.scalar_one_or_none()

        is_retry = False
        if pending:
            if abs(float(pending.amount) - amount) < 0.001:
                record = pending
                is_retry = True
            else:
                user.balance = round(float(user.balance) + float(pending.amount), 2)
                user.frozen_balance = round(float(user.frozen_balance) - float(pending.amount), 2)
                pending.status = "failed"
                pending.fail_reason = "amount_changed_by_user"
                pending.updated_at = datetime.utcnow()
                await session.flush()

        if not is_retry:
            available = round(float(user.balance) - float(user.frozen_balance), 2)
            if amount > available:
                return None, f"insufficient available balance: {available:.2f}"

            user.balance = round(float(user.balance) - amount, 2)
            user.frozen_balance = round(float(user.frozen_balance) + amount, 2)
            user.updated_at = datetime.utcnow()

            record = WithdrawalRecord(
                user_id=user_id,
                amount=amount,
                status="processing",
                batch_no=_generate_batch_no(),
                ip=ip,
            )
            session.add(record)
            await session.flush()

        target_openid = openid or user.openid
        if not target_openid:
            if not is_retry:
                await _rollback_balance(session, user, record, amount, "missing_openid")
            return None, "missing openid"

        submitted_record, error = await WithdrawalService.submit_processing_withdrawal(
            session,
            record.id,
            openid=target_openid,
            allow_existing_submission=is_retry,
        )
        if error:
            if not is_retry:
                await _rollback_balance(session, user, record, amount, error)
            return None, error
        return submitted_record, None

    @staticmethod
    async def submit_processing_withdrawal(
        session: AsyncSession,
        record_id: UUID,
        openid: Optional[str] = None,
        allow_existing_submission: bool = False,
    ) -> Tuple[Optional[WithdrawalRecord], Optional[str]]:
        record = await session.get(WithdrawalRecord, record_id)
        if not record:
            return None, "withdrawal record not found"
        if record.status != "processing":
            return None, "withdrawal is not in processing state"

        user = await session.get(User, record.user_id)
        if not user:
            return None, "user not found"

        target_openid = openid or user.openid
        if not target_openid:
            return None, "missing openid"

        if record.transfer_bill_no and not allow_existing_submission:
            return record, "transfer already submitted, waiting callback"

        transfer_result = _get_wx_pay().merchant_transfer(
            out_bill_no=record.batch_no,
            openid=target_openid,
            amount=float(record.amount),
            transfer_remark="withdrawal",
        )
        state = str(transfer_result.get("state") or "")
        transfer_bill_no = str(transfer_result.get("transfer_bill_no") or "")

        if transfer_bill_no:
            record.transfer_bill_no = transfer_bill_no
        record.updated_at = datetime.utcnow()

        if state == "SUCCESS":
            await WithdrawalService.handle_transfer_success(
                session,
                record.batch_no,
                transfer_bill_no or record.batch_no,
            )
            await session.flush()
            return record, None

        if state in PENDING_TRANSFER_STATES:
            await session.flush()
            return record, None

        return None, f"unexpected transfer state: {state or 'UNKNOWN'}"

    @staticmethod
    async def handle_transfer_success(
        session: AsyncSession,
        batch_no: str,
        transfer_bill_no: str,
    ) -> bool:
        result = await session.execute(select(WithdrawalRecord).where(WithdrawalRecord.batch_no == batch_no))
        record = result.scalar_one_or_none()
        if not record:
            return False
        if record.status != "processing":
            return True

        record.status = "success"
        record.transfer_bill_no = transfer_bill_no
        record.completed_at = datetime.utcnow()
        record.updated_at = datetime.utcnow()

        user = await session.get(User, record.user_id)
        if user:
            amount = float(record.amount)
            user.frozen_balance = round(float(user.frozen_balance) - amount, 2)
            user.total_withdrawn = round(float(user.total_withdrawn) + amount, 2)
            user.updated_at = datetime.utcnow()
        return True

    @staticmethod
    async def handle_transfer_failed(
        session: AsyncSession,
        batch_no: str,
        reason: str = "transfer_failed",
    ) -> bool:
        result = await session.execute(select(WithdrawalRecord).where(WithdrawalRecord.batch_no == batch_no))
        record = result.scalar_one_or_none()
        if not record:
            return False
        if record.status != "processing":
            return True

        record.status = "failed"
        record.fail_reason = reason
        record.completed_at = datetime.utcnow()
        record.updated_at = datetime.utcnow()

        user = await session.get(User, record.user_id)
        if user:
            amount = float(record.amount)
            user.balance = round(float(user.balance) + amount, 2)
            user.frozen_balance = round(float(user.frozen_balance) - amount, 2)
            user.updated_at = datetime.utcnow()
        return True

    @staticmethod
    async def release_frozen_amount(
        session: AsyncSession,
        user_id: UUID,
    ) -> Tuple[float, List[str], Optional[str]]:
        user = await session.get(User, user_id)
        if not user:
            return 0, [], "user not found"

        frozen = round(float(user.frozen_balance), 2)
        if frozen <= 0:
            return 0, [], None

        result = await session.execute(
            select(WithdrawalRecord).where(
                and_(
                    WithdrawalRecord.user_id == user_id,
                    WithdrawalRecord.status == "processing",
                )
            )
        )
        pending_records = result.scalars().all()

        if pending_records:
            cleared_batch_nos: List[str] = []
            total_cleared = 0.0
            for record in pending_records:
                if not record.created_at:
                    continue
                hours_since = (datetime.utcnow() - record.created_at.replace(tzinfo=None)).total_seconds() / 3600
                if hours_since <= 24:
                    continue

                amount = float(record.amount)
                user.balance = round(float(user.balance) + amount, 2)
                user.frozen_balance = round(float(user.frozen_balance) - amount, 2)
                record.status = "failed"
                record.fail_reason = "timeout_auto_release"
                record.completed_at = datetime.utcnow()
                record.updated_at = datetime.utcnow()
                cleared_batch_nos.append(record.batch_no)
                total_cleared += amount

            if cleared_batch_nos:
                user.updated_at = datetime.utcnow()
                await session.flush()
                return round(total_cleared, 2), cleared_batch_nos, None

            return 0, [], f"{len(pending_records)} processing withdrawals are still within 24 hours"

        user.balance = round(float(user.balance) + frozen, 2)
        user.frozen_balance = 0
        user.updated_at = datetime.utcnow()
        await session.flush()
        return frozen, [], None

    @staticmethod
    async def get_records(
        session: AsyncSession,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[WithdrawalRecord], int]:
        total_result = await session.execute(
            select(func.count()).select_from(WithdrawalRecord).where(WithdrawalRecord.user_id == user_id)
        )
        total = total_result.scalar() or 0

        list_result = await session.execute(
            select(WithdrawalRecord)
            .where(WithdrawalRecord.user_id == user_id)
            .order_by(WithdrawalRecord.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(list_result.scalars().all()), total


def _generate_batch_no() -> str:
    timestamp = str(int(time.time() * 1000))
    random_suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"{timestamp}{random_suffix}"


async def _rollback_balance(
    session: AsyncSession,
    user: User,
    record: WithdrawalRecord,
    amount: float,
    reason: str,
) -> None:
    user.balance = round(float(user.balance) + amount, 2)
    user.frozen_balance = round(float(user.frozen_balance) - amount, 2)
    user.updated_at = datetime.utcnow()

    record.status = "failed"
    record.fail_reason = reason
    record.completed_at = datetime.utcnow()
    record.updated_at = datetime.utcnow()

    await session.flush()
