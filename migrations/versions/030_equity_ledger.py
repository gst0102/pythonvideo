"""equity ledger

Revision ID: 030_equity_ledger
Revises: 029_commission_order_inviter_unique
Create Date: 2026-06-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "030_equity_ledger"
down_revision: Union[str, None] = "029_commission_order_inviter_unique"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("equity_ledger"):
        return

    op.create_table(
        "equity_ledger",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("change_type", sa.String(length=48), nullable=False),
        sa.Column("amount_delta", sa.Numeric(10, 2), nullable=False, server_default="0.00"),
        sa.Column("frozen_delta", sa.Numeric(10, 2), nullable=False, server_default="0.00"),
        sa.Column("total_income_delta", sa.Numeric(10, 2), nullable=False, server_default="0.00"),
        sa.Column("total_withdrawn_delta", sa.Numeric(10, 2), nullable=False, server_default="0.00"),
        sa.Column("balance_after", sa.Numeric(10, 2), nullable=False, server_default="0.00"),
        sa.Column("frozen_balance_after", sa.Numeric(10, 2), nullable=False, server_default="0.00"),
        sa.Column("total_income_after", sa.Numeric(10, 2), nullable=False, server_default="0.00"),
        sa.Column("total_withdrawn_after", sa.Numeric(10, 2), nullable=False, server_default="0.00"),
        sa.Column("related_type", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("related_id", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("remark", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("idempotency_key", name="uq_equity_ledger_idempotency_key"),
    )
    for column in ["user_id", "change_type", "related_type", "related_id", "idempotency_key", "created_at"]:
        op.create_index(f"ix_equity_ledger_{column}", "equity_ledger", [column])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("equity_ledger"):
        return
    for column in ["created_at", "idempotency_key", "related_id", "related_type", "change_type", "user_id"]:
        op.drop_index(f"ix_equity_ledger_{column}", table_name="equity_ledger")
    op.drop_table("equity_ledger")
