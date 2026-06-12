"""netdisk risk records and audit config

Revision ID: 013_netdisk_risk_records
Revises: 012_points_ledger_idempotency_unique
Create Date: 2026-06-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "013_netdisk_risk_records"
down_revision: Union[str, None] = "012_points_ledger_idempotency_unique"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "netdisk_risk_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("related_type", sa.String(length=64), nullable=False),
        sa.Column("related_id", sa.String(length=128), nullable=False),
        sa.Column("reason", sa.String(length=64), nullable=False),
        sa.Column("points_due", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("points_collected", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("idempotency_key", name="uq_netdisk_risk_records_idempotency_key"),
    )
    op.create_index("ix_netdisk_risk_records_user_id", "netdisk_risk_records", ["user_id"])
    op.create_index("ix_netdisk_risk_records_related_type", "netdisk_risk_records", ["related_type"])
    op.create_index("ix_netdisk_risk_records_related_id", "netdisk_risk_records", ["related_id"])
    op.create_index("ix_netdisk_risk_records_reason", "netdisk_risk_records", ["reason"])
    op.create_index("ix_netdisk_risk_records_status", "netdisk_risk_records", ["status"])
    op.create_index("ix_netdisk_risk_records_created_at", "netdisk_risk_records", ["created_at"])

    op.execute(
        """
        INSERT INTO system_configs (type, config_data, created_at, updated_at)
        VALUES (
            'netdisk_audit_config',
            '{"upload_reward_points":5,"repair_reward_points":5,"report_hide_threshold":3,"invalid_penalty_multiplier":1,"auto_hide_on_report":true}'::jsonb,
            now(),
            now()
        )
        ON CONFLICT (type) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM system_configs WHERE type = 'netdisk_audit_config'")
    op.drop_index("ix_netdisk_risk_records_created_at", table_name="netdisk_risk_records")
    op.drop_index("ix_netdisk_risk_records_status", table_name="netdisk_risk_records")
    op.drop_index("ix_netdisk_risk_records_reason", table_name="netdisk_risk_records")
    op.drop_index("ix_netdisk_risk_records_related_id", table_name="netdisk_risk_records")
    op.drop_index("ix_netdisk_risk_records_related_type", table_name="netdisk_risk_records")
    op.drop_index("ix_netdisk_risk_records_user_id", table_name="netdisk_risk_records")
    op.drop_table("netdisk_risk_records")
