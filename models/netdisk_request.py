"""Netdisk resource request model."""

import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import BigInteger, Column, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import DateTime, Field, SQLModel, func


class NetdiskRequest(SQLModel, table=True):
    __tablename__ = "netdisk_requests"

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
    title: str = Field(sa_column=Column(String(120), nullable=False, index=True))
    pans: str = Field(sa_column=Column(String(120), nullable=False))
    category: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    bounty_points: int = Field(default=5, sa_column=Column(BigInteger, nullable=False, server_default="5"))
    note: str = Field(default="", sa_column=Column(Text, nullable=False, server_default=""))
    status: str = Field(default="open", sa_column=Column(String(32), nullable=False, server_default="open", index=True))
    bounty_status: str = Field(default="frozen", sa_column=Column(String(32), nullable=False, server_default="frozen", index=True))
    accepted_upload_id: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=Column(UUID(as_uuid=True), ForeignKey("netdisk_uploads.id", ondelete="SET NULL"), nullable=True, index=True),
    )
    submissions_count: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    deadline_text: str = Field(default="3天后", sa_column=Column(String(32), nullable=False, server_default="3天后"))
    expires_at: datetime = Field(
        default_factory=lambda: datetime.utcnow() + timedelta(days=3),
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True),
    )
    accepted_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    closed_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), index=True),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )
