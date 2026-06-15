"""Payment business logic."""

import logging
import math
import os
from datetime import datetime, timedelta
from uuid import UUID

import httpx
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.databaseApi import get_access_token
from models.commission import CommissionRecord
from models.netdisk_user_notification import NetdiskUserNotification
from models.order import Order
from models.points_ledger import PointsLedger
from models.user import User
from services.config_service import ConfigService
from services.equity_ledger_service import EquityLedgerService
from services.invite_reward_service import InviteRewardService
from services.points_account_service import PointsAccountService

logger = logging.getLogger(__name__)

COMMISSION_LEVEL1_RATE = 0.50
COMMISSION_LEVEL2_RATE = 0.05
PERIOD_DAYS = {"month": 30, "quarter": 90, "year": 365}
BENEFIT_CARD_POINTS = {"card_month_10": 300, "card_month_20": 900}


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
        if order.status == "refunded":
            logger.warning("[Payment] success callback ignored for refunded order: %s", out_trade_no)
            return True

        amount_yuan = total_fee_in_fen / 100.0
        order.status = "paid"
        order.transaction_id = transaction_id
        order.amount = amount_yuan
        order.paid_at = _parse_paid_at(paid_at)
        order.updated_at = datetime.utcnow()
        await session.flush()

        if _is_points_recharge_order(order):
            await _grant_recharge_points(session, order)
            await InviteRewardService.grant_first_recharge_reward(
                session,
                invitee_id=order.user_id,
                order_id=str(order.id),
            )
            await _calculate_commission(session, order, grant_equity_cash=True)
        elif _is_benefit_card_order(order):
            await _activate_vip(session, order.user_id, order.period, order.duration_days or 30)
            await _grant_benefit_card_points(session, order)
            await _calculate_commission(session, order, grant_equity_cash=True)
        else:
            await _activate_vip(session, order.user_id, order.period, order.duration_days)
            await _grant_vip_gift_points(session, order)
            await _calculate_commission(session, order)

        return True

    @staticmethod
    async def handle_payment_refund(
        session: AsyncSession,
        out_trade_no: str,
        refund_id: str = "",
        refunded_at: str = "",
    ) -> bool:
        result = await session.execute(select(Order).where(Order.out_trade_no == out_trade_no))
        order = result.scalar_one_or_none()
        if not order:
            logger.error("[Payment] refund order not found: %s", out_trade_no)
            return False
        if order.status == "refunded":
            return True
        if order.status != "paid":
            logger.warning("[Payment] refund skipped for non-paid order: %s status=%s", out_trade_no, order.status)
            return False

        if _is_points_recharge_order(order):
            await _revoke_recharge_points(session, order, refund_id)
            await _revoke_first_recharge_reward(session, order, refund_id)
            await _cancel_commission_points(session, order, refund_id)
        elif _is_benefit_card_order(order):
            await _revoke_benefit_card_points(session, order, refund_id)
            await _cancel_commission_points(session, order, refund_id)
            await _revoke_vip_duration(session, order)
        else:
            await _revoke_vip_gift_points(session, order, refund_id)
            await _cancel_commission_points(session, order, refund_id)
            await _revoke_vip_duration(session, order)

        order.status = "refunded"
        order.updated_at = _parse_paid_at(refunded_at) if refunded_at else datetime.utcnow()
        await session.flush()
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


async def _calculate_commission(
    session: AsyncSession,
    order: Order,
    *,
    grant_equity_cash: bool = False,
) -> None:
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
            grant_equity_cash=grant_equity_cash,
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
            grant_equity_cash=False,
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
        availability="consumable",
        idempotency_key=f"vip_gift:{order.id}",
        related_type="order",
        related_id=str(order.id),
        remark=f"vip gift points: {order.period}",
    )


async def _grant_recharge_points(session: AsyncSession, order: Order) -> None:
    recharge_points = _points_from_recharge_period(order.period)
    if recharge_points <= 0:
        return

    await PointsAccountService.add_points(
        session=session,
        user_id=order.user_id,
        points=recharge_points,
        source="recharge",
        change_type="points_recharge",
        availability="consumable",
        idempotency_key=f"points_recharge:{order.id}",
        related_type="order",
        related_id=str(order.id),
        remark=f"充值积分到账：{recharge_points}分",
    )


async def _grant_benefit_card_points(session: AsyncSession, order: Order) -> None:
    card_points = _points_from_benefit_card_period(order.period)
    if card_points <= 0:
        return

    await PointsAccountService.add_points(
        session=session,
        user_id=order.user_id,
        points=card_points,
        source="vip",
        change_type="benefit_card_points",
        availability="consumable",
        idempotency_key=f"benefit_card_points:{order.id}",
        related_type="order",
        related_id=str(order.id),
        remark=f"月卡积分到账：{card_points}分",
    )


async def _revoke_recharge_points(session: AsyncSession, order: Order, refund_id: str = "") -> None:
    ledger = await PointsAccountService.get_ledger_by_idempotency_key(session, f"points_recharge:{order.id}")
    if not ledger or int(ledger.points_delta) <= 0:
        return

    await PointsAccountService.clawback_points(
        session=session,
        user_id=order.user_id,
        points=int(ledger.points_delta),
        availability="consumable",
        idempotency_key=f"refund:points_recharge:{order.id}",
        related_type="order",
        related_id=str(order.id),
        source="refund",
        change_type="points_recharge_refund",
        remark=f"refund points recharge; refund_id={refund_id or order.out_trade_no}",
    )


async def _revoke_benefit_card_points(session: AsyncSession, order: Order, refund_id: str = "") -> None:
    ledger = await PointsAccountService.get_ledger_by_idempotency_key(session, f"benefit_card_points:{order.id}")
    if not ledger or int(ledger.points_delta) <= 0:
        return

    await PointsAccountService.clawback_points(
        session=session,
        user_id=order.user_id,
        points=int(ledger.points_delta),
        availability="consumable",
        idempotency_key=f"refund:benefit_card_points:{order.id}",
        related_type="order",
        related_id=str(order.id),
        source="refund",
        change_type="benefit_card_points_refund",
        remark=f"refund benefit card points; refund_id={refund_id or order.out_trade_no}",
    )


async def _revoke_vip_gift_points(session: AsyncSession, order: Order, refund_id: str = "") -> None:
    ledger = await PointsAccountService.get_ledger_by_idempotency_key(session, f"vip_gift:{order.id}")
    if not ledger or int(ledger.points_delta) <= 0:
        return

    await PointsAccountService.clawback_points(
        session=session,
        user_id=order.user_id,
        points=int(ledger.points_delta),
        availability="consumable",
        idempotency_key=f"refund:vip_gift:{order.id}",
        related_type="order",
        related_id=str(order.id),
        source="refund",
        change_type="vip_gift_refund",
        remark=f"refund vip gift points; refund_id={refund_id or order.out_trade_no}",
    )


async def _revoke_first_recharge_reward(session: AsyncSession, order: Order, refund_id: str = "") -> None:
    result = await session.execute(
        select(PointsLedger).where(
            PointsLedger.source == "invite",
            PointsLedger.change_type == "invite_first_recharge",
            PointsLedger.related_type == "invite_relation",
            PointsLedger.remark.contains(str(order.id)),
        )
    )
    ledger = result.scalar_one_or_none()
    if not ledger or int(ledger.points_delta) <= 0:
        return

    await PointsAccountService.clawback_points(
        session=session,
        user_id=ledger.user_id,
        points=int(ledger.points_delta),
        availability="consumable",
        idempotency_key=f"refund:invite_first_recharge:{order.id}:{ledger.user_id}",
        related_type="order",
        related_id=str(order.id),
        source="refund",
        change_type="invite_first_recharge_refund",
        remark=f"refund invite first recharge reward; refund_id={refund_id or order.out_trade_no}",
    )


async def _cancel_commission_points(session: AsyncSession, order: Order, refund_id: str = "") -> None:
    records_result = await session.execute(select(CommissionRecord).where(CommissionRecord.order_id == order.id))
    records = list(records_result.scalars().all())
    should_revoke_equity_cash = _is_points_recharge_order(order) or _is_benefit_card_order(order)
    for record in records:
        if record.status == "cancelled":
            continue

        if should_revoke_equity_cash and int(record.level) == 1:
            await _revoke_equity_cash_reward(session, record, order, refund_id)

        ledger_result = await session.execute(
            select(PointsLedger).where(
                PointsLedger.source == "invite",
                PointsLedger.change_type == "invite_rebate_frozen",
                PointsLedger.related_type == "commission_record",
                PointsLedger.related_id == str(record.id),
            )
        )
        ledger = ledger_result.scalar_one_or_none()
        if ledger and int(ledger.points_delta) > 0:
            availability = "consumable" if record.status == "settled" else "frozen"
            change_type = "invite_rebate_refund_settled" if record.status == "settled" else "invite_rebate_refund_frozen"
            await PointsAccountService.clawback_points(
                session=session,
                user_id=record.user_id,
                points=int(ledger.points_delta),
                availability=availability,
                idempotency_key=f"refund:invite_rebate:{order.id}:{record.id}",
                related_type="commission_record",
                related_id=str(record.id),
                source="refund",
                change_type=change_type,
                remark=f"refund invite rebate; refund_id={refund_id or order.out_trade_no}",
            )

        record.status = "cancelled"
    await session.flush()


async def _revoke_equity_cash_reward(
    session: AsyncSession,
    record: CommissionRecord,
    order: Order,
    refund_id: str = "",
) -> None:
    user = await session.get(User, record.user_id)
    if not user:
        return
    amount = round(float(record.commission_amount or 0), 2)
    if amount <= 0:
        return

    user.balance = round(float(user.balance) - amount, 2)
    user.total_income = round(float(user.total_income) - amount, 2)
    user.updated_at = datetime.utcnow()
    await EquityLedgerService.record(
        session,
        user_id=record.user_id,
        change_type="refund_revoke",
        amount_delta=-amount,
        total_income_delta=-amount,
        related_type="commission_record",
        related_id=str(record.id),
        idempotency_key=f"equity:refund_revoke:{record.id}",
        remark=f"paid order refund; order_id={order.id}; refund_id={refund_id or order.out_trade_no}",
    )
    session.add(
        NetdiskUserNotification(
            user_id=record.user_id,
            notice_type="invite_equity_refund",
            title="权益金已回收",
            content=f"好友订单发生退款，已回收 {amount:.2f} 元权益金。退款单号：{refund_id or order.out_trade_no}",
            related_type="commission_record",
            related_id=str(record.id),
            status="unread",
        )
    )


async def _revoke_vip_duration(session: AsyncSession, order: Order) -> None:
    result = await session.execute(select(User).where(User.id == order.user_id))
    user = result.scalar_one_or_none()
    if not user or not user.vip_expire_at:
        return

    days = order.duration_days or PERIOD_DAYS.get(order.period, 30)
    user.vip_expire_at = user.vip_expire_at - timedelta(days=days)
    if user.vip_expire_at <= datetime.utcnow():
        user.is_vip = False
        user.vip_expire_at = None
    user.updated_at = datetime.utcnow()
    await session.flush()


def _is_points_recharge_order(order: Order) -> bool:
    return str(order.period or "").startswith("points_")


def _is_benefit_card_order(order: Order) -> bool:
    return str(order.period or "") in BENEFIT_CARD_POINTS


def _points_from_recharge_period(period: str) -> int:
    value = str(period or "").strip().lower()
    if not value.startswith("points_"):
        return 0
    try:
        return max(int(value.replace("points_", "", 1)), 0)
    except ValueError:
        return 0


def _points_from_benefit_card_period(period: str) -> int:
    return int(BENEFIT_CARD_POINTS.get(str(period or ""), 0))


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
    grant_equity_cash: bool = False,
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
    if grant_equity_cash and level == 1 and commission_amount > 0:
        await _grant_equity_cash_reward(
            session,
            user_id=user_id,
            from_user_id=from_user_id,
            order_id=order_id,
            amount=commission_amount,
            record_id=record.id,
        )


async def _grant_equity_cash_reward(
    session: AsyncSession,
    user_id: UUID,
    from_user_id: UUID,
    order_id: UUID,
    amount: float,
    record_id: UUID,
) -> None:
    user = await session.get(User, user_id)
    if not user:
        return
    amount = round(float(amount), 2)
    if amount <= 0:
        return

    user.balance = round(float(user.balance) + amount, 2)
    user.total_income = round(float(user.total_income) + amount, 2)
    user.updated_at = datetime.utcnow()
    await EquityLedgerService.record(
        session,
        user_id=user_id,
        change_type="invite_reward",
        amount_delta=amount,
        total_income_delta=amount,
        related_type="commission_record",
        related_id=str(record_id),
        idempotency_key=f"equity:invite_reward:{record_id}",
        remark=f"invite paid order reward; order_id={order_id}; from_user_id={from_user_id}",
    )
    session.add(
        NetdiskUserNotification(
            user_id=user_id,
            notice_type="invite_equity_reward",
            title="权益金到账",
            content=f"好友完成付费订单，你获得 {amount:.2f} 元权益金，可申请提现，预计24小时内到账。",
            related_type="commission_record",
            related_id=str(record_id),
            status="unread",
        )
    )
    await _send_invite_reward_subscribe_message(user, amount)
    logger.info(
        "[Payment] invite equity reward granted user=%s from=%s order=%s amount=%.2f",
        user_id,
        from_user_id,
        order_id,
        amount,
    )


async def _send_invite_reward_subscribe_message(user: User, amount: float) -> None:
    template_id = os.getenv("WX_INVITE_REWARD_TEMPLATE_ID", "").strip()
    if not template_id or not user.openid:
        logger.info("[Payment] invite reward subscribe message skipped: template_missing")
        return
    try:
        token_result = await get_access_token(redis_client=None)
        access_token = token_result.get("token")
        if not access_token:
            logger.warning("[Payment] invite reward subscribe message skipped: access_token missing")
            return

        title_field = os.getenv("WX_INVITE_REWARD_TITLE_FIELD", "thing1")
        amount_field = os.getenv("WX_INVITE_REWARD_AMOUNT_FIELD", "amount2")
        status_field = os.getenv("WX_INVITE_REWARD_STATUS_FIELD", "thing3")
        time_field = os.getenv("WX_INVITE_REWARD_TIME_FIELD", "time4")
        payload = {
            "touser": user.openid,
            "template_id": template_id,
            "page": "pages/netdisk/invite",
            "miniprogram_state": os.getenv("WX_SUBSCRIBE_MINIPROGRAM_STATE", "formal"),
            "lang": "zh_CN",
            "data": {
                title_field: {"value": "邀请权益金到账"[:20]},
                amount_field: {"value": f"{amount:.2f}元"},
                status_field: {"value": "可提现"[:20]},
                time_field: {"value": (datetime.utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")},
            },
        }
        async with httpx.AsyncClient(timeout=10) as client:
            result = await client.post(
                f"https://api.weixin.qq.com/cgi-bin/message/subscribe/send?access_token={access_token}",
                json=payload,
            )
            data = result.json()
        if int(data.get("errcode") or 0) != 0:
            logger.warning("[Payment] invite reward subscribe message failed: %s", data)
    except Exception as exc:
        logger.warning("[Payment] invite reward subscribe message error: %s", exc)


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
