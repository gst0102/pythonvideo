"""Stage 2 points routes."""

from fastapi import APIRouter, Depends, Query
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.response import response
from jwt_create import get_current_user
from models.base import get_session
from models.user import User
from schemas.points import PointsLedgerResponse
from services.points_ledger_service import PointsLedgerService

router = APIRouter(prefix="/points", tags=["points"])


@router.get("/ledger", summary="list points ledger")
async def list_points_ledger(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    source: str | None = Query(default=None, max_length=64),
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).where(User.openid == openid))
    user = result.scalar_one_or_none()
    if not user:
        return response([], 404, "user not found")

    payload = await PointsLedgerService.list_user_ledger(
        session=session,
        user=user,
        page=page,
        page_size=page_size,
        source=source,
    )
    return response(data=PointsLedgerResponse(**payload).model_dump(mode="json"))
