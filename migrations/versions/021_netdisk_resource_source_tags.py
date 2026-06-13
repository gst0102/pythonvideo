"""netdisk resource source tags and normalized title

Revision ID: 021_netdisk_resource_source_tags
Revises: 020_kdocs_xunlei_netdisk_links
Create Date: 2026-06-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "021_netdisk_resource_source_tags"
down_revision: Union[str, None] = "020_kdocs_xunlei_netdisk_links"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("netdisk_resources", sa.Column("tags", sa.Text(), nullable=False, server_default="[]"))
    op.add_column("netdisk_resources", sa.Column("source_type", sa.String(length=32), nullable=False, server_default="seed"))
    op.add_column("netdisk_resources", sa.Column("source_ref", sa.String(length=180), nullable=False, server_default=""))
    op.add_column("netdisk_resources", sa.Column("normalized_title", sa.String(length=180), nullable=False, server_default=""))
    op.create_index("ix_netdisk_resources_source_type", "netdisk_resources", ["source_type"])
    op.create_index("ix_netdisk_resources_source_ref", "netdisk_resources", ["source_ref"])
    op.create_index("ix_netdisk_resources_normalized_title", "netdisk_resources", ["normalized_title"])


def downgrade() -> None:
    op.drop_index("ix_netdisk_resources_normalized_title", table_name="netdisk_resources")
    op.drop_index("ix_netdisk_resources_source_ref", table_name="netdisk_resources")
    op.drop_index("ix_netdisk_resources_source_type", table_name="netdisk_resources")
    op.drop_column("netdisk_resources", "normalized_title")
    op.drop_column("netdisk_resources", "source_ref")
    op.drop_column("netdisk_resources", "source_type")
    op.drop_column("netdisk_resources", "tags")
