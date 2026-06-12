"""netdisk quality operations

Revision ID: 015_netdisk_quality_ops
Revises: 014_netdisk_audit_logs
Create Date: 2026-06-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "015_netdisk_quality_ops"
down_revision: Union[str, None] = "014_netdisk_audit_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "netdisk_quality_alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("resource_id", sa.String(length=64), nullable=False),
        sa.Column("alert_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("title", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("message", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("handled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("resource_id", "alert_type", name="uq_netdisk_quality_alert_resource_type"),
    )
    op.create_index("ix_netdisk_quality_alerts_resource_id", "netdisk_quality_alerts", ["resource_id"])
    op.create_index("ix_netdisk_quality_alerts_alert_type", "netdisk_quality_alerts", ["alert_type"])
    op.create_index("ix_netdisk_quality_alerts_status", "netdisk_quality_alerts", ["status"])
    op.create_index("ix_netdisk_quality_alerts_last_triggered_at", "netdisk_quality_alerts", ["last_triggered_at"])
    op.create_index("ix_netdisk_quality_alerts_created_at", "netdisk_quality_alerts", ["created_at"])

    op.create_table(
        "netdisk_quality_daily_stats",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("resource_id", sa.String(length=64), nullable=False),
        sa.Column("stat_date", sa.Date(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("category", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("pan", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("reports", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("restores", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("unlocks", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("unlock_users", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("score", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("resource_id", "stat_date", name="uq_netdisk_quality_daily_resource_date"),
    )
    op.create_index("ix_netdisk_quality_daily_stats_resource_id", "netdisk_quality_daily_stats", ["resource_id"])
    op.create_index("ix_netdisk_quality_daily_stats_stat_date", "netdisk_quality_daily_stats", ["stat_date"])
    op.create_index("ix_netdisk_quality_daily_stats_is_active", "netdisk_quality_daily_stats", ["is_active"])
    op.create_index("ix_netdisk_quality_daily_stats_created_at", "netdisk_quality_daily_stats", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_netdisk_quality_daily_stats_created_at", table_name="netdisk_quality_daily_stats")
    op.drop_index("ix_netdisk_quality_daily_stats_is_active", table_name="netdisk_quality_daily_stats")
    op.drop_index("ix_netdisk_quality_daily_stats_stat_date", table_name="netdisk_quality_daily_stats")
    op.drop_index("ix_netdisk_quality_daily_stats_resource_id", table_name="netdisk_quality_daily_stats")
    op.drop_table("netdisk_quality_daily_stats")
    op.drop_index("ix_netdisk_quality_alerts_created_at", table_name="netdisk_quality_alerts")
    op.drop_index("ix_netdisk_quality_alerts_last_triggered_at", table_name="netdisk_quality_alerts")
    op.drop_index("ix_netdisk_quality_alerts_status", table_name="netdisk_quality_alerts")
    op.drop_index("ix_netdisk_quality_alerts_alert_type", table_name="netdisk_quality_alerts")
    op.drop_index("ix_netdisk_quality_alerts_resource_id", table_name="netdisk_quality_alerts")
    op.drop_table("netdisk_quality_alerts")
