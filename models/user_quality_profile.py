"""User resource quality profile model."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import DateTime, Field, SQLModel, func


class UserQualityProfile(SQLModel, table=True):
    __tablename__ = "user_quality_profiles"

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
    credit_score: int = Field(default=100, sa_column=Column(BigInteger, nullable=False, server_default="100"))
    contribution_score: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    short_invalid_count: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    upload_restricted_until: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    risk_level: str = Field(default="normal", sa_column=Column(String(32), nullable=False, server_default="normal", index=True))
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )
