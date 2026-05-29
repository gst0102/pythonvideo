"""添加番剧订阅字段

Revision ID: 002
Revises: 001
Create Date: 2026-05-29

添加:
  - users.anime_subscriptions (JSON) — 用户订阅的番剧ID列表
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "anime_subscriptions",
            postgresql.JSON(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "anime_subscriptions")
