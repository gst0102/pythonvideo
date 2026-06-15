"""ensure commission order inviter uniqueness

Revision ID: 029_commission_order_inviter_unique
Revises: 028_netdisk_unlock_hidden
Create Date: 2026-06-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "029_commission_order_inviter_unique"
down_revision: Union[str, None] = "028_netdisk_unlock_hidden"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CONSTRAINT_NAME = "uq_commission_order_inviter_level"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("commission_records"):
        return

    existing_constraints = {
        item.get("name")
        for item in inspector.get_unique_constraints("commission_records")
    }
    if CONSTRAINT_NAME in existing_constraints:
        return

    duplicates = bind.execute(sa.text(
        """
        SELECT user_id, from_user_id, order_id, level, COUNT(*) AS duplicate_count
        FROM commission_records
        WHERE order_id IS NOT NULL
        GROUP BY user_id, from_user_id, order_id, level
        HAVING COUNT(*) > 1
        LIMIT 1
        """
    )).first()
    if duplicates:
        raise RuntimeError(
            "duplicate commission_records rows exist; clean them before adding uq_commission_order_inviter_level"
        )

    op.create_unique_constraint(
        CONSTRAINT_NAME,
        "commission_records",
        ["user_id", "from_user_id", "order_id", "level"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("commission_records"):
        return
    existing_constraints = {
        item.get("name")
        for item in inspector.get_unique_constraints("commission_records")
    }
    if CONSTRAINT_NAME in existing_constraints:
        op.drop_constraint(CONSTRAINT_NAME, "commission_records", type_="unique")
