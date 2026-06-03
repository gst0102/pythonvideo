"""add ad reward records

Revision ID: 005_ad_reward_records
Revises: 004_add_four_k_url
Create Date: 2026-06-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "005_ad_reward_records"
down_revision = "004_add_four_k_url"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ad_reward_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scene", sa.String(length=30), nullable=False),
        sa.Column("ad_unit_id", sa.String(length=80), nullable=True),
        sa.Column("is_ended", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("reward_amount", sa.Numeric(10, 3), nullable=False, server_default="0.000"),
        sa.Column("credited", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("event_id", name="uq_ad_reward_event_id"),
    )
    op.create_index("ix_ad_reward_records_event_id", "ad_reward_records", ["event_id"])
    op.create_index("ix_ad_reward_records_user_id", "ad_reward_records", ["user_id"])
    op.create_index("ix_ad_reward_records_scene", "ad_reward_records", ["scene"])


def downgrade() -> None:
    op.drop_index("ix_ad_reward_records_scene", table_name="ad_reward_records")
    op.drop_index("ix_ad_reward_records_user_id", table_name="ad_reward_records")
    op.drop_index("ix_ad_reward_records_event_id", table_name="ad_reward_records")
    op.drop_table("ad_reward_records")
