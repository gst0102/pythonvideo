"""Stage 2 daily game settlement batch model."""

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, Column, Date, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import DateTime, Field, SQLModel, func


class GameSettlementBatch(SQLModel, table=True):
    __tablename__ = "game_settlement_batches"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    )
    settlement_date: date = Field(sa_column=Column(Date, nullable=False, unique=True, index=True))
    status: str = Field(default="draft", sa_column=Column(String(32), nullable=False, server_default="draft"))
    ecpm_value: float | None = Field(default=None, sa_column=Column(Numeric(10, 4), nullable=True))
    ecpm_source: str = Field(default="manual", sa_column=Column(String(32), nullable=False, server_default="manual"))
    ad_pv: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    valid_clicks: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    total_revenue: float = Field(default=0.0, sa_column=Column(Numeric(12, 4), nullable=False, server_default="0"))
    settled_user_count: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    total_estimated_points: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    total_settled_points: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    total_adjustment_points: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    note: str | None = Field(default=None, sa_column=Column(String(512), nullable=True))
    settled_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )
