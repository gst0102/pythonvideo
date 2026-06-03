"""Order model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import DateTime, Field, Relationship, SQLModel, func

if TYPE_CHECKING:
    from models.user import User


class Order(SQLModel, table=True):
    __tablename__ = "orders"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    )
    user_id: uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True),
    )
    amount: float = Field(sa_column=Column(Numeric(10, 2), nullable=False))
    period: str = Field(sa_column=Column(String(20), nullable=False))
    duration_days: int = Field(default=30)
    description: str = Field(default="", sa_column=Column(String(200), default=""))
    out_trade_no: str = Field(sa_column=Column(String(64), unique=True, nullable=False, index=True))
    transaction_id: Optional[str] = Field(default=None, sa_column=Column(String(64), nullable=True))
    status: str = Field(default="pending", sa_column=Column(String(20), default="pending"))
    paid_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )

    user: "User" = Relationship(back_populates="orders")
