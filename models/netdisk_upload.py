"""Netdisk user upload submission model."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Column, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import DateTime, Field, SQLModel, func


class NetdiskUpload(SQLModel, table=True):
    __tablename__ = "netdisk_uploads"

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
    request_id: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("netdisk_requests.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )
    title: str = Field(sa_column=Column(String(120), nullable=False, index=True))
    category: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    pan: str = Field(sa_column=Column(String(32), nullable=False, index=True))
    link: str = Field(sa_column=Column(String(500), nullable=False))
    extract_code: str = Field(default="", sa_column=Column(String(64), nullable=False, server_default=""))
    unzip_code: str = Field(default="", sa_column=Column(String(64), nullable=False, server_default=""))
    description: str = Field(default="", sa_column=Column(Text, nullable=False, server_default=""))
    status: str = Field(default="pending", sa_column=Column(String(32), nullable=False, server_default="pending", index=True))
    reward_points: int = Field(default=5, sa_column=Column(BigInteger, nullable=False, server_default="5"))
    reward_released_points: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    valid_days_rewarded: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    accepted_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    audit_note: str = Field(default="系统正在校验链接有效性和内容匹配度。", sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), index=True),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )
