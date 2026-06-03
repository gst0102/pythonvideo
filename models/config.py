"""System config model."""

import uuid
from datetime import datetime
from typing import Any, Dict

from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlmodel import DateTime, Field, SQLModel, func


class SystemConfig(SQLModel, table=True):
    __tablename__ = "system_configs"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    )
    type: str = Field(sa_column=Column(String(50), unique=True, nullable=False, index=True))
    config_data: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False, default={}))
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )
