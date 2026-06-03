"""Chat service."""

import logging
from typing import List, Tuple
from uuid import UUID

from sqlmodel import and_, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from models.chat import ChatMessage

logger = logging.getLogger(__name__)
MAX_CONTENT_LENGTH = 1000


class ChatService:
    @staticmethod
    async def send_message(
        session: AsyncSession,
        user_id: UUID,
        content: str,
        sender: str = "user",
        msg_type: str = "text",
    ) -> ChatMessage:
        if not content or not content.strip():
            raise ValueError("content is required")

        message = ChatMessage(
            user_id=user_id,
            sender=sender,
            content=content.strip()[:MAX_CONTENT_LENGTH],
            msg_type=msg_type,
            is_read=False,
        )
        session.add(message)
        await session.flush()
        return message

    @staticmethod
    async def admin_reply(session: AsyncSession, user_id: UUID, content: str) -> ChatMessage:
        return await ChatService.send_message(session, user_id, content, sender="admin")

    @staticmethod
    async def get_history(
        session: AsyncSession,
        user_id: UUID,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[ChatMessage], int, bool]:
        count_result = await session.execute(
            select(func.count()).select_from(ChatMessage).where(ChatMessage.user_id == user_id)
        )
        total = count_result.scalar() or 0
        skip = (page - 1) * page_size
        list_result = await session.execute(
            select(ChatMessage)
            .where(ChatMessage.user_id == user_id)
            .order_by(ChatMessage.created_at.asc())
            .offset(skip)
            .limit(page_size)
        )
        messages = list(list_result.scalars().all())
        return messages, total, (skip + len(messages)) < total

    @staticmethod
    async def mark_as_read(session: AsyncSession, user_id: UUID) -> int:
        result = await session.execute(
            select(ChatMessage).where(
                and_(
                    ChatMessage.user_id == user_id,
                    ChatMessage.sender == "admin",
                    ChatMessage.is_read == False,  # noqa: E712
                )
            )
        )
        unread_messages = result.scalars().all()
        for msg in unread_messages:
            msg.is_read = True
        await session.flush()
        return len(unread_messages)
