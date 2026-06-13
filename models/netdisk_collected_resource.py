"""System-collected netdisk resource candidate model."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Column, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import DateTime, Field, SQLModel, func


class NetdiskCollectedResource(SQLModel, table=True):
    __tablename__ = "netdisk_collected_resources"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    )
    title: str = Field(sa_column=Column(String(180), nullable=False, index=True))
    category: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    pan: str = Field(sa_column=Column(String(32), nullable=False, index=True))
    link: str = Field(sa_column=Column(Text, nullable=False))
    extract_code: str = Field(default="", sa_column=Column(String(64), nullable=False, server_default=""))
    tags: str = Field(default="[]", sa_column=Column(Text, nullable=False, server_default="[]"))
    normalized_title: str = Field(default="", sa_column=Column(String(180), nullable=False, server_default="", index=True))
    source_type: str = Field(default="linuxdo", sa_column=Column(String(32), nullable=False, server_default="linuxdo", index=True))
    source_ref: str = Field(default="", sa_column=Column(String(180), nullable=False, server_default="", index=True))
    source_url: str = Field(default="", sa_column=Column(Text, nullable=False, server_default=""))
    confidence: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    duplicate_status: str = Field(default="none", sa_column=Column(String(32), nullable=False, server_default="none", index=True))
    ingest_action: str = Field(default="review_required", sa_column=Column(String(32), nullable=False, server_default="review_required", index=True))
    status: str = Field(default="pending", sa_column=Column(String(32), nullable=False, server_default="pending", index=True))
    error: str = Field(default="", sa_column=Column(Text, nullable=False, server_default=""))
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), index=True),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )
