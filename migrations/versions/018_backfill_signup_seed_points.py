"""backfill signup seed points for existing users

Revision ID: 018_backfill_signup_seed_points
Revises: 017_netdisk_points_quality_strategy
Create Date: 2026-06-13
"""

from typing import Sequence, Union

from alembic import op


revision: str = "018_backfill_signup_seed_points"
down_revision: Union[str, None] = "017_netdisk_points_quality_strategy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.exec_driver_sql(
        """
        INSERT INTO user_accounts (
            id,
            user_id,
            total_points,
            withdrawable_points,
            frozen_points,
            consumable_points,
            consumed_points,
            withdrawn_points,
            locked_withdraw_points,
            version,
            created_at,
            updated_at
        )
        SELECT
            (
                substr(md5('user_account:' || u.id::text), 1, 8) || '-' ||
                substr(md5('user_account:' || u.id::text), 9, 4) || '-' ||
                substr(md5('user_account:' || u.id::text), 13, 4) || '-' ||
                substr(md5('user_account:' || u.id::text), 17, 4) || '-' ||
                substr(md5('user_account:' || u.id::text), 21, 12)
            )::uuid,
            u.id,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            now(),
            now()
        FROM users u
        LEFT JOIN user_accounts a ON a.user_id = u.id
        WHERE a.id IS NULL;
        """
    )

    bind.exec_driver_sql(
        """
        WITH targets AS (
            SELECT
                u.id AS user_id,
                a.id AS account_id,
                a.withdrawable_points,
                a.frozen_points,
                a.consumable_points,
                ('signup_seed_points:' || u.id::text) AS idempotency_key
            FROM users u
            JOIN user_accounts a ON a.user_id = u.id
            LEFT JOIN points_ledger l
              ON l.idempotency_key = ('signup_seed_points:' || u.id::text)
            WHERE l.id IS NULL
        ),
        updated AS (
            UPDATE user_accounts a
            SET
                total_points = a.total_points + 100,
                consumable_points = a.consumable_points + 100,
                updated_at = now()
            FROM targets t
            WHERE a.id = t.account_id
            RETURNING
                t.user_id,
                t.account_id,
                t.withdrawable_points,
                t.frozen_points,
                t.consumable_points + 100 AS balance_consumable_after,
                t.idempotency_key
        )
        INSERT INTO points_ledger (
            id,
            user_id,
            account_id,
            change_type,
            source,
            availability,
            points_delta,
            balance_withdrawable_after,
            balance_frozen_after,
            balance_consumable_after,
            related_type,
            related_id,
            idempotency_key,
            remark,
            created_at
        )
        SELECT
            (
                substr(md5('ledger:' || u.idempotency_key), 1, 8) || '-' ||
                substr(md5('ledger:' || u.idempotency_key), 9, 4) || '-' ||
                substr(md5('ledger:' || u.idempotency_key), 13, 4) || '-' ||
                substr(md5('ledger:' || u.idempotency_key), 17, 4) || '-' ||
                substr(md5('ledger:' || u.idempotency_key), 21, 12)
            )::uuid,
            u.user_id,
            u.account_id,
            'signup_seed_points',
            'signup',
            'consumable',
            100,
            u.withdrawable_points,
            u.frozen_points,
            u.balance_consumable_after,
            'user',
            u.user_id::text,
            u.idempotency_key,
            '存量用户补发新用户注册赠送100积分',
            now()
        FROM updated u
        ON CONFLICT (idempotency_key) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.get_bind().exec_driver_sql(
        """
        WITH removed AS (
            DELETE FROM points_ledger
            WHERE change_type = 'signup_seed_points'
              AND source = 'signup'
              AND remark = '存量用户补发新用户注册赠送100积分'
            RETURNING account_id
        )
        UPDATE user_accounts a
        SET
            total_points = GREATEST(a.total_points - 100, 0),
            consumable_points = GREATEST(a.consumable_points - 100, 0),
            updated_at = now()
        FROM removed r
        WHERE a.id = r.account_id;
        """
    )
