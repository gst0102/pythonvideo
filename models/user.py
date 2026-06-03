"""User model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Column, Numeric, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlmodel import DateTime, Field, Relationship, SQLModel, func

if TYPE_CHECKING:
    from models.chat import ChatMessage
    from models.commission import CommissionRecord
    from models.order import Order
    from models.withdrawal import WithdrawalRecord


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    )
    openid: str = Field(sa_column=Column(String(64), unique=True, nullable=False, index=True))
    nickname: str = Field(sa_column=Column(String(100), nullable=False))
    avatar: str = Field(default="", sa_column=Column(String(500), default=""))
    invite_code: str = Field(sa_column=Column(String(10), unique=True, nullable=False, index=True))
    parent_id: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=Column(UUID(as_uuid=True), nullable=True, index=True),
    )
    grand_parent_id: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=Column(UUID(as_uuid=True), nullable=True),
    )
    invite_count: int = Field(default=0)
    indirect_count: int = Field(default=0)
    team_count: int = Field(default=0)
    balance: float = Field(default=0.0, sa_column=Column(Numeric(10, 2), default=0.0))
    frozen_balance: float = Field(default=0.0, sa_column=Column(Numeric(10, 2), default=0.0))
    total_income: float = Field(default=0.0, sa_column=Column(Numeric(10, 2), default=0.0))
    total_withdrawn: float = Field(default=0.0, sa_column=Column(Numeric(10, 2), default=0.0))
    is_vip: bool = Field(default=False, sa_column=Column(Boolean, default=False))
    vip_expire_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    anime_subscriptions: list = Field(default_factory=list, sa_column=Column(JSON, default=[]))
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )

    orders: list["Order"] = Relationship(back_populates="user")
    commissions: list["CommissionRecord"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"foreign_keys": "[CommissionRecord.user_id]"},
    )
    withdrawals: list["WithdrawalRecord"] = Relationship(back_populates="user")
    chat_messages: list["ChatMessage"] = Relationship(back_populates="user")
