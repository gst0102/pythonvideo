"""创建番剧资源表 + 用户订阅表

Revision ID: 003
Revises: 002
Create Date: 2026-05-29

新增:
  - anime_resources    — 同步自外部数据源的番剧/电影/4K 资源
  - user_subscriptions — 用户订阅关系（替代 users.anime_subscriptions JSON 列）

URL 去重设计:
  - baidu_url 部分唯一索引（NULL 不冲突）
  - quark_url 部分唯一索引（NULL 不冲突）
  - 同步时按 URL 匹配 upsert，相同 URL 的新数据覆盖旧数据
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 anime_resources 和 user_subscriptions 表"""

    # ── 1. anime_resources 表 ─────────────────────────────────
    op.create_table(
        "anime_resources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("anime_id", sa.String(100), nullable=False, index=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("category", sa.String(20), nullable=False, server_default="anime", index=True),
        sa.Column("quality", sa.String(20), nullable=True),
        sa.Column("episode", sa.String(100), nullable=True),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("baidu_url", sa.Text(), nullable=True),
        sa.Column("baidu_password", sa.String(20), nullable=True),
        sa.Column("quark_url", sa.Text(), nullable=True),
        sa.Column("source_update_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # URL 去重：部分唯一索引（仅约束非 NULL 非空值）
    op.create_index(
        "uq_anime_baidu_url",
        "anime_resources",
        ["baidu_url"],
        unique=True,
        postgresql_where=sa.text("baidu_url IS NOT NULL AND baidu_url != ''"),
    )
    op.create_index(
        "uq_anime_quark_url",
        "anime_resources",
        ["quark_url"],
        unique=True,
        postgresql_where=sa.text("quark_url IS NOT NULL AND quark_url != ''"),
    )

    # ── 2. user_subscriptions 表 ──────────────────────────────
    op.create_table(
        "user_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("anime_id", sa.String(100), nullable=False, index=True),
        sa.Column("is_reminded", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("last_episode", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # 唯一约束：每人每番剧只能订阅一次
    op.create_unique_constraint(
        "uq_user_anime", "user_subscriptions", ["user_id", "anime_id"]
    )

    # 外键
    op.create_foreign_key(
        "fk_sub_user_id", "user_subscriptions", "users",
        ["user_id"], ["id"], ondelete="CASCADE",
    )


def downgrade() -> None:
    """回滚：删除两张新表"""
    op.drop_table("user_subscriptions")
    op.drop_table("anime_resources")
