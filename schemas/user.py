"""
Pydantic 请求/响应模型 — MVC 架构中的 Schema 层

控制 API 输入输出的数据格式：
  - 请求模型（Request）: 定义入参验证规则
  - 响应模型（Response）: 定义返回数据格式

注意区分：
  - models/ 下是数据库模型（SQLModel ⇔ PostgreSQL）
  - schemas/ 下是 API 模型（Pydantic ⇔ HTTP）
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ═══════════════════════════════════════════════════════════════
#  用户模块
# ═══════════════════════════════════════════════════════════════

class UserLoginRequest(BaseModel):
    """用户登录/注册请求"""
    code: str
    avatar: str
    nickname: str
    invite_code: Optional[str] = None

    @field_validator("code", "avatar", "nickname", mode="before")
    @classmethod
    def check_not_empty(cls, v: Any, info: Any) -> Any:
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"{info.field_name} 必填")
        return v


class UserProfile(BaseModel):
    """用户信息响应"""
    id: str
    openid: str
    nickname: str
    avatar: str
    invite_code: str
    is_vip: bool
    vip_expire_at: Optional[datetime] = None
    balance: float
    frozen_balance: float = 0.0
    total_income: float
    total_withdrawn: float = 0.0
    invite_count: int
    team_count: int
    created_at: Optional[datetime] = None


class UserLoginResponse(BaseModel):
    """登录响应"""
    token: str
    is_new_user: bool
    user: UserProfile


class UserUpdateRequest(BaseModel):
    """更新用户资料"""
    avatar: Optional[str] = None
    nickname: Optional[str] = None


# ═══════════════════════════════════════════════════════════════
#  VIP / 支付模块
# ═══════════════════════════════════════════════════════════════

class VipPackage(BaseModel):
    """VIP 套餐"""
    id: str
    name: str
    price: float
    original_price: float = 0.0
    duration_days: int
    benefits: List[str] = []


class VipPackagesResponse(BaseModel):
    """VIP 套餐列表"""
    enabled: bool = True
    packages: List[VipPackage] = []


class CreateOrderRequest(BaseModel):
    """创建 VIP 订单"""
    package_id: str  # month / quarter / year


class CreateOrderResponse(BaseModel):
    """订单创建响应（含微信支付参数）"""
    order_id: str
    pay_params: Dict[str, Any]


class VipStatusResponse(BaseModel):
    """VIP 状态"""
    is_vip: bool
    vip_expire_at: Optional[datetime] = None
    days_remaining: int = 0


# ═══════════════════════════════════════════════════════════════
#  佣金 / 分销模块
# ═══════════════════════════════════════════════════════════════

class CommissionRecordItem(BaseModel):
    """佣金记录项"""
    id: str
    from_user_nickname: str
    from_user_avatar: str = ""
    order_amount: float
    commission_rate: str  # "10.0%"
    commission_amount: float
    level: int
    type: str
    created_at: Optional[str] = None


class InviteStatsResponse(BaseModel):
    """邀请统计"""
    invite_code: str
    direct_count: int
    indirect_count: int = 0
    team_count: int
    total_income: float
    balance: float
    total_withdrawn: float = 0.0
    frozen_balance: float = 0.0


class InviteeItem(BaseModel):
    """被邀请人信息"""
    nickname: str
    avatar: str = ""
    is_vip: bool = False
    joined_at: Optional[str] = None


# ═══════════════════════════════════════════════════════════════
#  提现模块
# ═══════════════════════════════════════════════════════════════

class WithdrawalApplyRequest(BaseModel):
    """提现申请"""
    amount: float = Field(gt=0, le=200.00, description="提现金额（元）")

    @field_validator("amount")
    @classmethod
    def check_min(cls, v: float) -> float:
        if v < 0.10:
            raise ValueError("最低提现 0.10 元")
        return v


class WithdrawalRecordItem(BaseModel):
    """提现记录项"""
    id: str
    amount: float
    status: str
    batch_no: str
    fail_reason: Optional[str] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None


class WithdrawalConfigResponse(BaseModel):
    """提现配置"""
    min_amount: float
    max_amount: float
    tips: str = ""


# ═══════════════════════════════════════════════════════════════
#  聊天模块
# ═══════════════════════════════════════════════════════════════

class ChatSendRequest(BaseModel):
    """发送消息"""
    content: str = Field(max_length=1000)
    msg_type: str = "text"

    @field_validator("content", mode="before")
    @classmethod
    def check_not_empty(cls, v: Any) -> Any:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("消息内容不能为空")
        return v


class ChatMessageItem(BaseModel):
    """聊天消息项"""
    id: str
    sender: str
    content: str
    msg_type: str = "text"
    is_self: bool = False
    is_read: bool = False
    created_at: Optional[str] = None


# ═══════════════════════════════════════════════════════════════
#  管理端模块
# ═══════════════════════════════════════════════════════════════

class DashboardStatsResponse(BaseModel):
    """仪表盘统计"""
    user_count: int
    vip_count: int
    today_new_users: int
    total_income: float
    pending_withdrawals: int
    success_withdrawal_amount: float
    pending_withdrawal_amount: float = 0.0


class ConfigUpdateRequest(BaseModel):
    """更新配置"""
    type: str
    config_data: Dict[str, Any] = {}


class AdminReplyRequest(BaseModel):
    """管理员回复"""
    user_id: str
    content: str


class WithdrawalProcessRequest(BaseModel):
    """处理提现"""
    record_id: str
    action: str  # approve / reject
    reason: Optional[str] = None


# ═══════════════════════════════════════════════════════════════
#  通用分页
# ═══════════════════════════════════════════════════════════════

class PaginatedResponse(BaseModel):
    """分页响应"""
    list: List[Any] = []
    total: int = 0
    page: int = 1
    page_size: int = 20
    has_more: bool = False
