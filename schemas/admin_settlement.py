"""Schemas for admin game settlement endpoints."""

from datetime import date

from pydantic import BaseModel, Field


class AdminGameSettlementUpsertRequest(BaseModel):
    settlement_date: date
    ecpm_value: float | None = Field(default=None, ge=0)
    ad_pv: int | None = Field(default=None, ge=0)
    valid_clicks: int | None = Field(default=None, ge=0)
    total_revenue: float | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=512)


class AdminGameSettlementTriggerRequest(BaseModel):
    settlement_date: date
    allow_fallback: bool = True
    force_recalculate: bool = False
