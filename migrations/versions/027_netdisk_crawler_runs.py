"""netdisk crawler runs

Revision ID: 027_netdisk_crawler_runs
Revises: 026_netdisk_subscription_push_logs
Create Date: 2026-06-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "027_netdisk_crawler_runs"
down_revision: Union[str, None] = "026_netdisk_subscription_push_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("netdisk_crawler_runs"):
        return

    op.create_table(
        "netdisk_crawler_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("crawler_key", sa.String(length=32), nullable=False),
        sa.Column("trigger_source", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="success"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("duration_seconds", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("synced_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("inactive_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("auto_published_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("review_required_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("netdisk_inactive_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("consecutive_failures", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("result_payload", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("error_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    for column in ["crawler_key", "trigger_source", "status", "started_at", "finished_at", "created_at"]:
        op.create_index(f"ix_netdisk_crawler_runs_{column}", "netdisk_crawler_runs", [column])


def downgrade() -> None:
    for column in ["created_at", "finished_at", "started_at", "status", "trigger_source", "crawler_key"]:
        op.drop_index(f"ix_netdisk_crawler_runs_{column}", table_name="netdisk_crawler_runs")
    op.drop_table("netdisk_crawler_runs")
