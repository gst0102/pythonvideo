"""Chat message model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import DateTime, Field, Relationship, SQLModel, func

if TYPE_CHECKING:
    from models.user import User


class ChatMessage(SQLModel, table=True):
    __tablename__ = "chat_messages"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    )
    user_id: uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True),
    )
    sender: str = Field(sa_column=Column(String(10), nullable=False))
    content: str = Field(sa_column=Column(Text, nullable=False))
    msg_type: str = Field(default="text", sa_column=Column(String(10), default="text"))
    is_read: bool = Field(default=False, sa_column=Column(Boolean, default=False))
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), index=True),
    )

    user: "User" = Relationship(back_populates="chat_messages")
