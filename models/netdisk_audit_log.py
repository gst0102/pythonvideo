"""Netdisk admin audit operation log model."""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import DateTime, Field, SQLModel, func


class NetdiskAuditLog(SQLModel, table=True):
    __tablename__ = "netdisk_audit_logs"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    )
    admin_name: str = Field(default="admin", sa_column=Column(String(64), nullable=False, server_default="admin", index=True))
    action: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    target_type: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    target_id: str = Field(sa_column=Column(String(128), nullable=False, index=True))
    target_title: str = Field(default="", sa_column=Column(String(200), nullable=False, server_default=""))
    note: str = Field(default="", sa_column=Column(Text, nullable=False, server_default=""))
    result: str = Field(default="success", sa_column=Column(String(32), nullable=False, server_default="success", index=True))
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), index=True),
    )
