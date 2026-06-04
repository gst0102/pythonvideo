"""Stage 2 daily task aggregation model."""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Column, Date, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import DateTime, Field, SQLModel, UniqueConstraint, func


class DailyTaskStat(SQLModel, table=True):
    __tablename__ = "daily_task_stats"
    __table_args__ = (
        UniqueConstraint("user_id", "stat_date", name="uq_daily_task_stats_user_date"),
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
    stat_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    today_points: int = Field(default=0)
    game_tasks_used: int = Field(default=0, sa_column=Column(Integer, nullable=False, server_default="0"))
    game_tasks_limit: int = Field(default=0, sa_column=Column(Integer, nullable=False, server_default="0"))
    checkin_done: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default="false"),
    )
    checkin_bonus_done: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default="false"),
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )
