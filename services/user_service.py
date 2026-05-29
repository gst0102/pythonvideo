"""
用户服务 — user_service

MVC 架构中的 Service 层，处理用户相关的所有业务逻辑。

迁移来源:
  - 云函数 cloudfunctions/userLogin/index.js
  - 云函数中的邀请关系更新逻辑

核心功能:
  1. 微信 code2Session 登录 + 自动注册
  2. 新用户注册时处理邀请关系（二级邀请树）
  3. 用户资料查询与更新
"""

import secrets
import logging
from datetime import datetime
from typing import Optional, Tuple
from uuid import UUID

import httpx
from dotenv import load_dotenv
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from models.user import User

load_dotenv()
logger = logging.getLogger(__name__)


class UserService:
    """用户业务逻辑服务"""

    @staticmethod
    async def wx_code2session(code: str) -> dict:
        """调用微信 jscode2session 换取 openid"""
        import os
        appid = os.getenv("APPID")
        secret = os.getenv("SECRET")

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.weixin.qq.com/sns/jscode2session",
                params={
                    "appid": appid,
                    "secret": secret,
                    "js_code": code,
                    "grant_type": "authorization_code",
                },
            )
            data = resp.json()
        return data

    @staticmethod
    async def get_or_create_user(
        session: AsyncSession,
        openid: str,
        nickname: str,
        avatar: str,
        invite_code: Optional[str] = None,
    ) -> Tuple[User, bool]:
        """
        查询或创建用户。

        Args:
            session: 数据库会话
            openid: 微信 openid
            nickname: 用户昵称
            avatar: 头像 URL
            invite_code: 邀请码（新用户注册时传入）

        Returns:
            (User, is_new_user)
        """
        # 1. 查询是否已存在
        stmt = select(User).where(User.openid == openid)
        result = await session.execute(stmt)
        existing_user = result.scalar_one_or_none()

        if existing_user:
            # 老用户：更新资料
            existing_user.nickname = nickname
            existing_user.avatar = avatar
            existing_user.updated_at = datetime.utcnow()
            await session.flush()
            return existing_user, False

        # 2. 新用户：注册
        new_invite_code = _generate_invite_code()

        # 3. 处理邀请关系
        parent_id = None
        grand_parent_id = None

        if invite_code:
            inviter = await _find_user_by_invite_code(session, invite_code)
            if inviter and str(inviter.id) != "":  # 不能邀请自己
                parent_id = inviter.id
                grand_parent_id = inviter.parent_id

        # 4. 创建用户
        user = User(
            openid=openid,
            nickname=nickname,
            avatar=avatar,
            invite_code=new_invite_code,
            parent_id=parent_id,
            grand_parent_id=grand_parent_id,
        )
        session.add(user)
        await session.flush()

        # 5. 更新邀请人的统计数据
        if parent_id:
            await _inc_invite_stats(session, parent_id, is_direct=True)
        if grand_parent_id:
            await _inc_invite_stats(session, grand_parent_id, is_direct=False)

        return user, True

    @staticmethod
    async def get_user_by_id(session: AsyncSession, user_id: UUID) -> Optional[User]:
        """根据 ID 获取用户"""
        stmt = select(User).where(User.id == user_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def update_profile(session: AsyncSession, user_id: UUID, **kwargs) -> Optional[User]:
        """更新用户资料"""
        user = await UserService.get_user_by_id(session, user_id)
        if not user:
            return None
        for key, value in kwargs.items():
            if hasattr(user, key) and value is not None:
                setattr(user, key, value)
        user.updated_at = datetime.utcnow()
        await session.flush()
        return user


# ── 内部辅助函数 ────────────────────────────────────────────────

def _generate_invite_code(length: int = 10) -> str:
    """生成加密安全的随机邀请码"""
    return secrets.token_hex(length // 2)[:length]


async def _find_user_by_invite_code(session: AsyncSession, invite_code: str) -> Optional[User]:
    """根据邀请码查找用户"""
    stmt = select(User).where(User.invite_code == invite_code)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _inc_invite_stats(session: AsyncSession, user_id: UUID, is_direct: bool):
    """更新邀请人的统计数字"""
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    inviter = result.scalar_one_or_none()
    if not inviter:
        return

    inviter.team_count += 1
    if is_direct:
        inviter.invite_count += 1
    else:
        inviter.indirect_count += 1

    inviter.updated_at = datetime.utcnow()
    await session.flush()
