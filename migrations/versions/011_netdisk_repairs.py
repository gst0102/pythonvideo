"""netdisk repair submissions

Revision ID: 011_netdisk_repairs
Revises: 010_netdisk_resources
Create Date: 2026-06-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "011_netdisk_repairs"
down_revision: Union[str, None] = "010_netdisk_resources"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "netdisk_repairs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resource_id", sa.String(length=64), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("resource_title", sa.String(length=120), nullable=False),
        sa.Column("pan", sa.String(length=32), nullable=False),
        sa.Column("link", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("extract_code", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("unzip_code", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("reward_points", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("audit_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_netdisk_repairs_user_id", "netdisk_repairs", ["user_id"])
    op.create_index("ix_netdisk_repairs_resource_id", "netdisk_repairs", ["resource_id"])
    op.create_index("ix_netdisk_repairs_mode", "netdisk_repairs", ["mode"])
    op.create_index("ix_netdisk_repairs_pan", "netdisk_repairs", ["pan"])
    op.create_index("ix_netdisk_repairs_status", "netdisk_repairs", ["status"])
    op.create_index("ix_netdisk_repairs_created_at", "netdisk_repairs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_netdisk_repairs_created_at", table_name="netdisk_repairs")
    op.drop_index("ix_netdisk_repairs_status", table_name="netdisk_repairs")
    op.drop_index("ix_netdisk_repairs_pan", table_name="netdisk_repairs")
    op.drop_index("ix_netdisk_repairs_mode", table_name="netdisk_repairs")
    op.drop_index("ix_netdisk_repairs_resource_id", table_name="netdisk_repairs")
    op.drop_index("ix_netdisk_repairs_user_id", table_name="netdisk_repairs")
    op.drop_table("netdisk_repairs")
