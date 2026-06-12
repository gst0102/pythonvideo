"""netdisk points quality strategy

Revision ID: 017_netdisk_points_quality_strategy
Revises: 016_netdisk_upload_resource_notifications
Create Date: 2026-06-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "017_netdisk_points_quality_strategy"
down_revision: Union[str, None] = "016_netdisk_upload_resource_notifications"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("netdisk_uploads"):
        op.create_table(
            "netdisk_uploads",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("title", sa.String(length=120), nullable=False),
            sa.Column("category", sa.String(length=64), nullable=False),
            sa.Column("pan", sa.String(length=32), nullable=False),
            sa.Column("link", sa.String(length=500), nullable=False),
            sa.Column("extract_code", sa.String(length=64), nullable=False, server_default=""),
            sa.Column("unzip_code", sa.String(length=64), nullable=False, server_default=""),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("reward_points", sa.BigInteger(), nullable=False, server_default="5"),
            sa.Column("reward_released_points", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("valid_days_rewarded", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("audit_note", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_netdisk_uploads_user_id", "netdisk_uploads", ["user_id"])
        op.create_index("ix_netdisk_uploads_title", "netdisk_uploads", ["title"])
        op.create_index("ix_netdisk_uploads_category", "netdisk_uploads", ["category"])
        op.create_index("ix_netdisk_uploads_pan", "netdisk_uploads", ["pan"])
        op.create_index("ix_netdisk_uploads_status", "netdisk_uploads", ["status"])
        op.create_index("ix_netdisk_uploads_created_at", "netdisk_uploads", ["created_at"])
    else:
        upload_columns = _columns(inspector, "netdisk_uploads")
        if "reward_released_points" not in upload_columns:
            op.add_column("netdisk_uploads", sa.Column("reward_released_points", sa.BigInteger(), nullable=False, server_default="0"))
        if "valid_days_rewarded" not in upload_columns:
            op.add_column("netdisk_uploads", sa.Column("valid_days_rewarded", sa.BigInteger(), nullable=False, server_default="0"))

    if not inspector.has_table("netdisk_favorites"):
        op.create_table(
            "netdisk_favorites",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("resource_id", sa.String(length=64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("user_id", "resource_id", name="uq_netdisk_favorite_user_resource"),
        )
        op.create_index("ix_netdisk_favorites_user_id", "netdisk_favorites", ["user_id"])
        op.create_index("ix_netdisk_favorites_resource_id", "netdisk_favorites", ["resource_id"])
        op.create_index("ix_netdisk_favorites_created_at", "netdisk_favorites", ["created_at"])

    if not inspector.has_table("netdisk_requests"):
        op.create_table(
            "netdisk_requests",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("title", sa.String(length=120), nullable=False),
            sa.Column("pans", sa.String(length=120), nullable=False),
            sa.Column("category", sa.String(length=64), nullable=False),
            sa.Column("bounty_points", sa.BigInteger(), nullable=False, server_default="5"),
            sa.Column("note", sa.Text(), nullable=False, server_default=""),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
            sa.Column("submissions_count", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("deadline_text", sa.String(length=32), nullable=False, server_default="3天后"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_netdisk_requests_user_id", "netdisk_requests", ["user_id"])
        op.create_index("ix_netdisk_requests_title", "netdisk_requests", ["title"])
        op.create_index("ix_netdisk_requests_category", "netdisk_requests", ["category"])
        op.create_index("ix_netdisk_requests_status", "netdisk_requests", ["status"])
        op.create_index("ix_netdisk_requests_created_at", "netdisk_requests", ["created_at"])

    if not inspector.has_table("user_quality_profiles"):
        op.create_table(
            "user_quality_profiles",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("credit_score", sa.BigInteger(), nullable=False, server_default="100"),
            sa.Column("contribution_score", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("short_invalid_count", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("upload_restricted_until", sa.DateTime(timezone=True), nullable=True),
            sa.Column("risk_level", sa.String(length=32), nullable=False, server_default="normal"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("user_id"),
        )
        op.create_index("ix_user_quality_profiles_user_id", "user_quality_profiles", ["user_id"])
        op.create_index("ix_user_quality_profiles_risk_level", "user_quality_profiles", ["risk_level"])

    resource_columns = _columns(inspector, "netdisk_resources")
    if "uploader_user_id" not in resource_columns:
        op.add_column("netdisk_resources", sa.Column("uploader_user_id", postgresql.UUID(as_uuid=True), nullable=True))
        op.create_foreign_key(
            "fk_netdisk_resources_uploader_user_id_users",
            "netdisk_resources",
            "users",
            ["uploader_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index("ix_netdisk_resources_uploader_user_id", "netdisk_resources", ["uploader_user_id"])
    if "invalid_count" not in resource_columns:
        op.add_column("netdisk_resources", sa.Column("invalid_count", sa.BigInteger(), nullable=False, server_default="0"))
    if "report_count" not in resource_columns:
        op.add_column("netdisk_resources", sa.Column("report_count", sa.BigInteger(), nullable=False, server_default="0"))
    if "quality_score" not in resource_columns:
        op.add_column("netdisk_resources", sa.Column("quality_score", sa.BigInteger(), nullable=False, server_default="0"))
        op.create_index("ix_netdisk_resources_quality_score", "netdisk_resources", ["quality_score"])
    if "valid_days_rewarded" not in resource_columns:
        op.add_column("netdisk_resources", sa.Column("valid_days_rewarded", sa.BigInteger(), nullable=False, server_default="0"))
    if "last_invalid_at" not in resource_columns:
        op.add_column("netdisk_resources", sa.Column("last_invalid_at", sa.DateTime(timezone=True), nullable=True))

    bind.exec_driver_sql(
        """
        UPDATE system_configs
        SET config_data = jsonb_build_object(
                'upload_reward_points', 5,
                'upload_approved_points', 2,
                'upload_valid_7d_points', 3,
                'repair_reward_points', 5,
                'repair_reward_normal', 5,
                'repair_reward_featured', 8,
                'repair_reward_official', 10,
                'report_hide_threshold', 3,
                'invalid_penalty_multiplier', 1,
                'auto_hide_on_report', true
            ),
            updated_at = now()
        WHERE type = 'netdisk_audit_config';
        """
    )


def downgrade() -> None:
    op.drop_column("netdisk_uploads", "valid_days_rewarded")
    op.drop_column("netdisk_uploads", "reward_released_points")

    op.drop_index("ix_netdisk_resources_quality_score", table_name="netdisk_resources")
    op.drop_index("ix_netdisk_resources_uploader_user_id", table_name="netdisk_resources")
    op.drop_constraint("fk_netdisk_resources_uploader_user_id_users", "netdisk_resources", type_="foreignkey")
    op.drop_column("netdisk_resources", "last_invalid_at")
    op.drop_column("netdisk_resources", "valid_days_rewarded")
    op.drop_column("netdisk_resources", "quality_score")
    op.drop_column("netdisk_resources", "report_count")
    op.drop_column("netdisk_resources", "invalid_count")
    op.drop_column("netdisk_resources", "uploader_user_id")

    op.drop_index("ix_user_quality_profiles_risk_level", table_name="user_quality_profiles")
    op.drop_index("ix_user_quality_profiles_user_id", table_name="user_quality_profiles")
    op.drop_table("user_quality_profiles")


def _columns(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}
