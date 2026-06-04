"""Points account initialization service for Stage 2."""

from datetime import datetime
from typing import Optional, Tuple
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from models.points_ledger import PointsLedger
from models.user_account import UserAccount


class PointsAccountService:
    """Stage 2 points account service."""

    @staticmethod
    async def get_user_account(session: AsyncSession, user_id: UUID) -> Optional[UserAccount]:
        stmt = select(UserAccount).where(UserAccount.user_id == user_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def ensure_user_account(
        session: AsyncSession,
        user_id: UUID,
    ) -> Tuple[UserAccount, bool]:
        account = await PointsAccountService.get_user_account(session, user_id)
        if account:
            return account, False

        account = UserAccount(user_id=user_id)
        session.add(account)
        await session.flush()
        return account, True

    @staticmethod
    async def get_ledger_by_idempotency_key(
        session: AsyncSession,
        idempotency_key: str,
    ) -> Optional[PointsLedger]:
        stmt = select(PointsLedger).where(PointsLedger.idempotency_key == idempotency_key)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def add_points(
        session: AsyncSession,
        user_id: UUID,
        points: int,
        source: str,
        change_type: str,
        availability: str,
        idempotency_key: str,
        related_type: str | None = None,
        related_id: str | None = None,
        remark: str | None = None,
    ) -> Tuple[PointsLedger, UserAccount, bool]:
        existing = await PointsAccountService.get_ledger_by_idempotency_key(session, idempotency_key)
        if existing:
            account = await PointsAccountService.get_user_account(session, user_id)
            if not account:
                account, _ = await PointsAccountService.ensure_user_account(session, user_id)
            return existing, account, False

        account, _ = await PointsAccountService.ensure_user_account(session, user_id)

        delta = int(points)
        account.total_points += delta
        if availability == "withdrawable":
            account.withdrawable_points += delta
        elif availability == "frozen":
            account.frozen_points += delta
        elif availability == "consumable":
            account.consumable_points += delta
        else:
            raise ValueError(f"unsupported availability: {availability}")
        account.updated_at = datetime.utcnow()

        ledger = PointsLedger(
            user_id=user_id,
            account_id=account.id,
            change_type=change_type,
            source=source,
            availability=availability,
            points_delta=delta,
            balance_withdrawable_after=int(account.withdrawable_points),
            balance_frozen_after=int(account.frozen_points),
            balance_consumable_after=int(account.consumable_points),
            related_type=related_type,
            related_id=related_id,
            idempotency_key=idempotency_key,
            remark=remark,
        )
        session.add(ledger)
        await session.flush()
        return ledger, account, True

    @staticmethod
    async def move_withdrawable_to_locked(
        session: AsyncSession,
        user_id: UUID,
        points: int,
        idempotency_key: str,
        related_type: str,
        related_id: str,
        remark: str | None = None,
    ) -> Tuple[PointsLedger, UserAccount, bool]:
        existing = await PointsAccountService.get_ledger_by_idempotency_key(session, idempotency_key)
        account, _ = await PointsAccountService.ensure_user_account(session, user_id)
        if existing:
            return existing, account, False

        delta = int(points)
        if delta <= 0:
            raise ValueError("points must be positive")
        if int(account.withdrawable_points) < delta:
            raise ValueError("insufficient withdrawable points")

        account.withdrawable_points -= delta
        account.locked_withdraw_points += delta
        account.updated_at = datetime.utcnow()

        ledger = PointsLedger(
            user_id=user_id,
            account_id=account.id,
            change_type="withdraw_lock",
            source="withdraw",
            availability="withdrawable",
            points_delta=-delta,
            balance_withdrawable_after=int(account.withdrawable_points),
            balance_frozen_after=int(account.frozen_points),
            balance_consumable_after=int(account.consumable_points),
            related_type=related_type,
            related_id=related_id,
            idempotency_key=idempotency_key,
            remark=remark,
        )
        session.add(ledger)
        await session.flush()
        return ledger, account, True

    @staticmethod
    async def settle_locked_withdrawal(
        session: AsyncSession,
        user_id: UUID,
        points: int,
        idempotency_key: str,
        related_type: str,
        related_id: str,
        remark: str | None = None,
    ) -> Tuple[PointsLedger, UserAccount, bool]:
        existing = await PointsAccountService.get_ledger_by_idempotency_key(session, idempotency_key)
        account, _ = await PointsAccountService.ensure_user_account(session, user_id)
        if existing:
            return existing, account, False

        delta = int(points)
        if delta <= 0:
            raise ValueError("points must be positive")
        if int(account.locked_withdraw_points) < delta:
            raise ValueError("insufficient locked withdraw points")

        account.locked_withdraw_points -= delta
        account.withdrawn_points += delta
        account.updated_at = datetime.utcnow()

        ledger = PointsLedger(
            user_id=user_id,
            account_id=account.id,
            change_type="withdraw_success",
            source="withdraw",
            availability="withdrawable",
            points_delta=-delta,
            balance_withdrawable_after=int(account.withdrawable_points),
            balance_frozen_after=int(account.frozen_points),
            balance_consumable_after=int(account.consumable_points),
            related_type=related_type,
            related_id=related_id,
            idempotency_key=idempotency_key,
            remark=remark,
        )
        session.add(ledger)
        await session.flush()
        return ledger, account, True

    @staticmethod
    async def return_locked_withdrawal(
        session: AsyncSession,
        user_id: UUID,
        points: int,
        idempotency_key: str,
        related_type: str,
        related_id: str,
        remark: str | None = None,
    ) -> Tuple[PointsLedger, UserAccount, bool]:
        existing = await PointsAccountService.get_ledger_by_idempotency_key(session, idempotency_key)
        account, _ = await PointsAccountService.ensure_user_account(session, user_id)
        if existing:
            return existing, account, False

        delta = int(points)
        if delta <= 0:
            raise ValueError("points must be positive")
        if int(account.locked_withdraw_points) < delta:
            raise ValueError("insufficient locked withdraw points")

        account.locked_withdraw_points -= delta
        account.withdrawable_points += delta
        account.updated_at = datetime.utcnow()

        ledger = PointsLedger(
            user_id=user_id,
            account_id=account.id,
            change_type="withdraw_reject_return",
            source="withdraw",
            availability="withdrawable",
            points_delta=delta,
            balance_withdrawable_after=int(account.withdrawable_points),
            balance_frozen_after=int(account.frozen_points),
            balance_consumable_after=int(account.consumable_points),
            related_type=related_type,
            related_id=related_id,
            idempotency_key=idempotency_key,
            remark=remark,
        )
        session.add(ledger)
        await session.flush()
        return ledger, account, True
