"""Stage 2 daily check-in model."""

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Column, Date, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import DateTime, Field, SQLModel, UniqueConstraint, func


class CheckinRecord(SQLModel, table=True):
    __tablename__ = "checkin_records"
    __table_args__ = (
        UniqueConstraint("user_id", "checkin_date", name="uq_checkin_records_user_date"),
    )

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
    checkin_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    base_points: int = Field(default=0)
    bonus_points: int = Field(default=0)
    total_points: int = Field(default=0)
    continuous_days: int = Field(default=1, sa_column=Column(Integer, nullable=False, server_default="1"))
    is_member_at_checkin: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default="false"),
    )
    ad_bonus_used: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default="false"),
    )
    ad_event_id: Optional[str] = Field(default=None, sa_column=Column(String(128), nullable=True))
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )
