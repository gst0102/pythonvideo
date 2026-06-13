"""netdisk feedback tickets

Revision ID: 023_netdisk_feedback_tickets
Revises: 022_netdisk_collected_resources
Create Date: 2026-06-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "023_netdisk_feedback_tickets"
down_revision: Union[str, None] = "022_netdisk_collected_resources"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "netdisk_feedbacks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("feedback_type", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("contact", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("auto_reply", sa.Text(), nullable=False, server_default=""),
        sa.Column("admin_reply", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for column in ["user_id", "feedback_type", "status", "created_at"]:
        op.create_index(f"ix_netdisk_feedbacks_{column}", "netdisk_feedbacks", [column])


def downgrade() -> None:
    for column in ["created_at", "status", "feedback_type", "user_id"]:
        op.drop_index(f"ix_netdisk_feedbacks_{column}", table_name="netdisk_feedbacks")
    op.drop_table("netdisk_feedbacks")
