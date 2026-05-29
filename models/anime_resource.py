"""
影视资源表 — anime_resources

存储从外部数据源同步的番剧/电影/4K 资源数据。
每 15 分钟增量同步，按 baidu_url / quark_url 做唯一去重。

设计要点：
  - baidu_url 和 quark_url 使用部分唯一索引（NULL 不冲突）
  - is_active 标记而非物理删除（保留已订阅用户的历史引用）
  - 增量 upsert：URL 相同 → 覆盖更新；新数据 → 插入
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlmodel import Column, DateTime, Field, SQLModel, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import String, Boolean, Text


class AnimeResource(SQLModel, table=True):
    __tablename__ = "anime_resources"

    # ── 主键 ──
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    )

    # ── 外部源 ID ──
    anime_id: str = Field(
        sa_column=Column(String(100), nullable=False, index=True),
        description="外部数据源的番剧 ID",
    )

    # ── 基本信息 ──
    title: str = Field(
        sa_column=Column(String(500), nullable=False),
        description="番剧标题（含画质等信息）",
    )

    category: str = Field(
        default="anime",
        sa_column=Column(String(20), nullable=False, index=True, server_default="anime"),
        description="资源类型：anime / movie / 4k",
    )

    quality: Optional[str] = Field(
        default=None,
        sa_column=Column(String(20), nullable=True),
        description="画质：1080P / 4K / 720P",
    )

    episode: Optional[str] = Field(
        default=None,
        sa_column=Column(String(100), nullable=True),
        description="当前更新进度，如「更至36集」",
    )

    status: Optional[str] = Field(
        default=None,
        sa_column=Column(String(20), nullable=True),
        description="状态：更新中 / 完结 / 预告",
    )

    # ── 网盘链接 ──
    baidu_url: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="百度网盘链接（部分唯一索引）",
    )

    baidu_password: Optional[str] = Field(
        default=None,
        sa_column=Column(String(20), nullable=True),
    )

    quark_url: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="夸克网盘链接（部分唯一索引）",
    )

    # ── 元数据 ──
    source_update_time: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="外部源的最后更新时间",
    )

    is_active: bool = Field(
        default=True,
        sa_column=Column(Boolean, default=True, index=True),
        description="是否活跃（外部源删除后标记为 False）",
    )

    # ── 时间戳 ──
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )
