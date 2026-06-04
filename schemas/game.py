"""Schemas for stage 2 game task endpoints."""

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from schemas.checkin import CheckinAccountSummary


class GameTaskItem(BaseModel):
    code: str
    name: str
    status: str = "available"
    points_range: str


class GameTaskStatusResponse(BaseModel):
    today: date
    today_points: int = 0
    today_used: int = 0
    today_limit: int = 0
    today_remaining: int = 0
    member_bonus_enabled: bool = False
    account: CheckinAccountSummary
    games: list[GameTaskItem] = Field(default_factory=list)


class GameAdSlotResponse(BaseModel):
    available: bool = False
    scene: str
    ad_event_id: str | None = None
    ad_unit_id: str | None = None
    ad_code: str | None = None
    message: str | None = None
    daily_user_show_limit: int | None = None
    daily_user_complete_limit: int | None = None


class GameRoundCompleteRequest(BaseModel):
    game_code: str
    round_id: str
    result: str
    ad_event_id: str | None = None

    @field_validator("game_code", "round_id", "result", mode="before")
    @classmethod
    def validate_required_str(cls, value: object) -> object:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("field is required")
        return value.strip()


class GameRoundCompleteResponse(BaseModel):
    success: bool = True
    game_code: str
    round_id: str
    result: str
    points_added: int
    base_points: int
    bonus_points: int = 0
    today_used: int
    today_limit: int
    today_remaining: int
    account: CheckinAccountSummary
    ledger_id: str
    created_at: datetime | None = None


class GameRoundAdBonusRequest(BaseModel):
    round_id: str
    ad_event_id: str

    @field_validator("round_id", "ad_event_id", mode="before")
    @classmethod
    def validate_ad_bonus_required_str(cls, value: object) -> object:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("field is required")
        return value.strip()


class GameRoundAdBonusResponse(BaseModel):
    rewarded: bool = True
    round_id: str
    ad_event_id: str | None = None
    points_added: int = 0
    base_points: int = 0
    bonus_points: int = 0
    total_points: int = 0
    today_points: int = 0
    today_used: int = 0
    today_limit: int = 0
    today_remaining: int = 0
    account: CheckinAccountSummary
    ledger_id: str = ""
    created_at: datetime | None = None
