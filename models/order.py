"""
订单表 — orders

对应原云开发集合: order-info
迁移逻辑来源: cloudfunctions/controllers/weixinpay.py

核心业务:
  - VIP 购买订单
  - 支付状态流转: pending → paid / cancelled
  - 关联微信支付: out_trade_no + transaction_id
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import Column, DateTime, Field, Relationship, SQLModel, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import String, Numeric, ForeignKey

if TYPE_CHECKING:
    from models.user import User


class Order(SQLModel, table=True):
    __tablename__ = "orders"

    # ── 主键 ──
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    )

    # ── 用户 ──
    user_id: uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True),
    )

    # ── 订单信息 ──
    amount: float = Field(
        sa_column=Column(Numeric(10, 2), nullable=False),
        description="订单金额（元）",
    )
    period: str = Field(
        sa_column=Column(String(20), nullable=False),
        description="订阅周期: month / quarter / year",
    )
    duration_days: int = Field(
        default=30,
        description="VIP 有效天数",
    )
    description: str = Field(
        default="",
        sa_column=Column(String(200), default=""),
    )

    # ── 支付信息 ──
    out_trade_no: str = Field(
        sa_column=Column(String(64), unique=True, nullable=False, index=True),
        description="商户订单号",
    )
    transaction_id: Optional[str] = Field(
        default=None,
        sa_column=Column(String(64), nullable=True),
        description="微信支付订单号",
    )

    # ── 状态 ──
    status: str = Field(
        default="pending",
        sa_column=Column(String(20), default="pending"),
        description="pending / paid / cancelled",
    )

    # ── 时间 ──
    paid_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )

    # ── 关联 ──
    user: "User" = Relationship(back_populates="orders")
