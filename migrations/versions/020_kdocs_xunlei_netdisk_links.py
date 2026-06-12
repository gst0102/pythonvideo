"""kdocs xunlei and long netdisk links

Revision ID: 020_kdocs_xunlei_netdisk_links
Revises: 019_netdisk_request_bounty_loop
Create Date: 2026-06-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "020_kdocs_xunlei_netdisk_links"
down_revision: Union[str, None] = "019_netdisk_request_bounty_loop"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("anime_resources", sa.Column("xunlei_url", sa.Text(), nullable=True))
    op.create_index(
        "uq_anime_xunlei_url",
        "anime_resources",
        ["xunlei_url"],
        unique=True,
        postgresql_where=sa.text("xunlei_url IS NOT NULL AND xunlei_url != ''"),
    )
    op.alter_column(
        "netdisk_resources",
        "link",
        existing_type=sa.String(length=500),
        type_=sa.Text(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "netdisk_resources",
        "link",
        existing_type=sa.Text(),
        type_=sa.String(length=500),
        existing_nullable=False,
    )
    op.drop_index("uq_anime_xunlei_url", table_name="anime_resources")
    op.drop_column("anime_resources", "xunlei_url")
