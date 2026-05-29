"""
系统配置表 — system_configs

对应原云开发集合: manger-data
迁移逻辑来源: cloudfunctions/admin-api/index.js + src/services/config.ts

核心业务:
  - 使用 PostgreSQL JSONB 列存储灵活的键值配置
  - 避免为每种配置类型创建单独的表
  - 支持动态扩展，无需变更表结构

配置类型:
  - vip_settings        — VIP 套餐配置
  - withdrawal_config   — 提现规则配置
  - service_settings    — 客服配置
  - platform_settings   — 平台配置
  - commission_settings — 佣金规则
  - banner_settings     — Banner 广告配置
"""

import uuid
from datetime import datetime
from typing import Any, Dict

from sqlmodel import Column, DateTime, Field, SQLModel, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB


class SystemConfig(SQLModel, table=True):
    __tablename__ = "system_configs"

    # ── 主键 ──
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    )

    # ── 配置类型 ──
    type: str = Field(
        sa_column=Column(String(50), unique=True, nullable=False, index=True),
        description="配置类型: vip_settings / withdrawal_config / ...",
    )

    # ── 配置数据（JSONB 灵活存储） ──
    config_data: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, default={}),
        description="JSON 格式的配置内容",
    )

    # ── 时间 ──
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )
