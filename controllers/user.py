"""
User controller routes.
"""

import logging
import os
from decimal import Decimal, ROUND_HALF_UP
from typing import cast
from uuid import uuid4

from fastapi import APIRouter, Depends, UploadFile
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.response import response
from jwt_create import create_access_token, get_current_user
from models.ad_event import AdEventRecord
from models.ad_reward import AdRewardRecord
from models.base import get_session
from models.user import User
from models.user_account import UserAccount
from schemas.checkin import CheckinAccountSummary
from schemas.user import (
    AdRewardGrantRequest,
    AdRewardGrantResponse,
    UserLoginRequest,
    UserLoginResponse,
    UserProfile,
    UserUpdateRequest,
)
from services.user_service import UserService
from services.ad_analytics_service import get_reward_config, now_keys, scene_location
from services.points_account_service import PointsAccountService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/user", tags=["user"])


@router.post("/login", summary="微信登录/注册")
async def login(req: UserLoginRequest, session: AsyncSession = Depends(get_session)):
    wx_data = await UserService.wx_code2session(req.code)
    openid = wx_data.get("openid")
    if not openid:
        return response([], 400, wx_data)

    user, is_new = await UserService.get_or_create_user(
        session,
        openid,
        req.nickname,
        req.avatar,
        req.invite_code,
    )

    token = create_access_token(
        {
            "openid": openid,
        }
    )

    account, _ = await PointsAccountService.ensure_user_account(session, user.id)
    profile = _build_profile(user, account)
    return response(
        data=UserLoginResponse(
            token=token,
            is_new_user=is_new,
            user=profile,
        ).model_dump(mode="json"),
        msg="注册成功" if is_new else "登录成功",
    )


@router.get("/profile", summary="获取用户信息")
async def get_profile(
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).where(User.openid == openid))
    user = result.scalar_one_or_none()
    if not user:
        return response([], 404, "user not found")

    account, _ = await PointsAccountService.ensure_user_account(session, user.id)
    return response(data=_build_profile(user, account).model_dump(mode="json"))


@router.put("/profile", summary="更新用户信息")
async def update_profile(
    req: UserUpdateRequest,
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).where(User.openid == openid))
    user = result.scalar_one_or_none()
    if not user:
        return response([], 404, "user not found")

    if req.avatar is not None:
        user.avatar = req.avatar
    if req.nickname is not None:
        user.nickname = req.nickname

    await session.flush()
    account, _ = await PointsAccountService.ensure_user_account(session, user.id)
    return response(data=_build_profile(user, account).model_dump(mode="json"), msg="更新成功")


@router.post("/ad-reward", summary="发放小游戏激励广告奖励")
async def grant_ad_reward(
    req: AdRewardGrantRequest,
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user_result = await session.execute(select(User).where(User.openid == openid))
    user = user_result.scalar_one_or_none()
    if not user:
        return response([], 404, "user not found")

    existing_result = await session.execute(
        select(AdRewardRecord).where(AdRewardRecord.event_id == req.event_id)
    )
    existing = existing_result.scalar_one_or_none()
    if existing:
        return response(
            data=AdRewardGrantResponse(
                event_id=existing.event_id,
                reward_points=float(req.reward_points),
                reward_amount=float(existing.reward_amount),
                balance=float(user.balance),
                total_income=float(user.total_income),
                credited=bool(existing.credited),
            ).model_dump(mode="json")
        )

    reward_config = await get_reward_config(session)
    reward_points = float(req.reward_points)
    expected_points = float(reward_config["points_per_reward"])
    if abs(reward_points - expected_points) > 0.001:
        return response([], 400, "invalid reward points")

    reward_amount_decimal = Decimal(str(reward_config["cash_per_reward"])).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )
    reward_amount = float(reward_amount_decimal)

    user.balance = round(float(user.balance) + reward_amount, 2)
    user.total_income = round(float(user.total_income) + reward_amount, 2)

    session.add(
        AdRewardRecord(
            event_id=req.event_id,
            user_id=user.id,
            scene=req.scene or "game_jump",
            ad_unit_id=req.ad_unit_id or "",
            is_ended=bool(req.is_ended),
            reward_amount=reward_amount,
            credited=True,
        )
    )
    module = (req.module or "").strip()
    section = (req.section or "").strip()
    if not module or not section:
        module, section = scene_location(req.scene or "game_jump")
    date_key, week_key, month_key = now_keys()
    session.add(
        AdEventRecord(
            event_id=req.event_id,
            user_id=user.id,
            openid=openid,
            module=module,
            section=section,
            scene=req.scene or "game_jump",
            ad_unit_id=req.ad_unit_id or "",
            event_type="reward",
            is_completed=bool(req.is_ended),
            reward_points=reward_points,
            reward_amount=reward_amount,
            date_key=date_key,
            week_key=week_key,
            month_key=month_key,
        )
    )
    await session.flush()

    return response(
        data=AdRewardGrantResponse(
            event_id=req.event_id,
            reward_points=reward_points,
            reward_amount=reward_amount,
            balance=float(user.balance),
            total_income=float(user.total_income),
            credited=True,
        ).model_dump(mode="json")
    )


@router.post("/upload_image", summary="头像上传")
async def upload_image(file: UploadFile):
    return await _handle_upload(file)


def _build_profile(user: User, account: UserAccount) -> UserProfile:
    return UserProfile(
        id=str(user.id),
        openid=user.openid,
        nickname=user.nickname,
        avatar=user.avatar,
        invite_code=user.invite_code,
        is_vip=user.is_vip,
        vip_expire_at=user.vip_expire_at,
        balance=float(user.balance),
        frozen_balance=float(user.frozen_balance),
        total_income=float(user.total_income),
        total_withdrawn=float(user.total_withdrawn),
        invite_count=user.invite_count,
        team_count=user.team_count,
        created_at=user.created_at,
        account=CheckinAccountSummary(
            total_points=int(account.total_points),
            withdrawable_points=int(account.withdrawable_points),
            frozen_points=int(account.frozen_points),
            consumable_points=int(account.consumable_points),
        ),
    )


async def _handle_upload(file: UploadFile):
    max_file_size = 10 * 1024 * 1024
    allowed_types = {"image/jpeg", "image/png", "image/webp"}

    if file.content_type not in allowed_types:
        return response([], 422, "请上传合法的头像")
    if cast(int, file.size) > max_file_size:
        return response([], 422, "上传的头像过大")

    original_ext = os.path.splitext(cast(str, file.filename))[1]
    new_filename = f"{uuid4().hex}{original_ext}"
    save_folder = os.path.join(os.getcwd(), "image")
    os.makedirs(save_folder, exist_ok=True)
    file_path = os.path.join(save_folder, new_filename)

    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    public_base_url = os.getenv("PUBLIC_BASE_URL") or os.getenv("API_BASE_URL") or ""
    domain = os.getenv("DOMAIN") or ""
    ip = os.getenv("IP", "127.0.0.1").strip()
    port = os.getenv("PORT", "8000").strip()

    if public_base_url:
        base_url = public_base_url.rstrip("/")
    elif domain:
        base_url = f"https://{domain.strip().strip('/')}"
    elif ip.startswith(("http://", "https://")):
        base_url = ip.rstrip("/")
    else:
        base_url = f"http://{ip}:{port}"

    return response({"upload_image": f"{base_url}/image/{new_filename}"})
