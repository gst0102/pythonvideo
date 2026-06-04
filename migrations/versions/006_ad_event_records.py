"""add ad event records

Revision ID: 006_ad_event_records
Revises: 005_ad_reward_records
Create Date: 2026-06-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "006_ad_event_records"
down_revision = "005_ad_reward_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ad_event_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_id", sa.String(length=80), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("openid", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("module", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("section", sa.String(length=60), nullable=False, server_default=""),
        sa.Column("scene", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("ad_unit_id", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("event_type", sa.String(length=20), nullable=False, server_default="request"),
        sa.Column("is_completed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("reward_points", sa.Numeric(10, 3), nullable=False, server_default="0.000"),
        sa.Column("reward_amount", sa.Numeric(10, 3), nullable=False, server_default="0.000"),
        sa.Column("date_key", sa.String(length=10), nullable=False, server_default=""),
        sa.Column("week_key", sa.String(length=8), nullable=False, server_default=""),
        sa.Column("month_key", sa.String(length=7), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    for col in [
        "event_id",
        "user_id",
        "openid",
        "module",
        "section",
        "scene",
        "ad_unit_id",
        "event_type",
        "is_completed",
        "date_key",
        "week_key",
        "month_key",
        "created_at",
    ]:
        op.create_index(f"ix_ad_event_records_{col}", "ad_event_records", [col])


def downgrade() -> None:
    for col in [
        "created_at",
        "month_key",
        "week_key",
        "date_key",
        "is_completed",
        "event_type",
        "ad_unit_id",
        "scene",
        "section",
        "module",
        "openid",
        "user_id",
        "event_id",
    ]:
        op.drop_index(f"ix_ad_event_records_{col}", table_name="ad_event_records")
    op.drop_table("ad_event_records")
