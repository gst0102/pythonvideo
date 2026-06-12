"""Netdisk resource quality alert state model."""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import DateTime, Field, SQLModel, func


class NetdiskQualityAlert(SQLModel, table=True):
    __tablename__ = "netdisk_quality_alerts"
    __table_args__ = (
        UniqueConstraint("resource_id", "alert_type", name="uq_netdisk_quality_alert_resource_type"),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    )
    resource_id: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    alert_type: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    status: str = Field(default="open", sa_column=Column(String(32), nullable=False, server_default="open", index=True))
    title: str = Field(default="", sa_column=Column(String(200), nullable=False, server_default=""))
    message: str = Field(default="", sa_column=Column(String(300), nullable=False, server_default=""))
    note: str = Field(default="", sa_column=Column(Text, nullable=False, server_default=""))
    last_triggered_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), index=True),
    )
    handled_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), index=True),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )
