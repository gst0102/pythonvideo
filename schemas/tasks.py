"""Schemas for stage 2 task overview endpoints."""

from datetime import date, datetime

from pydantic import BaseModel

from schemas.checkin import CheckinAccountSummary, CheckinStatusResponse
from schemas.game import GameTaskStatusResponse


class TaskOverviewUserSummary(BaseModel):
    id: str
    nickname: str
    avatar: str = ""
    invite_code: str


class TaskOverviewMemberSummary(BaseModel):
    is_vip: bool = False
    plan_code: str = "none"
    vip_expire_at: datetime | None = None
    days_remaining: int = 0


class TaskOverviewResponse(BaseModel):
    today: date
    user: TaskOverviewUserSummary
    member: TaskOverviewMemberSummary
    account: CheckinAccountSummary
    today_points: int = 0
    checkin: CheckinStatusResponse
    game_task: GameTaskStatusResponse
