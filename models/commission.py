"""
佣金记录表 — commission_records

对应原云开发集合: commission_records
迁移逻辑来源: cloudfunctions/userLogin（支付回调中计算佣金）

核心业务:
  - VIP 充值产生的两级分销佣金
  - 一级 10%，二级 5%
  - 支付成功时自动结算
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import Column, DateTime, Field, Relationship, SQLModel, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import String, Numeric, SmallInteger, ForeignKey

if TYPE_CHECKING:
    from models.user import User
    from models.order import Order


class CommissionRecord(SQLModel, table=True):
    __tablename__ = "commission_records"

    # ── 主键 ──
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    )

    # ── 佣金归属 ──
    user_id: uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True),
        description="获得佣金的用户（邀请人）",
    )

    # ── 佣金来源 ──
    from_user_id: uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True),
        description="贡献佣金的用户（购买 VIP 的人）",
    )
    order_id: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=Column(UUID(as_uuid=True), nullable=True),
        description="关联的订单",
    )

    # ── 金额 ──
    order_amount: float = Field(
        sa_column=Column(Numeric(10, 2), nullable=False),
        description="订单金额（元）",
    )
    commission_rate: float = Field(
        sa_column=Column(Numeric(5, 2), nullable=False),
        description="佣金比例（如 10.00 = 10%）",
    )
    commission_amount: float = Field(
        sa_column=Column(Numeric(10, 2), nullable=False),
        description="实际佣金金额（元）",
    )

    # ── 层级 ──
    level: int = Field(
        sa_column=Column(SmallInteger, nullable=False),
        description="1=一级邀请, 2=二级邀请",
    )

    # ── 类型 & 状态 ──
    type: str = Field(
        default="vip_recharge",
        sa_column=Column(String(20), default="vip_recharge"),
    )
    status: str = Field(
        default="settled",
        sa_column=Column(String(20), default="settled"),
        description="pending / settled / cancelled",
    )

    # ── 时间 ──
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )

    # ── 关联 ──
    user: "User" = Relationship(
        back_populates="commissions",
        sa_relationship_kwargs={"foreign_keys": "[CommissionRecord.user_id]"},
    )
    from_user: Optional["User"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[CommissionRecord.from_user_id]"},
    )
