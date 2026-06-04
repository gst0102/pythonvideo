"""Stage 2 mine assets routes."""

from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.response import response
from jwt_create import get_current_user
from models.base import get_session
from models.user import User
from schemas.mine import MineAssetsResponse
from services.mine_assets_service import MineAssetsService

router = APIRouter(prefix="/mine", tags=["mine"])


@router.get("/assets", summary="get mine assets")
async def get_mine_assets(
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).where(User.openid == openid))
    user = result.scalar_one_or_none()
    if not user:
        return response([], 404, "user not found")

    payload = await MineAssetsService.get_assets(session, user)
    return response(data=MineAssetsResponse(**payload).model_dump(mode="json"))
