"""Netdisk pending recovery/risk record model."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Column, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import DateTime, Field, SQLModel, func


class NetdiskRiskRecord(SQLModel, table=True):
    __tablename__ = "netdisk_risk_records"

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
    related_type: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    related_id: str = Field(sa_column=Column(String(128), nullable=False, index=True))
    reason: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    points_due: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    points_collected: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    status: str = Field(default="open", sa_column=Column(String(32), nullable=False, server_default="open", index=True))
    note: str = Field(default="", sa_column=Column(Text, nullable=False, server_default=""))
    idempotency_key: str = Field(sa_column=Column(String(128), nullable=False, unique=True, index=True))
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), index=True),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )
