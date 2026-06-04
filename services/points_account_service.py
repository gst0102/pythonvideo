"""Points account initialization service for Stage 2."""

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
