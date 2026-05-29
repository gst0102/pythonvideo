"""
用户接口 — /user

MVC 架构中的 Controller 层。

改造说明:
  - 原登录只做 code2Session + 发 JWT，用户数据靠云函数
  - 现在直接操作 PostgreSQL，登录 + 注册 + 邀请关系一步完成
  - 新增: 用户资料查询、更新接口
"""

import logging

from fastapi import APIRouter, Depends, UploadFile
from sqlmodel.ext.asyncio.session import AsyncSession

from core.response import response
from schemas.user import (
    UserLoginRequest,
    UserLoginResponse,
    UserProfile,
    UserUpdateRequest,
)
from models.user import User
from models.base import get_session
from services.user_service import UserService
from jwt_create import create_access_token, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/user", tags=["用户相关接口"])

# ═══════════════════════════════════════════════════════════════
#  登录/注册
# ═══════════════════════════════════════════════════════════════

@router.post("/login", summary="微信登录/注册")
async def login(req: UserLoginRequest, session: AsyncSession = Depends(get_session)):
    """
    微信小程序登录。
    新用户自动注册，支持邀请码（二级分销）。
    """
    # 1. code2Session 获取 openid
    wx_data = await UserService.wx_code2session(req.code)
    openid = wx_data.get("openid")
    if not openid:
        return response([], 400, wx_data)

    # 2. 查询或创建用户（含邀请关系处理）
    user, is_new = await UserService.get_or_create_user(
        session, openid, req.nickname, req.avatar, req.invite_code,
    )

    # 3. 生成 JWT
    token = create_access_token({"openid": openid})

    # 4. 组装响应
    profile = _build_profile(user)
    return response(
        data=UserLoginResponse(
            token=token,
            is_new_user=is_new,
            user=profile,
        ).model_dump(mode="json"),
        msg="注册成功" if is_new else "登录成功",
    )


# ═══════════════════════════════════════════════════════════════
#  用户资料
# ═══════════════════════════════════════════════════════════════

@router.get("/profile", summary="获取用户信息")
async def get_profile(
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """获取当前登录用户信息"""
    stmt = (
        __import__("sqlmodel").select(User)
        .where(User.openid == openid)
    )
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        return response([], 404, "用户不存在")

    return response(data=_build_profile(user).model_dump(mode="json"))


@router.put("/profile", summary="更新用户信息")
async def update_profile(
    req: UserUpdateRequest,
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """更新用户头像/昵称"""
    stmt = (
        __import__("sqlmodel").select(User)
        .where(User.openid == openid)
    )
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        return response([], 404, "用户不存在")

    if req.avatar is not None:
        user.avatar = req.avatar
    if req.nickname is not None:
        user.nickname = req.nickname

    import datetime
    user.updated_at = datetime.datetime.utcnow()
    await session.flush()

    return response(data=_build_profile(user).model_dump(mode="json"), msg="更新成功")


# ═══════════════════════════════════════════════════════════════
#  图片上传（保留原有）
# ═══════════════════════════════════════════════════════════════

@router.post("/upload_image", summary="头像上传")
async def upload_image(file: UploadFile):
    """保留原有头像上传逻辑"""
    # 委托给 upload_router
    return await _handle_upload(file)


# ═══════════════════════════════════════════════════════════════
#  工具函数
# ═══════════════════════════════════════════════════════════════

def _build_profile(user: User) -> UserProfile:
    """从 User 模型构建响应对象"""
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
    )


async def _handle_upload(file: UploadFile):
    """图片上传处理（保留原有逻辑）"""
    import os
    from uuid import uuid4
    from typing import cast

    MAX_FILE_SIZE = 10 * 1024 * 1024
    ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}

    if file.content_type not in ALLOWED_TYPES:
        return response([], 422, "请上传合法的头像")
    if cast(int, file.size) > MAX_FILE_SIZE:
        return response([], 422, "上传的头像太大")

    original_ext = os.path.splitext(cast(str, file.filename))[1]
    new_filename = f"{uuid4().hex}{original_ext}"
    save_folder = os.path.join(os.getcwd(), "image")
    file_path = os.path.join(save_folder, new_filename)

    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    import os as _os
    ip = _os.getenv("IP", "127.0.0.1")
    port = _os.getenv("PORT", "8000")
    return response({"upload_image": f"{ip}:{port}/image/{new_filename}"})
