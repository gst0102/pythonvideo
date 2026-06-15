"""Persistent run history for crawler worker tasks."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Column, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import DateTime, Field, SQLModel, func


class NetdiskCrawlerRun(SQLModel, table=True):
    __tablename__ = "netdisk_crawler_runs"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    )
    crawler_key: str = Field(sa_column=Column(String(32), nullable=False, index=True))
    trigger_source: str = Field(default="manual", sa_column=Column(String(32), nullable=False, server_default="manual", index=True))
    status: str = Field(default="success", sa_column=Column(String(32), nullable=False, server_default="success", index=True))
    started_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True),
    )
    finished_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True),
    )
    duration_seconds: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    synced_count: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    inactive_count: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    auto_published_count: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    review_required_count: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    skipped_count: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    failed_count: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    netdisk_inactive_count: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    consecutive_failures: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    result_payload: str = Field(default="{}", sa_column=Column(Text, nullable=False, server_default="{}"))
    error_text: str = Field(default="", sa_column=Column(Text, nullable=False, server_default=""))
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True),
    )
