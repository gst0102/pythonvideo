"""Equity cash ledger for invite-benefit money movements."""

import uuid
from datetime import datetime

from sqlalchemy import Column, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import DateTime, Field, SQLModel, func


class EquityLedger(SQLModel, table=True):
    __tablename__ = "equity_ledger"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    )
    user_id: uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
    )
    change_type: str = Field(sa_column=Column(String(48), nullable=False, index=True))
    amount_delta: float = Field(default=0.0, sa_column=Column(Numeric(10, 2), nullable=False, default=0.0))
    frozen_delta: float = Field(default=0.0, sa_column=Column(Numeric(10, 2), nullable=False, default=0.0))
    total_income_delta: float = Field(default=0.0, sa_column=Column(Numeric(10, 2), nullable=False, default=0.0))
    total_withdrawn_delta: float = Field(default=0.0, sa_column=Column(Numeric(10, 2), nullable=False, default=0.0))
    balance_after: float = Field(default=0.0, sa_column=Column(Numeric(10, 2), nullable=False, default=0.0))
    frozen_balance_after: float = Field(default=0.0, sa_column=Column(Numeric(10, 2), nullable=False, default=0.0))
    total_income_after: float = Field(default=0.0, sa_column=Column(Numeric(10, 2), nullable=False, default=0.0))
    total_withdrawn_after: float = Field(default=0.0, sa_column=Column(Numeric(10, 2), nullable=False, default=0.0))
    related_type: str = Field(default="", sa_column=Column(String(64), nullable=False, server_default="", index=True))
    related_id: str = Field(default="", sa_column=Column(String(128), nullable=False, server_default="", index=True))
    idempotency_key: str = Field(sa_column=Column(String(160), nullable=False, unique=True, index=True))
    remark: str = Field(default="", sa_column=Column(String(512), nullable=False, server_default=""))
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True),
    )
