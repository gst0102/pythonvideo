"""Ad event records for rewarded ad analytics."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Column, DateTime, Field, Relationship, SQLModel, func

if TYPE_CHECKING:
    from models.user import User


class AdEventRecord(SQLModel, table=True):
    __tablename__ = "ad_event_records"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    )
    event_id: str = Field(
        sa_column=Column(String(80), nullable=False, index=True),
    )
    user_id: uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True),
    )
    openid: str = Field(
        default="",
        sa_column=Column(String(128), default="", nullable=False, index=True),
    )
    module: str = Field(
        default="",
        sa_column=Column(String(40), default="", nullable=False, index=True),
    )
    section: str = Field(
        default="",
        sa_column=Column(String(60), default="", nullable=False, index=True),
    )
    scene: str = Field(
        default="",
        sa_column=Column(String(40), default="", nullable=False, index=True),
    )
    ad_unit_id: str = Field(
        default="",
        sa_column=Column(String(100), default="", nullable=False, index=True),
    )
    event_type: str = Field(
        default="request",
        sa_column=Column(String(20), default="request", nullable=False, index=True),
    )
    is_completed: bool = Field(
        default=False,
        sa_column=Column(Boolean, default=False, nullable=False, index=True),
    )
    reward_points: float = Field(
        default=0.0,
        sa_column=Column(Numeric(10, 3), default=0.0, nullable=False),
    )
    reward_amount: float = Field(
        default=0.0,
        sa_column=Column(Numeric(10, 3), default=0.0, nullable=False),
    )
    date_key: str = Field(
        default="",
        sa_column=Column(String(10), default="", nullable=False, index=True),
    )
    week_key: str = Field(
        default="",
        sa_column=Column(String(8), default="", nullable=False, index=True),
    )
    month_key: str = Field(
        default="",
        sa_column=Column(String(7), default="", nullable=False, index=True),
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), index=True),
    )

    user: Optional["User"] = Relationship()
