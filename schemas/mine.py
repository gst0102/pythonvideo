"""Schemas for stage 2 mine assets endpoints."""

from pydantic import BaseModel, Field

from schemas.checkin import CheckinAccountSummary
from schemas.tasks import TaskOverviewMemberSummary, TaskOverviewUserSummary


class MineLegacyWallet(BaseModel):
    balance: float = 0.0
    frozen_balance: float = 0.0
    available_balance: float = 0.0
    total_income: float = 0.0
    total_withdrawn: float = 0.0


class MinePointsWallet(BaseModel):
    display_unit: str = "积分"
    exchange_rate: int = 100
    total_points: int = 0
    withdrawable_points: int = 0
    frozen_points: int = 0
    consumable_points: int = 0
    convertible_amount: float = 0.0
    withdrawable_amount: float = 0.0


class MineInviteSummary(BaseModel):
    invite_code: str
    direct_count: int = 0
    indirect_count: int = 0
    team_count: int = 0


class MineQuickAction(BaseModel):
    code: str
    title: str
    subtitle: str = ""


class MineAssetsResponse(BaseModel):
    user: TaskOverviewUserSummary
    member: TaskOverviewMemberSummary
    account: CheckinAccountSummary
    legacy_wallet: MineLegacyWallet
    points_wallet: MinePointsWallet
    invite_summary: MineInviteSummary
    quick_actions: list[MineQuickAction] = Field(default_factory=list)
