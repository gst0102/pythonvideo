"""netdisk upload resource source and notifications

Revision ID: 016_netdisk_upload_resource_notifications
Revises: 015_netdisk_quality_ops
Create Date: 2026-06-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "016_netdisk_upload_resource_notifications"
down_revision: Union[str, None] = "015_netdisk_quality_ops"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "netdisk_resources",
        sa.Column("source_upload_id", sa.String(length=64), nullable=False, server_default=""),
    )
    op.create_index("ix_netdisk_resources_source_upload_id", "netdisk_resources", ["source_upload_id"])

    op.create_table(
        "netdisk_user_notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("notice_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("related_type", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("related_id", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="unread"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_netdisk_user_notifications_user_id", "netdisk_user_notifications", ["user_id"])
    op.create_index("ix_netdisk_user_notifications_notice_type", "netdisk_user_notifications", ["notice_type"])
    op.create_index("ix_netdisk_user_notifications_related_type", "netdisk_user_notifications", ["related_type"])
    op.create_index("ix_netdisk_user_notifications_related_id", "netdisk_user_notifications", ["related_id"])
    op.create_index("ix_netdisk_user_notifications_status", "netdisk_user_notifications", ["status"])
    op.create_index("ix_netdisk_user_notifications_created_at", "netdisk_user_notifications", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_netdisk_user_notifications_created_at", table_name="netdisk_user_notifications")
    op.drop_index("ix_netdisk_user_notifications_status", table_name="netdisk_user_notifications")
    op.drop_index("ix_netdisk_user_notifications_related_id", table_name="netdisk_user_notifications")
    op.drop_index("ix_netdisk_user_notifications_related_type", table_name="netdisk_user_notifications")
    op.drop_index("ix_netdisk_user_notifications_notice_type", table_name="netdisk_user_notifications")
    op.drop_index("ix_netdisk_user_notifications_user_id", table_name="netdisk_user_notifications")
    op.drop_table("netdisk_user_notifications")
    op.drop_index("ix_netdisk_resources_source_upload_id", table_name="netdisk_resources")
    op.drop_column("netdisk_resources", "source_upload_id")
