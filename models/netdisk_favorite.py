"""Netdisk resource favorite model."""

import uuid
from datetime import datetime

from sqlalchemy import Column, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import DateTime, Field, SQLModel, func


class NetdiskFavorite(SQLModel, table=True):
    __tablename__ = "netdisk_favorites"
    __table_args__ = (
        UniqueConstraint("user_id", "resource_id", name="uq_netdisk_favorite_user_resource"),
    )

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
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), index=True),
    )
