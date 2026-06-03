"""Withdrawal record model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import DateTime, Field, Relationship, SQLModel, func

if TYPE_CHECKING:
    from models.user import User


class WithdrawalRecord(SQLModel, table=True):
    __tablename__ = "withdraw_records"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    )
    user_id: uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True),
    )
    amount: float = Field(sa_column=Column(Numeric(10, 2), nullable=False))
    status: str = Field(default="processing", sa_column=Column(String(20), default="processing", index=True))
    batch_no: str = Field(sa_column=Column(String(64), unique=True, nullable=False, index=True))
    transfer_bill_no: Optional[str] = Field(default=None, sa_column=Column(String(64), nullable=True))
    fail_reason: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    ip: Optional[str] = Field(default=None, sa_column=Column(String(45), nullable=True))
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    completed_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )

    user: "User" = Relationship(back_populates="withdrawals")
