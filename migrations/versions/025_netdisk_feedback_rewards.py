"""netdisk feedback rewards

Revision ID: 025_netdisk_feedback_rewards
Revises: 024_netdisk_import_batches
Create Date: 2026-06-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "025_netdisk_feedback_rewards"
down_revision: Union[str, None] = "024_netdisk_import_batches"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("netdisk_feedbacks", sa.Column("reward_points", sa.BigInteger(), nullable=False, server_default="0"))
    op.add_column("netdisk_feedbacks", sa.Column("reward_ledger_id", postgresql.UUID(as_uuid=True), nullable=True))


def downgrade() -> None:
    op.drop_column("netdisk_feedbacks", "reward_ledger_id")
    op.drop_column("netdisk_feedbacks", "reward_points")
