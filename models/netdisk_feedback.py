"""Netdisk feedback ticket model."""

import uuid
from datetime import datetime

from sqlalchemy import Column, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import DateTime, Field, SQLModel, func


class NetdiskFeedback(SQLModel, table=True):
    __tablename__ = "netdisk_feedbacks"

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
    feedback_type: str = Field(sa_column=Column(String(32), nullable=False, index=True))
    content: str = Field(sa_column=Column(Text, nullable=False))
    contact: str = Field(default="", sa_column=Column(String(120), nullable=False, server_default=""))
    status: str = Field(default="pending", sa_column=Column(String(32), nullable=False, server_default="pending", index=True))
    auto_reply: str = Field(default="", sa_column=Column(Text, nullable=False, server_default=""))
    admin_reply: str = Field(default="", sa_column=Column(Text, nullable=False, server_default=""))
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), index=True),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )
