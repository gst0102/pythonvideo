"""netdisk approved resources

Revision ID: 010_netdisk_resources
Revises: 009_invite_relations
Create Date: 2026-06-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "010_netdisk_resources"
down_revision: Union[str, None] = "009_invite_relations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "netdisk_resources",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("pan", sa.String(length=32), nullable=False),
        sa.Column("level", sa.String(length=32), nullable=False, server_default="normal"),
        sa.Column("cost_points", sa.BigInteger(), nullable=False, server_default="5"),
        sa.Column("downloads", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("favorites", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("link", sa.String(length=500), nullable=False),
        sa.Column("extract_code", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("unzip_code", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("verified_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_netdisk_resources_title", "netdisk_resources", ["title"])
    op.create_index("ix_netdisk_resources_category", "netdisk_resources", ["category"])
    op.create_index("ix_netdisk_resources_pan", "netdisk_resources", ["pan"])
    op.create_index("ix_netdisk_resources_level", "netdisk_resources", ["level"])
    op.create_index("ix_netdisk_resources_is_active", "netdisk_resources", ["is_active"])
    op.create_index("ix_netdisk_resources_verified_at", "netdisk_resources", ["verified_at"])
    op.create_index("ix_netdisk_resources_created_at", "netdisk_resources", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_netdisk_resources_created_at", table_name="netdisk_resources")
    op.drop_index("ix_netdisk_resources_verified_at", table_name="netdisk_resources")
    op.drop_index("ix_netdisk_resources_is_active", table_name="netdisk_resources")
    op.drop_index("ix_netdisk_resources_level", table_name="netdisk_resources")
    op.drop_index("ix_netdisk_resources_pan", table_name="netdisk_resources")
    op.drop_index("ix_netdisk_resources_category", table_name="netdisk_resources")
    op.drop_index("ix_netdisk_resources_title", table_name="netdisk_resources")
    op.drop_table("netdisk_resources")
