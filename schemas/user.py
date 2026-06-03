"""
API schemas shared by user, payment, withdrawal, chat, and admin modules.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class UserLoginRequest(BaseModel):
    code: str
    avatar: str
    nickname: str
    invite_code: Optional[str] = None

    @field_validator("code", "avatar", "nickname", mode="before")
    @classmethod
    def check_not_empty(cls, value: Any) -> Any:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("field is required")
        return value


class UserProfile(BaseModel):
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
    token: str
    is_new_user: bool
    user: UserProfile


class UserUpdateRequest(BaseModel):
    avatar: Optional[str] = None
    nickname: Optional[str] = None


class VipPackage(BaseModel):
    id: str
    name: str
    price: float
    original_price: float = 0.0
    duration_days: int
    benefits: List[str] = Field(default_factory=list)


class VipPackagesResponse(BaseModel):
    enabled: bool = True
    packages: List[VipPackage] = Field(default_factory=list)


class CreateOrderRequest(BaseModel):
    package_id: str


class CreateOrderResponse(BaseModel):
    order_id: str
    pay_params: Dict[str, Any]


class VipStatusResponse(BaseModel):
    is_vip: bool
    vip_expire_at: Optional[datetime] = None
    days_remaining: int = 0


class CommissionRecordItem(BaseModel):
    id: str
    from_user_nickname: str
    from_user_avatar: str = ""
    order_amount: float
    commission_rate: str
    commission_amount: float
    level: int
    type: str
    created_at: Optional[str] = None


class InviteStatsResponse(BaseModel):
    invite_code: str
    direct_count: int
    indirect_count: int = 0
    team_count: int
    total_income: float
    balance: float
    total_withdrawn: float = 0.0
    frozen_balance: float = 0.0


class InviteeItem(BaseModel):
    nickname: str
    avatar: str = ""
    is_vip: bool = False
    joined_at: Optional[str] = None


class WithdrawalApplyRequest(BaseModel):
    amount: float = Field(gt=0, le=200.00, description="withdrawal amount")

    @field_validator("amount")
    @classmethod
    def check_min(cls, value: float) -> float:
        if value < 0.10:
            raise ValueError("minimum amount is 0.10")
        return value


class WithdrawalRecordItem(BaseModel):
    id: str
    amount: float
    status: str
    batch_no: str
    fail_reason: Optional[str] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None


class WithdrawalConfigResponse(BaseModel):
    min_amount: float
    max_amount: float
    tips: str = ""


class ChatSendRequest(BaseModel):
    content: str = Field(max_length=1000)
    msg_type: str = "text"

    @field_validator("content", mode="before")
    @classmethod
    def check_chat_content(cls, value: Any) -> Any:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("content is required")
        return value


class ChatMessageItem(BaseModel):
    id: str
    sender: str
    content: str
    msg_type: str = "text"
    is_self: bool = False
    is_read: bool = False
    created_at: Optional[str] = None


class DashboardStatsResponse(BaseModel):
    user_count: int
    vip_count: int
    today_new_users: int
    total_income: float
    pending_withdrawals: int
    success_withdrawal_amount: float
    pending_withdrawal_amount: float = 0.0


class ConfigUpdateRequest(BaseModel):
    type: str
    config_data: Dict[str, Any] = Field(default_factory=dict)


class AdminReplyRequest(BaseModel):
    user_id: str
    content: str


class AdminUserVipUpdateRequest(BaseModel):
    is_vip: bool
    vip_expire_at: Optional[datetime] = None


class WithdrawalProcessRequest(BaseModel):
    record_id: str
    action: str
    reason: Optional[str] = None


class PaginatedResponse(BaseModel):
    list: List[Any] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
    has_more: bool = False
