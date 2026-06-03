"""Payment business logic."""

import logging
from datetime import datetime, timedelta
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from models.commission import CommissionRecord
from models.order import Order
from models.user import User

logger = logging.getLogger(__name__)

COMMISSION_LEVEL1_RATE = 0.10
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
    if buyer.parent_id:
        await _create_commission_record(
            session,
            buyer.parent_id,
            buyer.id,
            order.id,
            amount,
            COMMISSION_LEVEL1_RATE * 100,
            round(amount * COMMISSION_LEVEL1_RATE, 2),
            1,
        )
    if buyer.grand_parent_id:
        await _create_commission_record(
            session,
            buyer.grand_parent_id,
            buyer.id,
            order.id,
            amount,
            COMMISSION_LEVEL2_RATE * 100,
            round(amount * COMMISSION_LEVEL2_RATE, 2),
            2,
        )


async def _create_commission_record(
    session: AsyncSession,
    user_id: UUID,
    from_user_id: UUID,
    order_id: UUID,
    order_amount: float,
    rate: float,
    commission_amount: float,
    level: int,
) -> None:
    if commission_amount <= 0:
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
        status="settled",
    )
    session.add(record)

    result = await session.execute(select(User).where(User.id == user_id))
    inviter = result.scalar_one_or_none()
    if inviter:
        inviter.balance += commission_amount
        inviter.total_income += commission_amount
        inviter.updated_at = datetime.utcnow()

    await session.flush()


def _parse_paid_at(paid_at_str: str) -> datetime:
    if not paid_at_str:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(paid_at_str)
    except ValueError:
        return datetime.utcnow()
