"""
用户表 — users

对应原云开发集合: user-info
迁移逻辑来源: cloudfunctions/userLogin/index.js

核心业务:
  - 微信 openid 唯一标识
  - 二级邀请树（parent_id → grand_parent_id）
  - 余额、冻结机制（提现安全）
  - VIP 会员状态
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import Column, DateTime, Field, Relationship, SQLModel, func
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy import String, Numeric, Boolean

if TYPE_CHECKING:
    from models.order import Order
    from models.commission import CommissionRecord
    from models.withdrawal import WithdrawalRecord
    from models.chat import ChatMessage


class User(SQLModel, table=True):
    __tablename__ = "users"

    # ── 主键 ──
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    )

    # ── 微信身份 ──
    openid: str = Field(
        sa_column=Column(String(64), unique=True, nullable=False, index=True),
    )

    # ── 个人资料 ──
    nickname: str = Field(
        sa_column=Column(String(100), nullable=False),
    )
    avatar: str = Field(
        default="",
        sa_column=Column(String(500), default=""),
    )

    # ── 邀请系统 ──
    invite_code: str = Field(
        sa_column=Column(String(10), unique=True, nullable=False, index=True),
    )

    # 一级邀请人（直接邀请我的）
    parent_id: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=Column(UUID(as_uuid=True), nullable=True, index=True),
    )

    # 二级邀请人（邀请人的邀请人）
    grand_parent_id: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=Column(UUID(as_uuid=True), nullable=True),
    )

    # 邀请统计
    invite_count: int = Field(default=0)       # 我直接邀请的人数
    indirect_count: int = Field(default=0)      # 间接邀请人数
    team_count: int = Field(default=0)          # 总团队人数

    # ── 财务 ──
    balance: float = Field(
        default=0.00,
        sa_column=Column(Numeric(10, 2), default=0.00),
    )
    frozen_balance: float = Field(
        default=0.00,
        sa_column=Column(Numeric(10, 2), default=0.00),
    )
    total_income: float = Field(
        default=0.00,
        sa_column=Column(Numeric(10, 2), default=0.00),
    )
    total_withdrawn: float = Field(
        default=0.00,
        sa_column=Column(Numeric(10, 2), default=0.00),
    )

    # ── VIP ──
    is_vip: bool = Field(
        default=False,
        sa_column=Column(Boolean, default=False),
    )
    vip_expire_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    # ── 番剧订阅 ──
    anime_subscriptions: list = Field(
        default=[],
        sa_column=Column(JSON, default=[]),
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

    # ── 关联 ──
    orders: list["Order"] = Relationship(back_populates="user")
    commissions: list["CommissionRecord"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"foreign_keys": "[CommissionRecord.user_id]"},
    )
    withdrawals: list["WithdrawalRecord"] = Relationship(back_populates="user")
    chat_messages: list["ChatMessage"] = Relationship(back_populates="user")
