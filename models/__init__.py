"""
数据模型层 — SQLModel 表定义

MVC 架构中的 Model 层：
  - base.py       — 数据库引擎、会话管理、依赖注入
  - user.py       — 用户表（注册、邀请、余额、VIP）
  - order.py      — 订单表（VIP 购买、支付状态）
  - commission.py — 佣金记录表（二级分销）
  - withdrawal.py — 提现记录表（微信商家转账）
  - chat.py       — 聊天消息表（在线客服）
  - config.py     — 系统配置表（JSONB 灵活配置）

使用方式：
  from models import User, Order, get_session
  from models.base import init_db, close_db
"""

from models.base import (
    close_db,
    get_session,
    get_session_ctx,
    init_db,
)
from models.user import User
from models.order import Order
from models.commission import CommissionRecord
from models.withdrawal import WithdrawalRecord
from models.chat import ChatMessage
from models.config import SystemConfig
from models.anime_resource import AnimeResource
from models.user_subscription import UserSubscription

# 所有表，供 Alembic 自动发现
__all__ = [
    "User",
    "Order",
    "CommissionRecord",
    "WithdrawalRecord",
    "ChatMessage",
    "SystemConfig",
    "AnimeResource",
    "UserSubscription",
    "get_session",
    "get_session_ctx",
    "init_db",
    "close_db",
]
