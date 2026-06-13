"""netdisk collected resource candidates

Revision ID: 022_netdisk_collected_resources
Revises: 021_netdisk_resource_source_tags
Create Date: 2026-06-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "022_netdisk_collected_resources"
down_revision: Union[str, None] = "021_netdisk_resource_source_tags"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "netdisk_collected_resources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("pan", sa.String(length=32), nullable=False),
        sa.Column("link", sa.Text(), nullable=False),
        sa.Column("extract_code", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("tags", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("normalized_title", sa.String(length=180), nullable=False, server_default=""),
        sa.Column("source_type", sa.String(length=32), nullable=False, server_default="linuxdo"),
        sa.Column("source_ref", sa.String(length=180), nullable=False, server_default=""),
        sa.Column("source_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("confidence", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("duplicate_status", sa.String(length=32), nullable=False, server_default="none"),
        sa.Column("ingest_action", sa.String(length=32), nullable=False, server_default="review_required"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("error", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for column in [
        "title",
        "category",
        "pan",
        "normalized_title",
        "source_type",
        "source_ref",
        "duplicate_status",
        "ingest_action",
        "status",
        "created_at",
    ]:
        op.create_index(f"ix_netdisk_collected_resources_{column}", "netdisk_collected_resources", [column])


def downgrade() -> None:
    for column in [
        "created_at",
        "status",
        "ingest_action",
        "duplicate_status",
        "source_ref",
        "source_type",
        "normalized_title",
        "pan",
        "category",
        "title",
    ]:
        op.drop_index(f"ix_netdisk_collected_resources_{column}", table_name="netdisk_collected_resources")
    op.drop_table("netdisk_collected_resources")
