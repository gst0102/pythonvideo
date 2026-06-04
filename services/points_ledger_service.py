"""Stage 2 points ledger query service."""

from __future__ import annotations

from typing import Any, Dict

from sqlalchemy import desc, func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from models.points_ledger import PointsLedger
from models.user import User
from services.points_account_service import PointsAccountService


class PointsLedgerService:
    """Read-only queries for user points ledger."""

    @staticmethod
    async def list_user_ledger(
        session: AsyncSession,
        user: User,
        page: int = 1,
        page_size: int = 20,
        source: str | None = None,
    ) -> Dict[str, Any]:
        safe_page = max(int(page or 1), 1)
        safe_page_size = min(max(int(page_size or 20), 1), 100)
        offset = (safe_page - 1) * safe_page_size

        account, _ = await PointsAccountService.ensure_user_account(session, user.id)

        filters = [PointsLedger.user_id == user.id]
        if source:
            filters.append(PointsLedger.source == source)

        count_stmt = select(func.count()).select_from(PointsLedger).where(*filters)
        total_result = await session.execute(count_stmt)
        total = int(total_result.scalar_one() or 0)

        stmt = (
            select(PointsLedger)
            .where(*filters)
            .order_by(desc(PointsLedger.created_at), desc(PointsLedger.id))
            .offset(offset)
            .limit(safe_page_size)
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()

        return {
            "page": safe_page,
            "page_size": safe_page_size,
            "total": total,
            "has_more": offset + len(rows) < total,
            "account": {
                "total_points": int(account.total_points),
                "withdrawable_points": int(account.withdrawable_points),
                "frozen_points": int(account.frozen_points),
                "consumable_points": int(account.consumable_points),
            },
            "items": [
                {
                    "id": str(row.id),
                    "change_type": row.change_type,
                    "source": row.source,
                    "availability": row.availability,
                    "points_delta": int(row.points_delta),
                    "balance_withdrawable_after": int(row.balance_withdrawable_after),
                    "balance_frozen_after": int(row.balance_frozen_after),
                    "balance_consumable_after": int(row.balance_consumable_after),
                    "related_type": row.related_type,
                    "related_id": row.related_id,
                    "remark": row.remark,
                    "created_at": row.created_at,
                }
                for row in rows
            ],
        }
