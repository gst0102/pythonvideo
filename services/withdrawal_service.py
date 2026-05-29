"""
提现服务 — withdrawal_service

MVC 架构中的 Service 层，处理提现申请和转账回调。

核心功能:
  1. 提现申请（余额校验、冻结、调用微信商家转账API）
  2. 转账成功回调（解冻、更新余额）
  3. 转账失败回调（回滚、退回余额）
  4. 提现记录查询
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
from sqlmodel import select, func, and_
from sqlmodel.ext.asyncio.session import AsyncSession

from core.wepay import WeChatPayV3
from models.user import User
from models.withdrawal import WithdrawalRecord

load_dotenv()
logger = logging.getLogger(__name__)


def _get_wx_pay() -> WeChatPayV3:
    """获取微信支付实例"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return WeChatPayV3(
        mch_id=os.getenv("mchid", ""),
        app_id=os.getenv("APPID", ""),
        api_v3_key=os.getenv("APIv3", ""),
        private_key_path=os.path.join(base_dir, "certs", "apiclient_key.pem"),
        serial_no=os.getenv("serial_no", ""),
        notify_url=os.getenv("NOTIFY_URL", ""),
    )


class WithdrawalService:
    """提现业务逻辑服务"""

    @staticmethod
    async def apply_withdrawal(
        session: AsyncSession,
        user_id: UUID,
        amount: float,
        ip: Optional[str] = None,
        openid: Optional[str] = None,
    ) -> Tuple[Optional[WithdrawalRecord], Optional[str]]:
        """
        申请提现（含微信商家转账调用）。
        参照云函数 merchantTransfer 逻辑：冻结 → 调API → 成功则解冻，失败则显式回滚。

        Returns:
            (WithdrawalRecord, error_msg)
        """
        amount = round(amount, 2)

        # 1. 验证金额
        if amount < 0.10:
            return None, "最低提现 0.10 元"
        if amount > 200.00:
            return None, "单次最多提现 200.00 元"

        # 2. 查询用户
        user = await session.get(User, user_id)
        if not user:
            return None, "用户不存在"

        # 3. 检查是否有可复用的待处理提现（云函数模式：支持重试）
        pending_stmt = (
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
        pending_result = await session.execute(pending_stmt)
        pending = pending_result.scalar_one_or_none()

        is_retry = False
        if pending:
            # 金额一致 → 复用上次的 batch_no，直接重试 API
            if abs(float(pending.amount) - amount) < 0.001:
                batch_no = pending.batch_no
                is_retry = True
                record = pending
                logger.info(f"[Withdrawal] 复用待确认记录: {batch_no} ({amount}元)")
            else:
                # 金额不一致 → 取消旧记录，解冻余额
                logger.info(f"[Withdrawal] 金额不一致，回滚旧记录: {pending.batch_no} (旧:{pending.amount}, 新:{amount})")
                user.balance += float(pending.amount)
                user.frozen_balance = float(user.frozen_balance) - float(pending.amount)
                pending.status = "failed"
                pending.fail_reason = "用户发起新提现（金额不一致）"
                pending.updated_at = datetime.utcnow()
                await session.flush()

        if not is_retry:
            # 4. 检查余额（云函数方式：new_Inc - frozen_amount）
            available = round(float(user.balance) - float(user.frozen_balance), 2)
            if available < amount:
                return None, f"余额不足，可提现: {available:.2f} 元"

            # 5. 冻结余额
            user.balance -= amount
            user.frozen_balance = round(float(user.frozen_balance) + amount, 2)
            user.updated_at = datetime.utcnow()

            # 6. 创建提现记录
            batch_no = _generate_batch_no()
            record = WithdrawalRecord(
                user_id=user_id,
                amount=amount,
                status="processing",
                batch_no=batch_no,
                ip=ip,
            )
            session.add(record)
            await session.flush()
            logger.info(f"[Withdrawal] 新订单已创建: {batch_no}, amount={amount}")

        # 7. 调用微信商家转账 API
        target_openid = openid or user.openid
        if not target_openid:
            # 显式回滚余额（不依赖事务）
            if not is_retry:
                user.balance += amount
                user.frozen_balance = round(float(user.frozen_balance) - amount, 2)
                record.status = "failed"
                record.fail_reason = "用户未绑定微信"
            return None, "用户未绑定微信，无法提现"

        try:
            wx_pay = _get_wx_pay()
            transfer_result = wx_pay.merchant_transfer(
                out_bill_no=batch_no,
                openid=target_openid,
                amount=amount,
                transfer_remark="收益提现",
            )
            state = transfer_result.get("state", "")
            logger.info(f"[Withdrawal] 微信转账返回: state={state}")

            # ⭐ 云函数逻辑：WAIT_USER_CONFIRM / ACCEPTED / SUCCESS → 直接解冻完成
            if state in ("WAIT_USER_CONFIRM", "ACCEPTED", "SUCCESS"):
                if transfer_result.get("transfer_bill_no"):
                    record.transfer_bill_no = transfer_result["transfer_bill_no"]

                # 解冻余额、累计提现
                user.frozen_balance = round(float(user.frozen_balance) - amount, 2)
                user.total_withdrawn = round(float(user.total_withdrawn) + amount, 2)
                record.status = "success"
                record.completed_at = datetime.utcnow()
                record.updated_at = datetime.utcnow()
                await session.flush()
                logger.info(f"[Withdrawal] 转账成功: {batch_no}, amount={amount}")

                return record, None

            # API 返回非预期状态 → 显式回滚（云函数模式：rollbackBalance）
            logger.error(f"[Withdrawal] 转账API返回非预期状态: {state}")
            if not is_retry:
                await _rollback_balance(session, user, record, amount, f"微信API返回异常状态: {state}")
            return None, f"转账预下单失败: {state}"

        except Exception as e:
            logger.error(f"[Withdrawal] 微信转账调用异常: {e}")
            # 显式回滚（云函数模式：API调用失败自动回滚）
            if not is_retry:
                await _rollback_balance(session, user, record, amount, f"API调用失败: {str(e)[:100]}")
            return None, f"提现失败: {str(e)}"

    @staticmethod
    async def handle_transfer_success(
        session: AsyncSession,
        batch_no: str,
        transfer_bill_no: str,
    ) -> bool:
        """处理转账成功回调"""
        stmt = select(WithdrawalRecord).where(WithdrawalRecord.batch_no == batch_no)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            logger.warning(f"[Transfer] 提现记录不存在: {batch_no}")
            return False

        if record.status != "processing":
            return True  # 幂等

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

        logger.info(f"[Transfer] 转账成功: {batch_no}, amount={record.amount}")
        return True

    @staticmethod
    async def handle_transfer_failed(
        session: AsyncSession,
        batch_no: str,
        reason: str = "转账失败",
    ) -> bool:
        """处理转账失败回调：退回冻结金额到余额"""
        stmt = select(WithdrawalRecord).where(WithdrawalRecord.batch_no == batch_no)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            return False

        if record.status != "processing":
            return True  # 幂等

        record.status = "failed"
        record.fail_reason = reason
        record.completed_at = datetime.utcnow()
        record.updated_at = datetime.utcnow()

        user = await session.get(User, record.user_id)
        if user:
            amount = float(record.amount)
            # 退回余额：balance +amount, frozen_balance -amount
            user.balance = round(float(user.balance) + amount, 2)
            user.frozen_balance = round(float(user.frozen_balance) - amount, 2)
            user.updated_at = datetime.utcnow()

        logger.info(f"[Transfer] 转账失败已退回: {batch_no}, amount={record.amount}, reason={reason}")
        return True

    @staticmethod
    async def release_frozen_amount(
        session: AsyncSession,
        user_id: UUID,
    ) -> Tuple[float, List[str], Optional[str]]:
        """
        清理用户被锁定的冻结金额（云函数 releaseFrozenAmount 的 Python 版本）。
        用于修复"上一次提现错误，钱没有回调退回"导致冻结金额卡住的问题。

        Returns:
            (released_amount, cleared_batch_nos, error_msg)
        """
        user = await session.get(User, user_id)
        if not user:
            return 0, [], "用户不存在"

        frozen = round(float(user.frozen_balance), 2)
        if frozen <= 0:
            return 0, [], None  # 没有冻结金额

        # 查找所有 processing 状态的提现记录
        stmt = (
            select(WithdrawalRecord)
            .where(
                and_(
                    WithdrawalRecord.user_id == user_id,
                    WithdrawalRecord.status == "processing",
                )
            )
        )
        result = await session.execute(stmt)
        pending_records = result.scalars().all()

        if pending_records:
            # 有处理中的记录 → 先检查是否超过24小时（云函数逻辑）
            cleared = []
            total_cleared = 0.0
            for rec in pending_records:
                rec_amount = float(rec.amount)
                hours_since = 0
                if rec.created_at:
                    hours_since = (datetime.utcnow() - rec.created_at.replace(tzinfo=None)).total_seconds() / 3600

                # 超过24小时的 processing 记录 → 标记失败并回滚
                if hours_since > 24:
                    user.balance = round(float(user.balance) + rec_amount, 2)
                    user.frozen_balance = round(float(user.frozen_balance) - rec_amount, 2)
                    rec.status = "failed"
                    rec.fail_reason = "超过24小时未确认，自动退回"
                    rec.completed_at = datetime.utcnow()
                    rec.updated_at = datetime.utcnow()
                    cleared.append(rec.batch_no)
                    total_cleared += rec_amount
                    logger.info(f"[ReleaseFrozen] 自动退回超时记录: {rec.batch_no} ({rec_amount}元, {hours_since:.1f}h)")

            if cleared:
                user.updated_at = datetime.utcnow()
                await session.flush()
                return round(total_cleared, 2), cleared, None
            else:
                # 有 processing 记录但都不足 24 小时 → 不允许强制释放
                return 0, [], f"存在 {len(pending_records)} 条处理中的提现（不足24小时），无法强制释放"

        # 没有 processing 记录但 frozen_balance > 0 → 直接释放（数据不一致修复）
        logger.warning(f"[ReleaseFrozen] 无处理中记录但冻结金额={frozen}，执行修复释放")
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
        """获取用户的提现记录（分页）"""
        count_stmt = (
            select(func.count())
            .select_from(WithdrawalRecord)
            .where(WithdrawalRecord.user_id == user_id)
        )
        result = await session.execute(count_stmt)
        total = result.scalar() or 0

        list_stmt = (
            select(WithdrawalRecord)
            .where(WithdrawalRecord.user_id == user_id)
            .order_by(WithdrawalRecord.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await session.execute(list_stmt)
        records = result.scalars().all()

        return list(records), total


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
    """
    显式回滚冻结金额（云函数 rollbackBalance 的 Python 版本）。
    不依赖 DB 事务回滚，直接修改字段值。
    """
    amount = round(amount, 2)
    logger.info(f"[Rollback] 开始回滚: user={user.id}, amount={amount}, batch={record.batch_no}, reason={reason}")

    user.balance = round(float(user.balance) + amount, 2)
    user.frozen_balance = round(float(user.frozen_balance) - amount, 2)
    user.updated_at = datetime.utcnow()

    record.status = "failed"
    record.fail_reason = reason
    record.completed_at = datetime.utcnow()
    record.updated_at = datetime.utcnow()

    await session.flush()
    logger.info(f"[Rollback] 回滚完成: {record.batch_no}")
