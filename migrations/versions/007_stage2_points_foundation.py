"""stage2 points foundation draft

Revision ID: 007_stage2_points_foundation
Revises: 006_ad_event_records
Create Date: 2026-06-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "007_stage2_points_foundation"
down_revision: Union[str, None] = "006_ad_event_records"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Stage 2 foundation is additive only.
    # It introduces points-first accounting tables while keeping all current
    # cash-first online tables unchanged.

    op.create_table(
        "user_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("total_points", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("withdrawable_points", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("frozen_points", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("consumable_points", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("consumed_points", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("withdrawn_points", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("locked_withdraw_points", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("version", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", name="uq_user_accounts_user_id"),
    )
    op.create_index("ix_user_accounts_user_id", "user_accounts", ["user_id"])

    op.create_table(
        "points_ledger",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("change_type", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("availability", sa.String(length=32), nullable=False),
        sa.Column("points_delta", sa.BigInteger(), nullable=False),
        sa.Column("balance_withdrawable_after", sa.BigInteger(), nullable=False),
        sa.Column("balance_frozen_after", sa.BigInteger(), nullable=False),
        sa.Column("balance_consumable_after", sa.BigInteger(), nullable=False),
        sa.Column("related_type", sa.String(length=64), nullable=True),
        sa.Column("related_id", sa.String(length=128), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("remark", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["user_accounts.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("idempotency_key", name="uq_points_ledger_idempotency_key"),
    )
    op.create_index("ix_points_ledger_user_id", "points_ledger", ["user_id"])
    op.create_index("ix_points_ledger_account_id", "points_ledger", ["account_id"])
    op.create_index("ix_points_ledger_source", "points_ledger", ["source"])
    op.create_index("ix_points_ledger_created_at", "points_ledger", ["created_at"])
    op.create_index("ix_points_ledger_related", "points_ledger", ["related_type", "related_id"])

    op.create_table(
        "checkin_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("checkin_date", sa.Date(), nullable=False),
        sa.Column("base_points", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("bonus_points", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_points", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("continuous_days", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_member_at_checkin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("ad_bonus_used", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("ad_event_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "checkin_date", name="uq_checkin_records_user_date"),
    )
    op.create_index("ix_checkin_records_user_id", "checkin_records", ["user_id"])
    op.create_index("ix_checkin_records_checkin_date", "checkin_records", ["checkin_date"])

    op.create_table(
        "game_rounds",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("round_id", sa.String(length=128), nullable=False),
        sa.Column("game_code", sa.String(length=64), nullable=False),
        sa.Column("result", sa.String(length=32), nullable=False),
        sa.Column("base_points", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("bonus_points", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_points", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("ad_event_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="completed"),
        sa.Column("ledger_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("played_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("round_id", name="uq_game_rounds_round_id"),
    )
    op.create_index("ix_game_rounds_user_id", "game_rounds", ["user_id"])
    op.create_index("ix_game_rounds_played_date", "game_rounds", ["played_date"])
    op.create_index("ix_game_rounds_user_game_created", "game_rounds", ["user_id", "game_code", "created_at"])

    op.create_table(
        "daily_task_stats",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stat_date", sa.Date(), nullable=False),
        sa.Column("today_points", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("game_tasks_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("game_tasks_limit", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("checkin_done", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("checkin_bonus_done", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "stat_date", name="uq_daily_task_stats_user_date"),
    )
    op.create_index("ix_daily_task_stats_user_id", "daily_task_stats", ["user_id"])
    op.create_index("ix_daily_task_stats_stat_date", "daily_task_stats", ["stat_date"])

    _seed_stage2_config_placeholders()


def downgrade() -> None:
    _delete_stage2_config_placeholders()

    op.drop_index("ix_daily_task_stats_stat_date", table_name="daily_task_stats")
    op.drop_index("ix_daily_task_stats_user_id", table_name="daily_task_stats")
    op.drop_table("daily_task_stats")

    op.drop_index("ix_game_rounds_user_game_created", table_name="game_rounds")
    op.drop_index("ix_game_rounds_played_date", table_name="game_rounds")
    op.drop_index("ix_game_rounds_user_id", table_name="game_rounds")
    op.drop_table("game_rounds")

    op.drop_index("ix_checkin_records_checkin_date", table_name="checkin_records")
    op.drop_index("ix_checkin_records_user_id", table_name="checkin_records")
    op.drop_table("checkin_records")

    op.drop_index("ix_points_ledger_related", table_name="points_ledger")
    op.drop_index("ix_points_ledger_created_at", table_name="points_ledger")
    op.drop_index("ix_points_ledger_source", table_name="points_ledger")
    op.drop_index("ix_points_ledger_account_id", table_name="points_ledger")
    op.drop_index("ix_points_ledger_user_id", table_name="points_ledger")
    op.drop_table("points_ledger")

    op.drop_index("ix_user_accounts_user_id", table_name="user_accounts")
    op.drop_table("user_accounts")


def _seed_stage2_config_placeholders() -> None:
    system_configs = sa.table(
        "system_configs",
        sa.column("type", sa.String),
        sa.column("config_data", postgresql.JSONB),
        sa.column("updated_at", sa.DateTime),
    )

    configs = [
        (
            "stage2_points_config",
            {
                "exchange_rate": 100,
                "display_unit": "积分",
                "checkin_base_points_normal": 1,
                "checkin_base_points_member": 2,
                "checkin_ad_bonus_min": 1,
                "checkin_ad_bonus_max": 3,
                "game_base_points_min": 1,
                "game_base_points_max": 2,
                "game_ad_multiplier": 2,
            },
        ),
        (
            "stage2_task_config",
            {
                "daily_game_task_limit_normal": 10,
                "daily_game_task_limit_member_month": 100,
                "daily_game_task_limit_member_quarter": 150,
                "daily_game_task_limit_member_year": 200,
            },
        ),
        (
            "stage2_member_config",
            {
                "plans": [
                    {"code": "month", "name": "月卡", "price": 19.9, "duration_days": 31, "gift_points": 199},
                    {"code": "quarter", "name": "季卡", "price": 49.9, "duration_days": 93, "gift_points": 599},
                    {"code": "year", "name": "年卡", "price": 99.9, "duration_days": 365, "gift_points": 1299},
                ]
            },
        ),
        (
            "stage2_invite_config",
            {
                "invite_register_points": 10,
                "hd_unlock_count": 3,
                "fourk_unlock_count": 5,
                "level1_member_rebate_rate": 0.5,
                "level2_member_rebate_rate": 0.05,
                "rebate_freeze_days": 7,
            },
        ),
        (
            "stage2_withdraw_config",
            {
                "first_withdraw_min_amount": 1,
                "normal_withdraw_min_amount": 5,
                "member_withdraw_min_amount": 1,
                "normal_fee_rate": 0.1,
                "member_fee_rate": 0.05,
                "manual_review": True,
            },
        ),
        (
            "stage2_media_rights_config",
            {
                "free_user_need_interaction_before_copy": True,
                "member_daily_free_copy_limit": 20,
                "points_cost_copy_without_ad": 2,
            },
        ),
        (
            "stage2_video_config",
            {
                "free_user_need_interaction_before_download": True,
                "member_daily_free_download_limit": 20,
                "parse_failed_actions": ["retry", "feedback", "go_tasks", "go_media"],
            },
        ),
    ]

    bind = op.get_bind()
    for config_type, config_data in configs:
        exists = bind.execute(
            sa.text("SELECT 1 FROM system_configs WHERE type = :type LIMIT 1"),
            {"type": config_type},
        ).first()
        if exists:
            continue
        op.execute(
            system_configs.insert().values(
                type=config_type,
                config_data=config_data,
                updated_at=sa.func.now(),
            )
        )


def _delete_stage2_config_placeholders() -> None:
    for config_type in [
        "stage2_video_config",
        "stage2_media_rights_config",
        "stage2_withdraw_config",
        "stage2_invite_config",
        "stage2_member_config",
        "stage2_task_config",
        "stage2_points_config",
    ]:
        op.execute(
            sa.text("DELETE FROM system_configs WHERE type = :type"),
            {"type": config_type},
        )
