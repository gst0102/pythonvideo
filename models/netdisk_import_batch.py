"""Netdisk collected resource file import batch model."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Column, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import DateTime, Field, SQLModel, func


class NetdiskImportBatch(SQLModel, table=True):
    __tablename__ = "netdisk_import_batches"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    )
    filename: str = Field(default="", sa_column=Column(String(180), nullable=False, server_default=""))
    source_type: str = Field(default="manual", sa_column=Column(String(32), nullable=False, server_default="manual", index=True))
    operator_role: str = Field(default="", sa_column=Column(String(32), nullable=False, server_default=""))
    status: str = Field(default="success", sa_column=Column(String(32), nullable=False, server_default="success", index=True))
    total_rows: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    synced_count: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    auto_published_count: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    review_required_count: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    skipped_count: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    failed_count: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    failed_rows: str = Field(default="[]", sa_column=Column(Text, nullable=False, server_default="[]"))
    error: str = Field(default="", sa_column=Column(Text, nullable=False, server_default=""))
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), index=True),
    )
