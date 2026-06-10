"""invite relation trace table

Revision ID: 009_invite_relations
Revises: 008_stage2_game_settlement
Create Date: 2026-06-11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "009_invite_relations"
down_revision: Union[str, None] = "008_stage2_game_settlement"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "invite_relations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("inviter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invitee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invite_code", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="login"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["inviter_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invitee_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("invitee_id", name="uq_invite_relations_invitee_id"),
    )
    op.create_index("ix_invite_relations_inviter_id", "invite_relations", ["inviter_id"])
    op.create_index("ix_invite_relations_invitee_id", "invite_relations", ["invitee_id"])
    op.create_index("ix_invite_relations_invite_code", "invite_relations", ["invite_code"])
    op.create_index("ix_invite_relations_created_at", "invite_relations", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_invite_relations_created_at", table_name="invite_relations")
    op.drop_index("ix_invite_relations_invite_code", table_name="invite_relations")
    op.drop_index("ix_invite_relations_invitee_id", table_name="invite_relations")
    op.drop_index("ix_invite_relations_inviter_id", table_name="invite_relations")
    op.drop_table("invite_relations")
