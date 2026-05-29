"""
支付服务 — payment_service

MVC 架构中的 Service 层，处理支付回调相关业务逻辑。

迁移来源:
  - weixinpay.py 中的 update_order_payment_status
  - 云函数中的佣金计算逻辑（支付成功 → 计算分销佣金）

核心功能:
  1. 支付成功回调处理
  2. VIP 激活（延长到期时间）
  3. 自动计算两级分销佣金
  4. 更新邀请人余额
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from models.user import User
from models.order import Order
from models.commission import CommissionRecord

logger = logging.getLogger(__name__)

# 分销佣金比例
COMMISSION_LEVEL1_RATE = 0.10   # 一级 10%
COMMISSION_LEVEL2_RATE = 0.05   # 二级 5%

# 套餐对应的 VIP 天数
PERIOD_DAYS = {
    "month": 30,
    "quarter": 90,
    "year": 365,
}


class PaymentService:
    """支付业务逻辑服务"""

    @staticmethod
    async def handle_payment_success(
        session: AsyncSession,
        out_trade_no: str,
        transaction_id: str,
        total_fee_in_fen: int,
        paid_at: str,
    ) -> bool:
        """
        处理支付成功回调。

        业务流:
          1. 更新订单状态为 paid
          2. 激活/延长用户 VIP
          3. 计算并发放两级分销佣金
        """
        # 1. 查询订单
        stmt = select(Order).where(Order.out_trade_no == out_trade_no)
        result = await session.execute(stmt)
        order = result.scalar_one_or_none()

        if not order:
            logger.error(f"[Payment] 订单不存在: {out_trade_no}")
            return False

        if order.status == "paid":
            logger.warning(f"[Payment] 订单已支付，忽略重复回调: {out_trade_no}")
            return True  # 幂等

        # 2. 更新订单
        amount_yuan = total_fee_in_fen / 100.0
        order.status = "paid"
        order.transaction_id = transaction_id
        order.amount = amount_yuan
        order.paid_at = _parse_paid_at(paid_at)
        order.updated_at = datetime.utcnow()
        await session.flush()

        # 3. 激活 VIP
        await _activate_vip(session, order.user_id, order.period, order.duration_days)

        # 4. 计算分销佣金
        await _calculate_commission(session, order)

        logger.info(f"[Payment] 支付处理完成: {out_trade_no}, 金额={amount_yuan}元")
        return True


# ── 内部函数 ───────────────────────────────────────────────────

async def _activate_vip(session: AsyncSession, user_id: UUID, period: str, duration_days: int = 0):
    """激活/延长用户 VIP"""
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        return

    days = duration_days or PERIOD_DAYS.get(period, 30)
    now = datetime.utcnow()

    # 如果已有 VIP 且未过期，累加天数；否则从今天开始
    if user.is_vip and user.vip_expire_at and user.vip_expire_at > now:
        user.vip_expire_at = user.vip_expire_at + timedelta(days=days)
    else:
        user.vip_expire_at = now + timedelta(days=days)

    user.is_vip = True
    user.updated_at = datetime.utcnow()
    await session.flush()
    logger.info(f"[VIP] 用户 {user_id} VIP 激活，到期: {user.vip_expire_at}")


async def _calculate_commission(session: AsyncSession, order: Order):
    """计算并发放两级分销佣金"""
    stmt = select(User).where(User.id == order.user_id)
    result = await session.execute(stmt)
    buyer = result.scalar_one_or_none()
    if not buyer:
        return

    amount = float(order.amount)

    # 一级佣金（直接邀请人）
    if buyer.parent_id:
        level1_amount = round(amount * COMMISSION_LEVEL1_RATE, 2)
        if level1_amount > 0:
            await _create_commission_record(
                session, buyer.parent_id, buyer.id, order.id,
                amount, COMMISSION_LEVEL1_RATE * 100, level1_amount, 1,
            )

    # 二级佣金（邀请人的邀请人）
    if buyer.grand_parent_id:
        level2_amount = round(amount * COMMISSION_LEVEL2_RATE, 2)
        if level2_amount > 0:
            await _create_commission_record(
                session, buyer.grand_parent_id, buyer.id, order.id,
                amount, COMMISSION_LEVEL2_RATE * 100, level2_amount, 2,
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
):
    """创建佣金记录并更新用户余额"""
    # 创建佣金记录
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

    # 更新邀请人余额
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    inviter = result.scalar_one_or_none()
    if inviter:
        inviter.balance += commission_amount
        inviter.total_income += commission_amount
        inviter.updated_at = datetime.utcnow()
        await session.flush()

    logger.info(f"[Commission] L{level}佣金: user={user_id}, amount={commission_amount}")


def _parse_paid_at(paid_at_str: str) -> datetime:
    """解析微信回调的支付时间"""
    if not paid_at_str:
        return datetime.utcnow()
    try:
        # 微信格式: "2026-05-29T15:30:00+08:00"
        return datetime.fromisoformat(paid_at_str)
    except ValueError:
        return datetime.utcnow()
