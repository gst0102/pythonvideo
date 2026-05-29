"""初始迁移：创建所有表

Revision ID: 001
Revises: None
Create Date: 2026-05-29

从云开发迁移到 PostgreSQL 的初始表结构：
  - users
  - orders
  - commission_records
  - withdraw_records
  - chat_messages
  - system_configs
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建所有表"""

    # ── 1. users 表 ──────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("openid", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column("nickname", sa.String(100), nullable=False),
        sa.Column("avatar", sa.String(500), server_default=""),
        sa.Column("invite_code", sa.String(10), unique=True, nullable=False, index=True),
        # 邀请关系
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("grand_parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("invite_count", sa.Integer(), server_default="0"),
        sa.Column("indirect_count", sa.Integer(), server_default="0"),
        sa.Column("team_count", sa.Integer(), server_default="0"),
        # 财务
        sa.Column("balance", sa.Numeric(10, 2), server_default="0.00"),
        sa.Column("frozen_balance", sa.Numeric(10, 2), server_default="0.00"),
        sa.Column("total_income", sa.Numeric(10, 2), server_default="0.00"),
        sa.Column("total_withdrawn", sa.Numeric(10, 2), server_default="0.00"),
        # VIP
        sa.Column("is_vip", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("vip_expire_at", sa.DateTime(timezone=True), nullable=True),
        # 时间戳
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_users_parent_id", "users", ["parent_id"])

    # ── 2. orders 表 ──────────────────────────────────────────
    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("period", sa.String(20), nullable=False),
        sa.Column("duration_days", sa.Integer(), server_default="30"),
        sa.Column("description", sa.String(200), server_default=""),
        sa.Column("out_trade_no", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column("transaction_id", sa.String(64), nullable=True),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── 3. commission_records 表 ─────────────────────────────
    op.create_table(
        "commission_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("from_user_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("order_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("commission_rate", sa.Numeric(5, 2), nullable=False),
        sa.Column("commission_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("level", sa.SmallInteger(), nullable=False),
        sa.Column("type", sa.String(20), server_default="vip_recharge"),
        sa.Column("status", sa.String(20), server_default="settled"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── 4. withdraw_records 表 ───────────────────────────────
    op.create_table(
        "withdraw_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(20), server_default="processing", index=True),
        sa.Column("batch_no", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column("transfer_bill_no", sa.String(64), nullable=True),
        sa.Column("fail_reason", sa.Text(), nullable=True),
        sa.Column("ip", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── 5. chat_messages 表 ──────────────────────────────────
    op.create_table(
        "chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("sender", sa.String(10), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("msg_type", sa.String(10), server_default="text"),
        sa.Column("is_read", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
    )

    # ── 6. system_configs 表 ─────────────────────────────────
    op.create_table(
        "system_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("type", sa.String(50), unique=True, nullable=False, index=True),
        sa.Column("config_data", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── 7. 外键约束 ──────────────────────────────────────────
    op.create_foreign_key("fk_users_parent_id", "users", "users", ["parent_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_orders_user_id", "orders", "users", ["user_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key("fk_commission_user_id", "commission_records", "users", ["user_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key("fk_commission_from_user_id", "commission_records", "users", ["from_user_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key("fk_commission_order_id", "commission_records", "orders", ["order_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_withdraw_user_id", "withdraw_records", "users", ["user_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key("fk_chat_user_id", "chat_messages", "users", ["user_id"], ["id"], ondelete="CASCADE")

    # ── 8. 默认系统配置 ─────────────────────────────────────
    _seed_configs()


def downgrade() -> None:
    """删除所有表"""
    op.drop_table("system_configs")
    op.drop_table("chat_messages")
    op.drop_table("withdraw_records")
    op.drop_table("commission_records")
    op.drop_table("orders")
    op.drop_table("users")


def _seed_configs() -> None:
    """插入默认系统配置"""
    import json
    from alembic import op

    configs = [
        ("vip_settings", {
            "enabled": True,
            "packages": [
                {"id": "month", "name": "月度会员", "price": 9.90, "original_price": 19.90,
                 "duration_days": 30, "benefits": ["免广告", "专属客服", "高清画质"]},
                {"id": "quarter", "name": "季度会员", "price": 26.90, "original_price": 59.70,
                 "duration_days": 90, "benefits": ["免广告", "专属客服", "高清画质", "优先处理"]},
                {"id": "year", "name": "年度会员", "price": 88.80, "original_price": 238.80,
                 "duration_days": 365, "benefits": ["全部权益", "年度特惠", "7×24专属客服", "生日特权"]},
            ],
        }),
        ("withdrawal_config", {
            "min_amount": 0.10,
            "max_amount": 200.00,
            "tips": "1. 提现将在1-3个工作日内到账\n2. 单次提现最低0.1元\n3. 如有问题请联系客服",
        }),
        ("commission_settings", {
            "level1_rate": 10.00,
            "level2_rate": 5.00,
            "rules": "1. 邀请好友购买VIP即可获得佣金\n2. 佣金将在订单完成后自动到账\n3. 二级代理可获得额外奖励",
        }),
        ("service_settings", {
            "auto_reply": False,
            "welcome_msg": "您好！我是客服小助手，有什么可以帮助您的吗？",
            "offline_msg": "抱歉，客服暂时不在线，请留言，我们会尽快回复您。",
            "quick_replies": [
                "您好，请问有什么可以帮您的？",
                "关于会员问题，您可以查看会员权益说明。",
                "提现问题一般1-3个工作日到账，如有异常请联系我们。",
                "感谢您的反馈，我们会尽快处理！",
            ],
        }),
        ("platform_settings", {
            "platform_name": "视频平台",
            "logo_url": "",
            "contact_info": "",
            "share_title": "",
            "share_desc": "",
            "share_image": "",
        }),
    ]

    now = sa.func.now()
    system_configs = sa.table(
        "system_configs",
        sa.column("type", sa.String),
        sa.column("config_data", postgresql.JSONB),
        sa.column("updated_at", sa.DateTime),
    )

    for config_type, config_data in configs:
        op.execute(
            system_configs.insert().values(
                type=config_type,
                config_data=config_data,
                updated_at=now,
            )
        )
