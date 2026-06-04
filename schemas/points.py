"""Schemas for stage 2 points ledger endpoints."""

from datetime import datetime

from pydantic import BaseModel, Field

from schemas.checkin import CheckinAccountSummary


class PointsAccountFullSummary(CheckinAccountSummary):
    locked_withdraw_points: int = 0
    withdrawn_points: int = 0


class PointsWithdrawalApplyRequest(BaseModel):
    points_amount: int = Field(gt=0, le=1000000)


class PointsWithdrawalSummaryResponse(BaseModel):
    exchange_rate: int = 100
    withdrawable_points: int = 0
    withdrawable_amount: float = 0.0
    min_withdraw_amount: float = 1.0
    min_withdraw_points: int = 100
    max_withdraw_amount: float = 200.0
    max_withdraw_points: int = 20000
    is_first_withdraw: bool = False
    is_member: bool = False
    tips: str = ""
    account: PointsAccountFullSummary


class PointsWithdrawalApplyResponse(BaseModel):
    record_id: str
    points_amount: int
    amount: float
    status: str
    batch_no: str
    transfer_bill_no: str = ""
    created_at: str | None = None
    account: PointsAccountFullSummary


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
