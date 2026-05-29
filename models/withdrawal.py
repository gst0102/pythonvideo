"""
提现记录表 — withdraw_records

对应原云开发集合: withdraw_records
迁移逻辑来源: cloudfunctions/merchantTransfer + transferCallback

核心业务:
  - 用户提现申请到微信商家转账的完整流程
  - 状态流转: processing → success / failed
  - 冻结机制: 提现中余额冻结，防止重复提现
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import Column, DateTime, Field, Relationship, SQLModel, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import String, Numeric, Text, ForeignKey

if TYPE_CHECKING:
    from models.user import User


class WithdrawalRecord(SQLModel, table=True):
    __tablename__ = "withdraw_records"

    # ── 主键 ──
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    )

    # ── 用户 ──
    user_id: uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True),
    )

    # ── 金额 ──
    amount: float = Field(
        sa_column=Column(Numeric(10, 2), nullable=False),
        description="提现金额（元）",
    )

    # ── 状态 ──
    status: str = Field(
        default="processing",
        sa_column=Column(String(20), default="processing", index=True),
        description="processing / success / failed",
    )

    # ── 微信转账信息 ──
    batch_no: str = Field(
        sa_column=Column(String(64), unique=True, nullable=False, index=True),
        description="商户批次单号",
    )
    transfer_bill_no: Optional[str] = Field(
        default=None,
        sa_column=Column(String(64), nullable=True),
        description="微信转账单号",
    )

    # ── 失败原因 ──
    fail_reason: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
    )

    # ── 安全 ──
    ip: Optional[str] = Field(
        default=None,
        sa_column=Column(String(45), nullable=True),
    )

    # ── 时间 ──
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )

    # ── 关联 ──
    user: "User" = Relationship(back_populates="withdrawals")
