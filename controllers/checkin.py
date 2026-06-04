"""Stage 2 daily check-in routes."""

from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.response import response
from jwt_create import get_current_user
from models.base import get_session
from models.user import User
from schemas.checkin import CheckinExecuteResponse, CheckinStatusResponse
from services.checkin_service import CheckinService

router = APIRouter(prefix="/checkin", tags=["checkin"])


@router.get("/status", summary="get daily checkin status")
async def get_checkin_status(
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).where(User.openid == openid))
    user = result.scalar_one_or_none()
    if not user:
        return response([], 404, "user not found")

    status = await CheckinService.get_status(session, user)
    return response(data=CheckinStatusResponse(**status).model_dump(mode="json"))


@router.post("", summary="execute daily checkin")
async def execute_checkin(
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).where(User.openid == openid))
    user = result.scalar_one_or_none()
    if not user:
        return response([], 404, "user not found")

    payload, created = await CheckinService.execute_checkin(session, user)
    if not created:
        return response(
            data=CheckinExecuteResponse(**payload).model_dump(mode="json"),
            code=400,
            msg="already checked in today",
        )

    return response(
        data=CheckinExecuteResponse(**payload).model_dump(mode="json"),
        msg="checkin success",
    )
