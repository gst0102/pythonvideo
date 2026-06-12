"""Netdisk approved resource model."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Column, String, Text
from sqlmodel import DateTime, Field, SQLModel, func


class NetdiskResource(SQLModel, table=True):
    __tablename__ = "netdisk_resources"

    id: str = Field(sa_column=Column(String(64), primary_key=True))
    title: str = Field(sa_column=Column(String(120), nullable=False, index=True))
    category: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    pan: str = Field(sa_column=Column(String(32), nullable=False, index=True))
    level: str = Field(default="normal", sa_column=Column(String(32), nullable=False, server_default="normal", index=True))
    cost_points: int = Field(default=5, sa_column=Column(BigInteger, nullable=False, server_default="5"))
    downloads: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    favorites: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    description: str = Field(default="", sa_column=Column(Text, nullable=False, server_default=""))
    link: str = Field(sa_column=Column(String(500), nullable=False))
    extract_code: str = Field(default="", sa_column=Column(String(64), nullable=False, server_default=""))
    unzip_code: str = Field(default="", sa_column=Column(String(64), nullable=False, server_default=""))
    source_upload_id: str = Field(default="", sa_column=Column(String(64), nullable=False, server_default="", index=True))
    is_active: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, server_default="true", index=True))
    verified_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), index=True),
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), index=True),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )
