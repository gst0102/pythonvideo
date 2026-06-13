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
from models.ad_reward import AdRewardRecord
from models.ad_event import AdEventRecord
from models.user_account import UserAccount
from models.user_quality_profile import UserQualityProfile
from models.points_ledger import PointsLedger
from models.checkin_record import CheckinRecord
from models.game_round import GameRound
from models.daily_task_stat import DailyTaskStat
from models.game_settlement_batch import GameSettlementBatch
from models.game_user_settlement import GameUserSettlement
from models.invite_relation import InviteRelation
from models.netdisk_favorite import NetdiskFavorite
from models.netdisk_feedback import NetdiskFeedback
from models.netdisk_import_batch import NetdiskImportBatch
from models.netdisk_audit_log import NetdiskAuditLog
from models.netdisk_collected_resource import NetdiskCollectedResource
from models.netdisk_quality_alert import NetdiskQualityAlert
from models.netdisk_quality_daily_stat import NetdiskQualityDailyStat
from models.netdisk_repair import NetdiskRepair
from models.netdisk_request import NetdiskRequest
from models.netdisk_resource import NetdiskResource
from models.netdisk_risk_record import NetdiskRiskRecord
from models.netdisk_upload import NetdiskUpload
from models.netdisk_user_notification import NetdiskUserNotification

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
    "AdRewardRecord",
    "AdEventRecord",
    "UserAccount",
    "UserQualityProfile",
    "PointsLedger",
    "CheckinRecord",
    "GameRound",
    "DailyTaskStat",
    "GameSettlementBatch",
    "GameUserSettlement",
    "InviteRelation",
    "NetdiskFavorite",
    "NetdiskFeedback",
    "NetdiskImportBatch",
    "NetdiskAuditLog",
    "NetdiskCollectedResource",
    "NetdiskQualityAlert",
    "NetdiskQualityDailyStat",
    "NetdiskRepair",
    "NetdiskRequest",
    "NetdiskResource",
    "NetdiskRiskRecord",
    "NetdiskUpload",
    "NetdiskUserNotification",
    "get_session",
    "get_session_ctx",
    "init_db",
    "close_db",
]
