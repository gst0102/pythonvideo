"""Schemas for stage 2 points ledger endpoints."""

from datetime import datetime

from pydantic import BaseModel, Field

from schemas.checkin import CheckinAccountSummary


class PointsLedgerItem(BaseModel):
    id: str
    change_type: str
    source: str
    availability: str
    points_delta: int
    balance_withdrawable_after: int
    balance_frozen_after: int
    balance_consumable_after: int
    related_type: str | None = None
    related_id: str | None = None
    remark: str | None = None
    created_at: datetime


class PointsLedgerResponse(BaseModel):
    page: int = 1
    page_size: int = 20
    total: int = 0
    has_more: bool = False
    account: CheckinAccountSummary
    items: list[PointsLedgerItem] = Field(default_factory=list)
