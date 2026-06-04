"""Stage 2 points account model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import DateTime, Field, Relationship, SQLModel, func

if TYPE_CHECKING:
    from models.points_ledger import PointsLedger


class UserAccount(SQLModel, table=True):
    __tablename__ = "user_accounts"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    )
    user_id: uuid.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
            index=True,
        )
    )
    total_points: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    withdrawable_points: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    frozen_points: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    consumable_points: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    consumed_points: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    withdrawn_points: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    locked_withdraw_points: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    version: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )

    points_ledger: list["PointsLedger"] = Relationship(back_populates="account")
