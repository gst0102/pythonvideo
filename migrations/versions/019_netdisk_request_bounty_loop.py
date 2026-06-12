"""netdisk request bounty loop

Revision ID: 019_netdisk_request_bounty_loop
Revises: 018_backfill_signup_seed_points
Create Date: 2026-06-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "019_netdisk_request_bounty_loop"
down_revision: Union[str, None] = "018_backfill_signup_seed_points"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    request_columns = _columns(inspector, "netdisk_requests")
    if "bounty_status" not in request_columns:
        op.add_column("netdisk_requests", sa.Column("bounty_status", sa.String(length=32), nullable=False, server_default="frozen"))
        op.create_index("ix_netdisk_requests_bounty_status", "netdisk_requests", ["bounty_status"])
    if "accepted_upload_id" not in request_columns:
        op.add_column("netdisk_requests", sa.Column("accepted_upload_id", postgresql.UUID(as_uuid=True), nullable=True))
        op.create_foreign_key(
            "fk_netdisk_requests_accepted_upload_id_uploads",
            "netdisk_requests",
            "netdisk_uploads",
            ["accepted_upload_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index("ix_netdisk_requests_accepted_upload_id", "netdisk_requests", ["accepted_upload_id"])
    if "expires_at" not in request_columns:
        op.add_column("netdisk_requests", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
        op.create_index("ix_netdisk_requests_expires_at", "netdisk_requests", ["expires_at"])
        bind.exec_driver_sql("UPDATE netdisk_requests SET expires_at = created_at + interval '3 days' WHERE expires_at <= created_at")
    if "accepted_at" not in request_columns:
        op.add_column("netdisk_requests", sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True))
    if "closed_at" not in request_columns:
        op.add_column("netdisk_requests", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))

    upload_columns = _columns(inspector, "netdisk_uploads")
    if "request_id" not in upload_columns:
        op.add_column("netdisk_uploads", sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=True))
        op.create_foreign_key(
            "fk_netdisk_uploads_request_id_requests",
            "netdisk_uploads",
            "netdisk_requests",
            ["request_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index("ix_netdisk_uploads_request_id", "netdisk_uploads", ["request_id"])
    if "accepted_at" not in upload_columns:
        op.add_column("netdisk_uploads", sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("netdisk_uploads", "accepted_at")
    op.drop_index("ix_netdisk_uploads_request_id", table_name="netdisk_uploads")
    op.drop_constraint("fk_netdisk_uploads_request_id_requests", "netdisk_uploads", type_="foreignkey")
    op.drop_column("netdisk_uploads", "request_id")

    op.drop_column("netdisk_requests", "closed_at")
    op.drop_column("netdisk_requests", "accepted_at")
    op.drop_index("ix_netdisk_requests_expires_at", table_name="netdisk_requests")
    op.drop_column("netdisk_requests", "expires_at")
    op.drop_index("ix_netdisk_requests_accepted_upload_id", table_name="netdisk_requests")
    op.drop_constraint("fk_netdisk_requests_accepted_upload_id_uploads", "netdisk_requests", type_="foreignkey")
    op.drop_column("netdisk_requests", "accepted_upload_id")
    op.drop_index("ix_netdisk_requests_bounty_status", table_name="netdisk_requests")
    op.drop_column("netdisk_requests", "bounty_status")


def _columns(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}
