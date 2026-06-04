"""Schemas for stage 2 home overview endpoints."""

from datetime import date

from pydantic import BaseModel, Field

from schemas.checkin import CheckinAccountSummary, CheckinStatusResponse
from schemas.game import GameTaskStatusResponse
from schemas.tasks import TaskOverviewMemberSummary, TaskOverviewUserSummary


class HomeWelfareCard(BaseModel):
    title: str = "今日福利"
    subtitle: str = "签到领积分，互动任务赚更多。"
    checked_in: bool
    continuous_days: int = 0
    total_points: int = 0
    today_points: int = 0
    game_remaining: int = 0
    game_limit: int = 0
    next_checkin_points: int = 0


class HomeQuickEntry(BaseModel):
    code: str
    title: str
    subtitle: str = ""
    badge: str = ""


class HomeOverviewResponse(BaseModel):
    today: date
    user: TaskOverviewUserSummary
    member: TaskOverviewMemberSummary
    account: CheckinAccountSummary
    welfare_card: HomeWelfareCard
    checkin: CheckinStatusResponse
    game_task: GameTaskStatusResponse
    quick_entries: list[HomeQuickEntry] = Field(default_factory=list)
