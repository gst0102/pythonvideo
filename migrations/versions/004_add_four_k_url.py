"""anime_resources 表新增 four_k_url 字段

Revision ID: 004
Revises: 003
Create Date: 2026-05-29

变更:
  - 新增 four_k_url 列 (TEXT, nullable)
  - 新增 four_k_url 部分唯一索引（NULL 不冲突）
  - 数据源从外部 API 改为金山文档逆向爬取
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "anime_resources",
        sa.Column("four_k_url", sa.Text(), nullable=True),
    )

    op.create_index(
        "uq_anime_four_k_url",
        "anime_resources",
        ["four_k_url"],
        unique=True,
        postgresql_where=sa.text("four_k_url IS NOT NULL AND four_k_url != ''"),
    )


def downgrade() -> None:
    op.drop_index("uq_anime_four_k_url", table_name="anime_resources")
    op.drop_column("anime_resources", "four_k_url")