"""Netdisk user-facing notification record."""

import uuid
from datetime import datetime

from sqlalchemy import Column, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import DateTime, Field, SQLModel, func


class NetdiskUserNotification(SQLModel, table=True):
    __tablename__ = "netdisk_user_notifications"

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
    notice_type: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    title: str = Field(default="", sa_column=Column(String(160), nullable=False, server_default=""))
    content: str = Field(default="", sa_column=Column(Text, nullable=False, server_default=""))
    related_type: str = Field(default="", sa_column=Column(String(64), nullable=False, server_default="", index=True))
    related_id: str = Field(default="", sa_column=Column(String(128), nullable=False, server_default="", index=True))
    status: str = Field(default="unread", sa_column=Column(String(32), nullable=False, server_default="unread", index=True))
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), index=True),
    )
