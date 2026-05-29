"""
聊天消息表 — chat_messages

对应原云开发集合: chat_messages
迁移逻辑来源: cloudfunctions/chatService/index.js

核心业务:
  - 用户 ↔ 管理员的在线客服聊天
  - 支持文本和图片消息
  - 已读/未读状态
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlmodel import Column, DateTime, Field, Relationship, SQLModel, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import String, Text, Boolean, ForeignKey

if TYPE_CHECKING:
    from models.user import User


class ChatMessage(SQLModel, table=True):
    __tablename__ = "chat_messages"

    # ── 主键 ──
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    )

    # ── 用户 ──
    user_id: uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True),
        description="用户 ID",
    )

    # ── 消息内容 ──
    sender: str = Field(
        sa_column=Column(String(10), nullable=False),
        description="发送者: user / admin",
    )
    content: str = Field(
        sa_column=Column(Text, nullable=False),
        description="消息内容，最多 1000 字",
    )
    msg_type: str = Field(
        default="text",
        sa_column=Column(String(10), default="text"),
        description="消息类型: text / image",
    )

    # ── 已读状态 ──
    is_read: bool = Field(
        default=False,
        sa_column=Column(Boolean, default=False),
    )

    # ── 时间 ──
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), index=True),
    )

    # ── 关联 ──
    user: "User" = Relationship(back_populates="chat_messages")
