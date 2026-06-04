"""Stage 2 home overview routes."""

from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.response import response
from jwt_create import get_current_user
from models.base import get_session
from models.user import User
from schemas.home import HomeOverviewResponse
from services.home_overview_service import HomeOverviewService

router = APIRouter(prefix="/home", tags=["home"])


@router.get("/overview", summary="get home overview")
async def get_home_overview(
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).where(User.openid == openid))
    user = result.scalar_one_or_none()
    if not user:
        return response([], 404, "user not found")

    payload = await HomeOverviewService.get_overview(session, user)
    return response(data=HomeOverviewResponse(**payload).model_dump(mode="json"))
