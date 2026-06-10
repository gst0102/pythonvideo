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

from models.invite_relation import InviteRelation
from models.user import User
from services.invite_reward_service import InviteRewardService
from services.points_account_service import PointsAccountService

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
            invite_code: 登录分享参数中的邀请人邀请码（首次有效绑定时使用）

        Returns:
            (User, is_new_user)
        """
        # 1. 查询是否已存在
        normalized_nickname = _normalize_nickname(nickname, openid)
        normalized_avatar = _normalize_avatar(avatar)
        stmt = select(User).where(User.openid == openid)
        result = await session.execute(stmt)
        existing_user = result.scalar_one_or_none()

        if existing_user:
            # 老用户：更新资料
            if nickname and nickname.strip():
                existing_user.nickname = normalized_nickname
            if avatar and avatar.strip():
                existing_user.avatar = normalized_avatar
            await _bind_inviter_if_allowed(session, existing_user, invite_code)
            existing_user.updated_at = datetime.utcnow()
            await session.flush()
            await PointsAccountService.ensure_user_account(session, existing_user.id)
            return existing_user, False

        # 2. 新用户：注册
        new_invite_code = _generate_invite_code()

        # 3. 创建用户。邀请关系在 flush 后统一绑定，便于防自邀和写追踪表。
        user = User(
            openid=openid,
            nickname=normalized_nickname,
            avatar=normalized_avatar,
            invite_code=new_invite_code,
        )
        session.add(user)
        await session.flush()

        # 4. 首次绑定邀请人。已有绑定时不覆盖，绑定成功时写 invite_relations 追踪记录。
        await _bind_inviter_if_allowed(session, user, invite_code)

        await PointsAccountService.ensure_user_account(session, user.id)
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


def _normalize_nickname(nickname: str, openid: str) -> str:
    cleaned = (nickname or "").strip()
    if cleaned:
        return cleaned
    suffix = (openid or "")[-6:]
    return f"微信用户{suffix}" if suffix else "微信用户"


def _normalize_avatar(avatar: str) -> str:
    return (avatar or "").strip()


async def _find_user_by_invite_code(session: AsyncSession, invite_code: str) -> Optional[User]:
    """根据邀请码查找用户"""
    stmt = select(User).where(User.invite_code == invite_code)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _bind_inviter_if_allowed(
    session: AsyncSession,
    user: User,
    invite_code: Optional[str],
    source: str = "login",
) -> bool:
    """Bind an inviter once when login carries a share invite code.

    Rules:
    - Empty/invalid invite code: no-op.
    - Existing parent or existing relation: no rebind.
    - Self invite: no-op.
    - Successful bind updates user parent fields, inviter counters, and trace row.
    """
    normalized_code = (invite_code or "").strip()
    if not normalized_code or user.parent_id:
        return False

    existing_relation_result = await session.execute(
        select(InviteRelation).where(InviteRelation.invitee_id == user.id)
    )
    if existing_relation_result.scalar_one_or_none():
        return False

    inviter = await _find_user_by_invite_code(session, normalized_code)
    if not inviter or inviter.id == user.id:
        return False

    user.parent_id = inviter.id
    user.grand_parent_id = inviter.parent_id
    user.updated_at = datetime.utcnow()
    relation = InviteRelation(
        inviter_id=inviter.id,
        invitee_id=user.id,
        invite_code=normalized_code,
        source=source,
    )
    session.add(relation)

    await _inc_invite_stats(session, inviter.id, is_direct=True)
    if inviter.parent_id:
        await _inc_invite_stats(session, inviter.parent_id, is_direct=False)
    await InviteRewardService.grant_register_reward_for_relation(session, relation)
    await session.flush()
    return True


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
