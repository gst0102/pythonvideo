"""ensure points ledger idempotency unique constraint

Revision ID: 012_points_ledger_idempotency_unique
Revises: 011_netdisk_repairs
Create Date: 2026-06-12
"""

from typing import Sequence, Union

from alembic import op


revision: str = "012_points_ledger_idempotency_unique"
down_revision: Union[str, None] = "011_netdisk_repairs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM points_ledger
                GROUP BY idempotency_key
                HAVING COUNT(*) > 1
            ) THEN
                RAISE EXCEPTION 'duplicate points_ledger.idempotency_key rows exist';
            END IF;

            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conrelid = 'points_ledger'::regclass
                  AND conname = 'uq_points_ledger_idempotency_key'
            ) THEN
                ALTER TABLE points_ledger
                ADD CONSTRAINT uq_points_ledger_idempotency_key UNIQUE (idempotency_key);
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE points_ledger
        DROP CONSTRAINT IF EXISTS uq_points_ledger_idempotency_key;
        """
    )
