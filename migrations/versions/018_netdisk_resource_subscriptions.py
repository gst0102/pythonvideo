"""netdisk resource subscriptions

Revision ID: 018_netdisk_resource_subscriptions
Revises: 017_netdisk_points_quality_strategy
Create Date: 2026-06-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "018_netdisk_resource_subscriptions"
down_revision: Union[str, None] = "017_netdisk_points_quality_strategy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("netdisk_resource_subscriptions"):
        return

    op.create_table(
        "netdisk_resource_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resource_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("wx_subscribe_status", sa.String(length=32), nullable=False, server_default="unknown"),
        sa.Column("template_id", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("subscribe_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("last_subscribed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_pushed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resource_id"], ["netdisk_resources.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "resource_id", name="uq_netdisk_resource_subscription_user_resource"),
    )
    op.create_index("ix_netdisk_resource_subscriptions_user_id", "netdisk_resource_subscriptions", ["user_id"])
    op.create_index("ix_netdisk_resource_subscriptions_resource_id", "netdisk_resource_subscriptions", ["resource_id"])
    op.create_index("ix_netdisk_resource_subscriptions_status", "netdisk_resource_subscriptions", ["status"])
    op.create_index("ix_netdisk_resource_subscriptions_wx_subscribe_status", "netdisk_resource_subscriptions", ["wx_subscribe_status"])
    op.create_index("ix_netdisk_resource_subscriptions_is_active", "netdisk_resource_subscriptions", ["is_active"])
    op.create_index("ix_netdisk_resource_subscriptions_created_at", "netdisk_resource_subscriptions", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_netdisk_resource_subscriptions_created_at", table_name="netdisk_resource_subscriptions")
    op.drop_index("ix_netdisk_resource_subscriptions_is_active", table_name="netdisk_resource_subscriptions")
    op.drop_index("ix_netdisk_resource_subscriptions_wx_subscribe_status", table_name="netdisk_resource_subscriptions")
    op.drop_index("ix_netdisk_resource_subscriptions_status", table_name="netdisk_resource_subscriptions")
    op.drop_index("ix_netdisk_resource_subscriptions_resource_id", table_name="netdisk_resource_subscriptions")
    op.drop_index("ix_netdisk_resource_subscriptions_user_id", table_name="netdisk_resource_subscriptions")
    op.drop_table("netdisk_resource_subscriptions")
