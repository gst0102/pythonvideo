"""Netdisk repair/report submission model."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Column, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import DateTime, Field, SQLModel, func


class NetdiskRepair(SQLModel, table=True):
    __tablename__ = "netdisk_repairs"

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
    resource_id: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    mode: str = Field(sa_column=Column(String(32), nullable=False, index=True))
    resource_title: str = Field(sa_column=Column(String(120), nullable=False))
    pan: str = Field(sa_column=Column(String(32), nullable=False, index=True))
    link: str = Field(default="", sa_column=Column(String(500), nullable=False, server_default=""))
    extract_code: str = Field(default="", sa_column=Column(String(64), nullable=False, server_default=""))
    unzip_code: str = Field(default="", sa_column=Column(String(64), nullable=False, server_default=""))
    note: str = Field(default="", sa_column=Column(Text, nullable=False, server_default=""))
    status: str = Field(default="pending", sa_column=Column(String(32), nullable=False, server_default="pending", index=True))
    reward_points: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    audit_note: str = Field(default="", sa_column=Column(Text, nullable=False, server_default=""))
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), index=True),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )
