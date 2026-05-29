"""
Alembic 迁移环境配置

支持异步 PostgreSQL 连接，自动发现 models/ 下的所有 SQLModel 表。
"""

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel

# 加载环境变量
load_dotenv()

# Alembic Config 对象
config = context.config

# 日志配置
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── 导入所有模型（确保 SQLModel.metadata 包含所有表） ──
# 必须导入所有模型类，Alembic 才能通过 metadata 发现它们
import models  # noqa: E402, F401

# 目标 metadata
target_metadata = SQLModel.metadata

# 数据库 URL（优先用环境变量）
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:w12345@127.0.0.1:5432/agent",
)


def run_migrations_offline() -> None:
    """
    离线模式：生成 SQL 脚本而不连接数据库
    用法: alembic upgrade head --sql
    """
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    """在线模式：连接数据库执行迁移"""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """异步在线迁移"""
    connectable = create_async_engine(DATABASE_URL, poolclass=pool.NullPool)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
