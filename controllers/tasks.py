"""Stage 2 task overview routes."""

from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.response import response
from jwt_create import get_current_user
from models.base import get_session
from models.user import User
from schemas.tasks import TaskOverviewResponse
from services.task_overview_service import TaskOverviewService

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/overview", summary="get task overview")
async def get_task_overview(
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).where(User.openid == openid))
    user = result.scalar_one_or_none()
    if not user:
        return response([], 404, "user not found")

    payload = await TaskOverviewService.get_overview(session, user)
    return response(data=TaskOverviewResponse(**payload).model_dump(mode="json"))
