"""
数据库引擎和会话管理

使用 SQLModel + asyncpg 连接 PostgreSQL。
采用 FastAPI 依赖注入模式，每个请求获取一个独立会话。
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(BACKEND_DIR / ".env", override=False)

# ── 数据库连接 ─────────────────────────────────────────────
def _build_database_url() -> str:
    if os.getenv("DB_HOST") or os.getenv("DB_NAME"):
        user = os.getenv("DB_USER", "postgres")
        password = quote_plus(os.getenv("DB_PASSWORD", "postgres"))
        host = os.getenv("DB_HOST", "localhost")
        port = os.getenv("DB_PORT", "5432")
        name = os.getenv("DB_NAME", "video_app")
        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"

    configured = os.getenv("DATABASE_URL")
    if configured:
        return configured

    user = os.getenv("DB_USER", "postgres")
    password = quote_plus(os.getenv("DB_PASSWORD", "postgres"))
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "video_app")
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"


DATABASE_URL = _build_database_url()

# 默认启用 echo 便于调试（生产环境通过 .env 关闭）
ECHO_SQL = os.getenv("DB_ECHO", "false").lower() == "true"

# SSL 模式（本地开发用 disable，生产用 prefer）
DB_SSL_MODE = os.getenv("DB_SSL_MODE", "disable")
_connect_args = {}
if DB_SSL_MODE == "disable":
    _connect_args["ssl"] = False

engine = create_async_engine(
    DATABASE_URL,
    echo=ECHO_SQL,
    future=True,
    connect_args=_connect_args if _connect_args else {},
)

# 会话工厂
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """创建所有表（开发环境用，生产环境用 Alembic 迁移）"""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def close_db() -> None:
    """释放数据库连接池"""
    await engine.dispose()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖注入：每个请求获取独立数据库会话"""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_session_ctx():
    """上下文管理器版本，用于非 FastAPI 场景（脚本、测试等）"""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
