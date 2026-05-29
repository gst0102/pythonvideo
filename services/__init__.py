"""
业务服务层 — MVC 架构中的 Service 层

所有核心业务逻辑都在这里：
  - user_service.py      — 登录注册、邀请关系
  - payment_service.py   — 支付回调、VIP 激活、佣金计算
  - withdrawal_service.py — 提现申请、转账回调
  - commission_service.py — 佣金查询、邀请统计
  - chat_service.py      — 聊天消息收发
  - config_service.py    — 系统配置读写
"""

from services.user_service import UserService
from services.payment_service import PaymentService
from services.withdrawal_service import WithdrawalService
from services.commission_service import CommissionService
from services.chat_service import ChatService
from services.config_service import ConfigService

__all__ = [
    "UserService",
    "PaymentService",
    "WithdrawalService",
    "CommissionService",
    "ChatService",
    "ConfigService",
]
