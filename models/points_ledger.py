"""Stage 2 points ledger model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import DateTime, Field, Relationship, SQLModel, func

if TYPE_CHECKING:
    from models.user_account import UserAccount


class PointsLedger(SQLModel, table=True):
    __tablename__ = "points_ledger"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    )
    user_id: uuid.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    account_id: uuid.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("user_accounts.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    change_type: str = Field(sa_column=Column(String(32), nullable=False))
    source: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    availability: str = Field(sa_column=Column(String(32), nullable=False))
    points_delta: int = Field(default=0, sa_column=Column(BigInteger, nullable=False))
    balance_withdrawable_after: int = Field(default=0, sa_column=Column(BigInteger, nullable=False))
    balance_frozen_after: int = Field(default=0, sa_column=Column(BigInteger, nullable=False))
    balance_consumable_after: int = Field(default=0, sa_column=Column(BigInteger, nullable=False))
    related_type: Optional[str] = Field(default=None, sa_column=Column(String(64), nullable=True))
    related_id: Optional[str] = Field(default=None, sa_column=Column(String(128), nullable=True))
    idempotency_key: str = Field(
        sa_column=Column(String(128), nullable=False, unique=True, index=True),
    )
    remark: Optional[str] = Field(default=None, sa_column=Column(String(512), nullable=True))
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), index=True),
    )

    account: Optional["UserAccount"] = Relationship(back_populates="points_ledger")
