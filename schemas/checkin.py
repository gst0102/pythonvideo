"""Schemas for stage 2 check-in endpoints."""

from datetime import date, datetime

from pydantic import BaseModel


class CheckinAccountSummary(BaseModel):
    total_points: int = 0
    withdrawable_points: int = 0
    frozen_points: int = 0
    consumable_points: int = 0


class CheckinStatusResponse(BaseModel):
    today: date
    checked_in: bool
    continuous_days: int = 0
    base_points: int = 0
    bonus_points: int = 0
    total_points: int = 0
    member_bonus_enabled: bool = False
    checkin_recorded_at: datetime | None = None
    account: CheckinAccountSummary


class CheckinExecuteResponse(BaseModel):
    today: date
    checked_in: bool = True
    continuous_days: int
    base_points: int
    bonus_points: int = 0
    total_points: int
    ledger_id: str
    account: CheckinAccountSummary
    checkin_recorded_at: datetime | None = None
