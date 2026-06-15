"""Netdisk resource subscription push attempt log."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Column, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import DateTime, Field, SQLModel, func


class NetdiskResourceSubscriptionPushLog(SQLModel, table=True):
    __tablename__ = "netdisk_resource_subscription_push_logs"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    )
    subscription_id: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(UUID(as_uuid=True), ForeignKey("netdisk_resource_subscriptions.id", ondelete="SET NULL"), nullable=True, index=True),
    )
    user_id: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
    )
    resource_id: str = Field(sa_column=Column(String(64), ForeignKey("netdisk_resources.id", ondelete="CASCADE"), nullable=False, index=True))
    template_id: str = Field(default="", sa_column=Column(String(128), nullable=False, server_default=""))
    status: str = Field(default="skipped", sa_column=Column(String(32), nullable=False, server_default="skipped", index=True))
    errcode: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    errmsg: str = Field(default="", sa_column=Column(String(300), nullable=False, server_default=""))
    response_body: str = Field(default="", sa_column=Column(Text, nullable=False, server_default=""))
    title_snapshot: str = Field(default="", sa_column=Column(String(180), nullable=False, server_default=""))
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_column=Column(DateTime(timezone=True), server_default=func.now(), index=True))
