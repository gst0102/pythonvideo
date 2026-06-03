"""Ad reward records."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Column, DateTime, Field, Relationship, SQLModel, func

if TYPE_CHECKING:
    from models.user import User


class AdRewardRecord(SQLModel, table=True):
    __tablename__ = "ad_reward_records"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    )
    event_id: str = Field(
        sa_column=Column(String(64), unique=True, nullable=False, index=True),
    )
    user_id: uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True),
    )
    scene: str = Field(
        default="game",
        sa_column=Column(String(30), nullable=False, index=True),
    )
    ad_unit_id: str = Field(
        default="",
        sa_column=Column(String(80), default=""),
    )
    is_ended: bool = Field(
        default=False,
        sa_column=Column(Boolean, default=False, nullable=False),
    )
    reward_amount: float = Field(
        default=0.00,
        sa_column=Column(Numeric(10, 3), default=0.00, nullable=False),
    )
    credited: bool = Field(
        default=False,
        sa_column=Column(Boolean, default=False, nullable=False),
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )

    user: Optional["User"] = Relationship()
