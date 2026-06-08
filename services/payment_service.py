"""Payment business logic."""

import logging
import math
from datetime import datetime, timedelta
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from models.commission import CommissionRecord
from models.order import Order
from models.user import User
from services.config_service import ConfigService
from services.points_account_service import PointsAccountService

logger = logging.getLogger(__name__)

COMMISSION_LEVEL1_RATE = 0.50
COMMISSION_LEVEL2_RATE = 0.05
PERIOD_DAYS = {"month": 30, "quarter": 90, "year": 365}


class PaymentService:
    @staticmethod
    async def handle_payment_success(
        session: AsyncSession,
        out_trade_no: str,
        transaction_id: str,
        total_fee_in_fen: int,
        paid_at: str,
    ) -> bool:
        result = await session.execute(select(Order).where(Order.out_trade_no == out_trade_no))
        order = result.scalar_one_or_none()
        if not order:
            logger.error("[Payment] order not found: %s", out_trade_no)
            return False

        if order.status == "paid":
            return True

        amount_yuan = total_fee_in_fen / 100.0
        order.status = "paid"
        order.transaction_id = transaction_id
        order.amount = amount_yuan
        order.paid_at = _parse_paid_at(paid_at)
        order.updated_at = datetime.utcnow()
        await session.flush()

        await _activate_vip(session, order.user_id, order.period, order.duration_days)
        await _grant_vip_gift_points(session, order)
        await _calculate_commission(session, order)
        return True


async def _activate_vip(session: AsyncSession, user_id: UUID, period: str, duration_days: int = 0) -> None:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return

    days = duration_days or PERIOD_DAYS.get(period, 30)
    now = datetime.utcnow()
    if user.is_vip and user.vip_expire_at and user.vip_expire_at > now:
        user.vip_expire_at = user.vip_expire_at + timedelta(days=days)
    else:
        user.vip_expire_at = now + timedelta(days=days)

    user.is_vip = True
    user.updated_at = datetime.utcnow()
    await session.flush()


async def _calculate_commission(session: AsyncSession, order: Order) -> None:
    result = await session.execute(select(User).where(User.id == order.user_id))
    buyer = result.scalar_one_or_none()
    if not buyer:
        return

    amount = float(order.amount)
    level1_rate, level2_rate = await _get_commission_rates(session)
    points_config = await ConfigService.get(session, "stage2_points_config")
    exchange_rate = _get_points_exchange_rate(points_config)
    if buyer.parent_id:
        await _create_commission_record(
            session,
            buyer.parent_id,
            buyer.id,
            order.id,
            amount,
            level1_rate * 100,
            round(amount * level1_rate, 2),
            _calculate_rebate_points(amount, level1_rate, exchange_rate),
            1,
        )
    if buyer.grand_parent_id:
        await _create_commission_record(
            session,
            buyer.grand_parent_id,
            buyer.id,
            order.id,
            amount,
            level2_rate * 100,
            round(amount * level2_rate, 2),
            _calculate_rebate_points(amount, level2_rate, exchange_rate),
            2,
        )


async def _grant_vip_gift_points(session: AsyncSession, order: Order) -> None:
    package = await _get_vip_package(session, order.period)
    gift_points = int(package.get("gift_points") or 0)
    if gift_points <= 0:
        return

    await PointsAccountService.add_points(
        session=session,
        user_id=order.user_id,
        points=gift_points,
        source="vip",
        change_type="vip_gift",
        availability="withdrawable",
        idempotency_key=f"vip_gift:{order.id}",
        related_type="order",
        related_id=str(order.id),
        remark=f"vip gift points: {order.period}",
    )


async def _get_vip_package(session: AsyncSession, period: str) -> dict:
    config = await ConfigService.get_vip_packages(session)
    packages = config.get("packages") or []
    normalized_period = str(period or "month").strip().lower()
    for package in packages:
        if str(package.get("id") or "").strip().lower() == normalized_period:
            return package
    return {"gift_points": 0}


async def _get_commission_rates(session: AsyncSession) -> tuple[float, float]:
    config = await ConfigService.get(session, "commission_settings")
    level1 = _percent_to_rate(config.get("level1_rate"), COMMISSION_LEVEL1_RATE)
    level2 = _percent_to_rate(config.get("level2_rate"), COMMISSION_LEVEL2_RATE)
    return level1, level2


def _percent_to_rate(value, default_rate: float) -> float:
    try:
        percent = float(value)
    except (TypeError, ValueError):
        return default_rate
    if percent < 0:
        return 0.0
    return percent / 100


async def _create_commission_record(
    session: AsyncSession,
    user_id: UUID,
    from_user_id: UUID,
    order_id: UUID,
    order_amount: float,
    rate: float,
    commission_amount: float,
    rebate_points: int,
    level: int,
) -> None:
    if commission_amount <= 0 or rebate_points <= 0:
        return

    existing_result = await session.execute(
        select(CommissionRecord).where(
            CommissionRecord.user_id == user_id,
            CommissionRecord.from_user_id == from_user_id,
            CommissionRecord.order_id == order_id,
            CommissionRecord.level == level,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing:
        return

    record = CommissionRecord(
        user_id=user_id,
        from_user_id=from_user_id,
        order_id=order_id,
        order_amount=order_amount,
        commission_rate=rate,
        commission_amount=commission_amount,
        level=level,
        type="vip_recharge",
        status="pending",
    )
    session.add(record)
    await session.flush()

    await PointsAccountService.add_points(
        session=session,
        user_id=user_id,
        points=rebate_points,
        source="invite",
        change_type="invite_rebate_frozen",
        availability="frozen",
        idempotency_key=f"invite_rebate:{order_id}:{level}:{user_id}",
        related_type="commission_record",
        related_id=str(record.id),
        remark=f"level {level} vip rebate frozen points",
    )


def _parse_paid_at(paid_at_str: str) -> datetime:
    if not paid_at_str:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(paid_at_str)
    except ValueError:
        return datetime.utcnow()


def _get_points_exchange_rate(config: dict) -> int:
    value = config.get("exchange_rate") or config.get("points_exchange_rate") or 100
    try:
        return max(int(value), 1)
    except (TypeError, ValueError):
        return 100


def _calculate_rebate_points(amount: float, rate: float, exchange_rate: int) -> int:
    return int(math.floor(float(amount) * float(rate) * int(exchange_rate)))
