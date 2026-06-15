"""Equity cash ledger writer.

Business services update User balances first, then call this service to persist
an immutable movement row with after-change snapshots.
"""

from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from models.equity_ledger import EquityLedger
from models.user import User


class EquityLedgerService:
    @staticmethod
    async def get_by_idempotency_key(session: AsyncSession, idempotency_key: str) -> EquityLedger | None:
        result = await session.execute(select(EquityLedger).where(EquityLedger.idempotency_key == idempotency_key))
        return result.scalar_one_or_none()

    @staticmethod
    async def record(
        session: AsyncSession,
        *,
        user_id: UUID,
        change_type: str,
        amount_delta: float = 0.0,
        frozen_delta: float = 0.0,
        total_income_delta: float = 0.0,
        total_withdrawn_delta: float = 0.0,
        related_type: str = "",
        related_id: str = "",
        idempotency_key: str,
        remark: str = "",
    ) -> tuple[EquityLedger, bool]:
        existing = await EquityLedgerService.get_by_idempotency_key(session, idempotency_key)
        if existing:
            return existing, False

        user = await session.get(User, user_id)
        if not user:
            raise ValueError("user not found")

        ledger = EquityLedger(
            user_id=user_id,
            change_type=change_type,
            amount_delta=round(float(amount_delta), 2),
            frozen_delta=round(float(frozen_delta), 2),
            total_income_delta=round(float(total_income_delta), 2),
            total_withdrawn_delta=round(float(total_withdrawn_delta), 2),
            balance_after=round(float(user.balance), 2),
            frozen_balance_after=round(float(user.frozen_balance), 2),
            total_income_after=round(float(user.total_income), 2),
            total_withdrawn_after=round(float(user.total_withdrawn), 2),
            related_type=related_type,
            related_id=related_id,
            idempotency_key=idempotency_key,
            remark=remark,
        )
        session.add(ledger)
        await session.flush()
        return ledger, True
