"""netdisk audit logs

Revision ID: 014_netdisk_audit_logs
Revises: 013_netdisk_risk_records
Create Date: 2026-06-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "014_netdisk_audit_logs"
down_revision: Union[str, None] = "013_netdisk_risk_records"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "netdisk_audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("admin_name", sa.String(length=64), nullable=False, server_default="admin"),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=False),
        sa.Column("target_title", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("result", sa.String(length=32), nullable=False, server_default="success"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_netdisk_audit_logs_admin_name", "netdisk_audit_logs", ["admin_name"])
    op.create_index("ix_netdisk_audit_logs_action", "netdisk_audit_logs", ["action"])
    op.create_index("ix_netdisk_audit_logs_target_type", "netdisk_audit_logs", ["target_type"])
    op.create_index("ix_netdisk_audit_logs_target_id", "netdisk_audit_logs", ["target_id"])
    op.create_index("ix_netdisk_audit_logs_result", "netdisk_audit_logs", ["result"])
    op.create_index("ix_netdisk_audit_logs_created_at", "netdisk_audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_netdisk_audit_logs_created_at", table_name="netdisk_audit_logs")
    op.drop_index("ix_netdisk_audit_logs_result", table_name="netdisk_audit_logs")
    op.drop_index("ix_netdisk_audit_logs_target_id", table_name="netdisk_audit_logs")
    op.drop_index("ix_netdisk_audit_logs_target_type", table_name="netdisk_audit_logs")
    op.drop_index("ix_netdisk_audit_logs_action", table_name="netdisk_audit_logs")
    op.drop_index("ix_netdisk_audit_logs_admin_name", table_name="netdisk_audit_logs")
    op.drop_table("netdisk_audit_logs")
