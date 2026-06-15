"""Netdisk resource update subscription."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import DateTime, Field, SQLModel, UniqueConstraint, func


class NetdiskResourceSubscription(SQLModel, table=True):
    __tablename__ = "netdisk_resource_subscriptions"
    __table_args__ = (UniqueConstraint("user_id", "resource_id", name="uq_netdisk_resource_subscription_user_resource"),)

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    )
    user_id: uuid.UUID = Field(sa_column=Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True))
    resource_id: str = Field(sa_column=Column(String(64), ForeignKey("netdisk_resources.id", ondelete="CASCADE"), nullable=False, index=True))
    status: str = Field(default="active", sa_column=Column(String(32), nullable=False, server_default="active", index=True))
    wx_subscribe_status: str = Field(default="unknown", sa_column=Column(String(32), nullable=False, server_default="unknown", index=True))
    template_id: str = Field(default="", sa_column=Column(String(128), nullable=False, server_default=""))
    subscribe_count: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    last_subscribed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    last_pushed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    is_active: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, server_default="true", index=True))
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_column=Column(DateTime(timezone=True), server_default=func.now(), index=True))
    updated_at: datetime = Field(default_factory=datetime.utcnow, sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()))
