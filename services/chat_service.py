"""
聊天服务 — chat_service

MVC 架构中的 Service 层，处理在线客服聊天。

迁移来源:
  - 云函数 cloudfunctions/chatService/index.js

核心功能:
  1. 用户发送消息
  2. 管理员回复消息（标记 is_read=False）
  3. 获取聊天历史（分页，按时间正序）
  4. 标记已读
"""

import logging
from datetime import datetime
from typing import List, Tuple
from uuid import UUID

from sqlmodel import select, func, and_
from sqlmodel.ext.asyncio.session import AsyncSession

from models.chat import ChatMessage

logger = logging.getLogger(__name__)

MAX_CONTENT_LENGTH = 1000


class ChatService:
    """聊天业务逻辑服务"""

    @staticmethod
    async def send_message(
        session: AsyncSession,
        user_id: UUID,
        content: str,
        sender: str = "user",
        msg_type: str = "text",
    ) -> ChatMessage:
        """
        发送消息。

        Args:
            session: 数据库会话
            user_id: 用户 ID
            content: 消息内容
            sender: 发送者 (user / admin)
            msg_type: 消息类型 (text / image)
        """
        if not content or not content.strip():
            raise ValueError("消息内容不能为空")

        trimmed = content.strip()[:MAX_CONTENT_LENGTH]

        message = ChatMessage(
            user_id=user_id,
            sender=sender,
            content=trimmed,
            msg_type=msg_type,
            is_read=False,
        )
        session.add(message)
        await session.flush()

        logger.info(f"[Chat] 消息已发送: user={user_id}, sender={sender}")
        return message

    @staticmethod
    async def admin_reply(
        session: AsyncSession,
        user_id: UUID,
        content: str,
    ) -> ChatMessage:
        """管理员回复消息"""
        return await ChatService.send_message(
            session, user_id, content, sender="admin"
        )

    @staticmethod
    async def get_history(
        session: AsyncSession,
        user_id: UUID,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[ChatMessage], int, bool]:
        """
        获取聊天历史（时间正序）。

        Returns:
            (messages, total, has_more)
        """
        # 总数
        count_stmt = (
            select(func.count())
            .select_from(ChatMessage)
            .where(ChatMessage.user_id == user_id)
        )
        result = await session.execute(count_stmt)
        total = result.scalar() or 0

        # 列表（正序）
        skip = (page - 1) * page_size
        list_stmt = (
            select(ChatMessage)
            .where(ChatMessage.user_id == user_id)
            .order_by(ChatMessage.created_at.asc())
            .offset(skip)
            .limit(page_size)
        )
        result = await session.execute(list_stmt)
        messages = result.scalars().all()

        has_more = (skip + len(messages)) < total
        return list(messages), total, has_more

    @staticmethod
    async def mark_as_read(session: AsyncSession, user_id: UUID) -> int:
        """
        将 admin 发给此用户的所有未读消息标记为已读。

        Returns:
            更新的消息条数
        """
        stmt = (
            select(ChatMessage)
            .where(
                and_(
                    ChatMessage.user_id == user_id,
                    ChatMessage.sender == "admin",
                    ChatMessage.is_read == False,  # noqa: E712
                )
            )
        )
        result = await session.execute(stmt)
        unread_messages = result.scalars().all()

        count = 0
        for msg in unread_messages:
            msg.is_read = True
            count += 1

        await session.flush()
        logger.info(f"[Chat] 标记已读: user={user_id}, count={count}")
        return count
