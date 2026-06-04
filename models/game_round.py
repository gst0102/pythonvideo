"""Stage 2 game round model."""

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Column, Date, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import DateTime, Field, SQLModel, func


class GameRound(SQLModel, table=True):
    __tablename__ = "game_rounds"

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
    round_id: str = Field(sa_column=Column(String(128), nullable=False, unique=True))
    game_code: str = Field(sa_column=Column(String(64), nullable=False))
    result: str = Field(sa_column=Column(String(32), nullable=False))
    base_points: int = Field(default=0)
    bonus_points: int = Field(default=0)
    total_points: int = Field(default=0)
    ad_event_id: Optional[str] = Field(default=None, sa_column=Column(String(128), nullable=True))
    status: str = Field(default="completed", sa_column=Column(String(32), nullable=False, server_default="completed"))
    ledger_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column(UUID(as_uuid=True), nullable=True))
    played_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )
