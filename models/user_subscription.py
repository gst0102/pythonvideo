"""
用户订阅表 — user_subscriptions

记录用户对番剧的订阅关系，支持催更标记和推送检测。

设计要点：
  - 每人每番剧只能订阅一次 (UNIQUE user_id, anime_id)
  - last_episode 用于增量推送检测（对比 anime_resources.episode）
  - is_reminded 标记用户是否需要更新提醒
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlmodel import Column, DateTime, Field, SQLModel, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import String, Boolean


class UserSubscription(SQLModel, table=True):
    __tablename__ = "user_subscriptions"

    # ── 主键 ──
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    )

    # ── 关联 ──
    user_id: uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), nullable=False, index=True),
        description="用户 ID → users.id",
    )

    anime_id: str = Field(
        sa_column=Column(String(100), nullable=False, index=True),
        description="番剧 ID → anime_resources.anime_id",
    )

    # ── 催更 ──
    is_reminded: bool = Field(
        default=False,
        sa_column=Column(Boolean, default=False),
        description="是否已催更（需要更新提醒）",
    )

    last_episode: Optional[str] = Field(
        default=None,
        sa_column=Column(String(100), nullable=True),
        description="用户最后看到的集数，用于增量推送比对",
    )

    # ── 时间戳 ──
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
