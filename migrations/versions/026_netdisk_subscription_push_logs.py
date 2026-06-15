"""netdisk subscription push logs

Revision ID: 026_netdisk_subscription_push_logs
Revises: 018_netdisk_resource_subscriptions, 025_netdisk_feedback_rewards
Create Date: 2026-06-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "026_netdisk_subscription_push_logs"
down_revision: Union[str, Sequence[str], None] = ("018_netdisk_resource_subscriptions", "025_netdisk_feedback_rewards")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("netdisk_resource_subscription_push_logs"):
        return

    op.create_table(
        "netdisk_resource_subscription_push_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resource_id", sa.String(length=64), nullable=False),
        sa.Column("template_id", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="skipped"),
        sa.Column("errcode", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("errmsg", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("response_body", sa.Text(), nullable=False, server_default=""),
        sa.Column("title_snapshot", sa.String(length=180), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["subscription_id"], ["netdisk_resource_subscriptions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["resource_id"], ["netdisk_resources.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_netdisk_resource_subscription_push_logs_subscription_id", "netdisk_resource_subscription_push_logs", ["subscription_id"])
    op.create_index("ix_netdisk_resource_subscription_push_logs_user_id", "netdisk_resource_subscription_push_logs", ["user_id"])
    op.create_index("ix_netdisk_resource_subscription_push_logs_resource_id", "netdisk_resource_subscription_push_logs", ["resource_id"])
    op.create_index("ix_netdisk_resource_subscription_push_logs_status", "netdisk_resource_subscription_push_logs", ["status"])
    op.create_index("ix_netdisk_resource_subscription_push_logs_created_at", "netdisk_resource_subscription_push_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_netdisk_resource_subscription_push_logs_created_at", table_name="netdisk_resource_subscription_push_logs")
    op.drop_index("ix_netdisk_resource_subscription_push_logs_status", table_name="netdisk_resource_subscription_push_logs")
    op.drop_index("ix_netdisk_resource_subscription_push_logs_resource_id", table_name="netdisk_resource_subscription_push_logs")
    op.drop_index("ix_netdisk_resource_subscription_push_logs_user_id", table_name="netdisk_resource_subscription_push_logs")
    op.drop_index("ix_netdisk_resource_subscription_push_logs_subscription_id", table_name="netdisk_resource_subscription_push_logs")
    op.drop_table("netdisk_resource_subscription_push_logs")
