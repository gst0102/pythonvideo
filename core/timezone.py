"""Timezone helpers for business-day calculations."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

BUSINESS_TZ = ZoneInfo("Asia/Shanghai")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_bj() -> datetime:
    return now_utc().astimezone(BUSINESS_TZ)


def today_bj() -> date:
    return now_bj().date()


def bj_day_bounds_utc(day: date | None = None) -> tuple[datetime, datetime]:
    target_day = day or today_bj()
    start_local = datetime.combine(target_day, time.min, tzinfo=BUSINESS_TZ)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def bj_date_key(now: datetime | None = None) -> tuple[str, str, str]:
    current = now or now_bj()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(BUSINESS_TZ)
    iso = current.isocalendar()
    return current.strftime("%Y-%m-%d"), f"{iso.year}-{iso.week:02d}", current.strftime("%Y-%m")
