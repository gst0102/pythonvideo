"""netdisk unlock hidden records

Revision ID: 028_netdisk_unlock_hidden
Revises: 027_netdisk_crawler_runs
Create Date: 2026-06-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "028_netdisk_unlock_hidden"
down_revision: Union[str, None] = "027_netdisk_crawler_runs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("netdisk_unlock_hidden"):
        return

    op.create_table(
        "netdisk_unlock_hidden",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ledger_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("points_ledger.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "ledger_id", name="uq_netdisk_unlock_hidden_user_ledger"),
    )
    op.create_index("ix_netdisk_unlock_hidden_user_id", "netdisk_unlock_hidden", ["user_id"])
    op.create_index("ix_netdisk_unlock_hidden_ledger_id", "netdisk_unlock_hidden", ["ledger_id"])
    op.create_index("ix_netdisk_unlock_hidden_created_at", "netdisk_unlock_hidden", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_netdisk_unlock_hidden_created_at", table_name="netdisk_unlock_hidden")
    op.drop_index("ix_netdisk_unlock_hidden_ledger_id", table_name="netdisk_unlock_hidden")
    op.drop_index("ix_netdisk_unlock_hidden_user_id", table_name="netdisk_unlock_hidden")
    op.drop_table("netdisk_unlock_hidden")
