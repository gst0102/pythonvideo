"""netdisk import batches

Revision ID: 024_netdisk_import_batches
Revises: 023_netdisk_feedback_tickets
Create Date: 2026-06-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "024_netdisk_import_batches"
down_revision: Union[str, None] = "023_netdisk_feedback_tickets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "netdisk_import_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("filename", sa.String(length=180), nullable=False, server_default=""),
        sa.Column("source_type", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("operator_role", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="success"),
        sa.Column("total_rows", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("synced_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("auto_published_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("review_required_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("failed_rows", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("error", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for column in ["source_type", "status", "created_at"]:
        op.create_index(f"ix_netdisk_import_batches_{column}", "netdisk_import_batches", [column])


def downgrade() -> None:
    for column in ["created_at", "status", "source_type"]:
        op.drop_index(f"ix_netdisk_import_batches_{column}", table_name="netdisk_import_batches")
    op.drop_table("netdisk_import_batches")
