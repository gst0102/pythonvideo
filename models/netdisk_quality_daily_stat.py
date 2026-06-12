"""Netdisk resource daily quality statistic model."""

from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Column, Date, String, UniqueConstraint
from sqlmodel import DateTime, Field, SQLModel, func


class NetdiskQualityDailyStat(SQLModel, table=True):
    __tablename__ = "netdisk_quality_daily_stats"
    __table_args__ = (
        UniqueConstraint("resource_id", "stat_date", name="uq_netdisk_quality_daily_resource_date"),
    )

    id: int | None = Field(default=None, primary_key=True)
    resource_id: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    stat_date: date = Field(sa_column=Column(Date(), nullable=False, index=True))
    title: str = Field(default="", sa_column=Column(String(200), nullable=False, server_default=""))
    category: str = Field(default="", sa_column=Column(String(64), nullable=False, server_default=""))
    pan: str = Field(default="", sa_column=Column(String(32), nullable=False, server_default=""))
    is_active: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, server_default="true", index=True))
    reports: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    restores: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    unlocks: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    unlock_users: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    score: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), index=True),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )
