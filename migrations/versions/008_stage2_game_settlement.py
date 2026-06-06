"""stage2 game settlement tables

Revision ID: 008_stage2_game_settlement
Revises: 007_stage2_points_foundation
Create Date: 2026-06-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "008_stage2_game_settlement"
down_revision: Union[str, None] = "007_stage2_points_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "game_settlement_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("settlement_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("ecpm_value", sa.Numeric(10, 4), nullable=True),
        sa.Column("ecpm_source", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("ad_pv", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("valid_clicks", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_revenue", sa.Numeric(12, 4), nullable=False, server_default="0"),
        sa.Column("settled_user_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_estimated_points", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_settled_points", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_adjustment_points", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("note", sa.String(length=512), nullable=True),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("settlement_date", name="uq_game_settlement_batches_date"),
    )
    op.create_index("ix_game_settlement_batches_date", "game_settlement_batches", ["settlement_date"])

    op.create_table(
        "game_user_settlements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("settlement_date", sa.Date(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("membership_level", sa.String(length=32), nullable=False),
        sa.Column("factor_value", sa.Numeric(6, 4), nullable=False, server_default="0"),
        sa.Column("estimated_points", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("settled_points", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("adjustment_points", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("round_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("ad_pv", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("valid_clicks", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="settled"),
        sa.Column("note", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["batch_id"], ["game_settlement_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "settlement_date", name="uq_game_user_settlements_user_date"),
    )
    op.create_index("ix_game_user_settlements_batch_id", "game_user_settlements", ["batch_id"])
    op.create_index("ix_game_user_settlements_date", "game_user_settlements", ["settlement_date"])
    op.create_index("ix_game_user_settlements_user_id", "game_user_settlements", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_game_user_settlements_user_id", table_name="game_user_settlements")
    op.drop_index("ix_game_user_settlements_date", table_name="game_user_settlements")
    op.drop_index("ix_game_user_settlements_batch_id", table_name="game_user_settlements")
    op.drop_table("game_user_settlements")

    op.drop_index("ix_game_settlement_batches_date", table_name="game_settlement_batches")
    op.drop_table("game_settlement_batches")
