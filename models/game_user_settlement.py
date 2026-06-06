"""Stage 2 per-user game settlement detail model."""

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, Column, Date, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import DateTime, Field, SQLModel, func


class GameUserSettlement(SQLModel, table=True):
    __tablename__ = "game_user_settlements"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    )
    batch_id: uuid.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("game_settlement_batches.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    settlement_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    user_id: uuid.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    membership_level: str = Field(sa_column=Column(String(32), nullable=False))
    factor_value: float = Field(default=0.0, sa_column=Column(Numeric(6, 4), nullable=False, server_default="0"))
    estimated_points: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    settled_points: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    adjustment_points: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    round_count: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    ad_pv: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    valid_clicks: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    status: str = Field(default="settled", sa_column=Column(String(32), nullable=False, server_default="settled"))
    note: str | None = Field(default=None, sa_column=Column(String(512), nullable=True))
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )
