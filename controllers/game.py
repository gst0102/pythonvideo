"""Stage 2 game task routes."""

from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.response import response
from jwt_create import get_current_user
from models.base import get_session
from models.user import User
from schemas.game import (
    GameAdSlotResponse,
    GameRoundAdBonusRequest,
    GameRoundAdBonusResponse,
    GameRoundCompleteRequest,
    GameRoundCompleteResponse,
    GameTaskStatusResponse,
)
from services.game_task_service import GameTaskService
from services.game_ad_service import GameAdService

router = APIRouter(prefix="/game", tags=["game"])


@router.get("/tasks/status", summary="get game task status")
async def get_game_task_status(
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).where(User.openid == openid))
    user = result.scalar_one_or_none()
    if not user:
        return response([], 404, "user not found")

    payload = await GameTaskService.get_status(session, user)
    return response(data=GameTaskStatusResponse(**payload).model_dump(mode="json"))


@router.get("/ads/available", summary="get available rewarded ad slot for game bonus")
async def get_available_game_ad_slot(
    round_id: str,
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).where(User.openid == openid))
    user = result.scalar_one_or_none()
    if not user:
        return response([], 404, "user not found")

    try:
        payload = await GameAdService.select_available_slot(session, user, round_id=round_id)
    except ValueError as exc:
        return response([], 400, str(exc))

    return response(data=GameAdSlotResponse(**payload).model_dump(mode="json"))


@router.post("/rounds", summary="complete game round")
async def complete_game_round(
    req: GameRoundCompleteRequest,
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).where(User.openid == openid))
    user = result.scalar_one_or_none()
    if not user:
        return response([], 404, "user not found")

    try:
        payload, created = await GameTaskService.complete_round(
            session,
            user,
            game_code=req.game_code,
            round_id=req.round_id,
            result=req.result,
            user_choice=req.user_choice,
            ad_event_id=req.ad_event_id,
        )
    except ValueError as exc:
        return response([], 400, str(exc))
    except RuntimeError as exc:
        return response([], 400, str(exc))

    if not created:
        return response(
            data=GameRoundCompleteResponse(**payload).model_dump(mode="json"),
            code=400,
            msg="game reward already granted",
        )

    return response(
        data=GameRoundCompleteResponse(**payload).model_dump(mode="json"),
        msg="game reward success",
    )


@router.post("/rounds/ad-bonus", summary="claim game round ad bonus")
async def claim_game_round_ad_bonus(
    req: GameRoundAdBonusRequest,
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).where(User.openid == openid))
    user = result.scalar_one_or_none()
    if not user:
        return response([], 404, "user not found")

    try:
        payload, rewarded = await GameTaskService.claim_round_ad_bonus(
            session,
            user,
            round_id=req.round_id,
            ad_event_id=req.ad_event_id,
        )
    except ValueError as exc:
        return response([], 400, str(exc))
    except RuntimeError as exc:
        return response([], 400, str(exc))

    return response(
        data=GameRoundAdBonusResponse(**payload).model_dump(mode="json"),
        msg="game ad bonus success" if rewarded else "game ad bonus already granted",
    )
