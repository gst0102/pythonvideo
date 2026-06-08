"""Stage 2 daily check-in service."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, Tuple

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from models.ad_event import AdEventRecord
from models.checkin_record import CheckinRecord
from models.daily_task_stat import DailyTaskStat
from models.points_ledger import PointsLedger
from models.user import User
from models.user_account import UserAccount
from services.config_service import ConfigService
from services.points_account_service import PointsAccountService


class CheckinService:
    """Daily check-in query and execution service."""

    @staticmethod
    async def get_status(session: AsyncSession, user: User) -> Dict[str, Any]:
        today = datetime.utcnow().date()
        account, _ = await PointsAccountService.ensure_user_account(session, user.id)
        record = await _get_checkin_record(session, user.id, today)
        config = await _get_points_config(session)

        if record:
            return _build_status_payload(
                today=today,
                account=account,
                record=record,
                base_points=int(record.base_points),
                bonus_points=int(record.bonus_points),
                total_points=int(record.total_points),
                member_bonus_enabled=bool(user.is_vip),
            )

        base_points = _resolve_base_points(config, bool(user.is_vip))
        return _build_status_payload(
            today=today,
            account=account,
            record=None,
            base_points=base_points,
            bonus_points=0,
            total_points=base_points,
            member_bonus_enabled=bool(user.is_vip),
        )

    @staticmethod
    async def execute_checkin(
        session: AsyncSession,
        user: User,
    ) -> Tuple[Dict[str, Any], bool]:
        today = datetime.utcnow().date()
        existing = await _get_checkin_record(session, user.id, today)
        account, _ = await PointsAccountService.ensure_user_account(session, user.id)
        config = await _get_points_config(session)

        if existing:
            ledger = await PointsAccountService.get_ledger_by_idempotency_key(
                session,
                f"checkin:{user.id}:{today.isoformat()}",
            )
            payload = _build_execute_payload(account=account, record=existing, ledger=ledger)
            return payload, False

        continuous_days = await _calculate_continuous_days(session, user.id, today)
        base_points = _resolve_base_points(config, bool(user.is_vip))
        bonus_points = 0
        total_points = base_points + bonus_points

        ledger, account, _ = await PointsAccountService.add_points(
            session=session,
            user_id=user.id,
            points=total_points,
            source="checkin",
            change_type="earn",
            availability="withdrawable",
            idempotency_key=f"checkin:{user.id}:{today.isoformat()}",
            related_type="checkin",
            related_id=today.isoformat(),
            remark="daily checkin reward",
        )

        record = CheckinRecord(
            user_id=user.id,
            checkin_date=today,
            base_points=base_points,
            bonus_points=bonus_points,
            total_points=total_points,
            continuous_days=continuous_days,
            is_member_at_checkin=bool(user.is_vip),
            ad_bonus_used=False,
        )
        session.add(record)

        stat = await _get_or_create_daily_task_stat(session, user.id, today)
        stat.today_points += total_points
        stat.checkin_done = True
        stat.updated_at = datetime.utcnow()

        await session.flush()
        return _build_execute_payload(account=account, record=record, ledger=ledger), True

    @staticmethod
    async def claim_ad_bonus(
        session: AsyncSession,
        user: User,
        ad_event_id: str,
    ) -> Tuple[Dict[str, Any], bool, str | None]:
        today = datetime.utcnow().date()
        clean_event_id = (ad_event_id or "").strip()
        if not clean_event_id:
            return {}, False, "ad_event_id is required"

        record = await _get_checkin_record(session, user.id, today)
        if not record:
            return {}, False, "check in before claiming ad bonus"

        account, _ = await PointsAccountService.ensure_user_account(session, user.id)
        existing_key = f"checkin_ad_bonus:{user.id}:{today.isoformat()}"
        existing_ledger = await PointsAccountService.get_ledger_by_idempotency_key(session, existing_key)
        if record.ad_bonus_used or existing_ledger:
            payload = _build_execute_payload(account=account, record=record, ledger=existing_ledger)
            return payload, False, None

        ad_event = await _get_completed_checkin_ad_event(session, user.id, clean_event_id)
        if not ad_event:
            return {}, False, "completed checkin ad event not found"

        config = await _get_points_config(session)
        bonus_points = _resolve_ad_bonus_points(config)
        ledger, account, created = await PointsAccountService.add_points(
            session=session,
            user_id=user.id,
            points=bonus_points,
            source="checkin",
            change_type="ad_bonus",
            availability="withdrawable",
            idempotency_key=existing_key,
            related_type="ad_event",
            related_id=clean_event_id,
            remark="daily checkin ad bonus",
        )

        record.ad_bonus_used = True
        record.ad_event_id = clean_event_id
        record.bonus_points += bonus_points
        record.total_points += bonus_points
        record.updated_at = datetime.utcnow()

        stat = await _get_or_create_daily_task_stat(session, user.id, today)
        stat.today_points += bonus_points
        stat.updated_at = datetime.utcnow()

        await session.flush()
        return _build_execute_payload(account=account, record=record, ledger=ledger), created, None


async def _get_points_config(session: AsyncSession) -> Dict[str, Any]:
    return await ConfigService.get(session, "stage2_points_config")


async def _get_checkin_record(session: AsyncSession, user_id, checkin_day: date) -> CheckinRecord | None:
    stmt = select(CheckinRecord).where(
        CheckinRecord.user_id == user_id,
        CheckinRecord.checkin_date == checkin_day,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _calculate_continuous_days(session: AsyncSession, user_id, today: date) -> int:
    yesterday = today - timedelta(days=1)
    previous = await _get_checkin_record(session, user_id, yesterday)
    if not previous:
        return 1
    return int(previous.continuous_days) + 1


async def _get_or_create_daily_task_stat(
    session: AsyncSession,
    user_id,
    stat_day: date,
) -> DailyTaskStat:
    stmt = select(DailyTaskStat).where(
        DailyTaskStat.user_id == user_id,
        DailyTaskStat.stat_date == stat_day,
    )
    result = await session.execute(stmt)
    stat = result.scalar_one_or_none()
    if stat:
        return stat

    stat = DailyTaskStat(user_id=user_id, stat_date=stat_day)
    session.add(stat)
    await session.flush()
    return stat


def _resolve_base_points(config: Dict[str, Any], is_member: bool) -> int:
    member_points = int(config.get("checkin_base_points_member", 2))
    normal_points = int(config.get("checkin_base_points_normal", 1))
    return member_points if is_member else normal_points


def _resolve_ad_bonus_points(config: Dict[str, Any]) -> int:
    value = config.get("checkin_ad_bonus_points", 1)
    try:
        return max(int(value), 1)
    except (TypeError, ValueError):
        return 1


async def _get_completed_checkin_ad_event(
    session: AsyncSession,
    user_id,
    event_id: str,
) -> AdEventRecord | None:
    stmt = (
        select(AdEventRecord)
        .where(
            AdEventRecord.user_id == user_id,
            AdEventRecord.event_id == event_id,
            AdEventRecord.event_type == "complete",
            AdEventRecord.is_completed == True,  # noqa: E712
        )
        .order_by(AdEventRecord.created_at.desc())
    )
    result = await session.execute(stmt)
    return result.scalars().first()


def _build_account_summary(account: UserAccount) -> Dict[str, int]:
    return {
        "total_points": int(account.total_points),
        "withdrawable_points": int(account.withdrawable_points),
        "frozen_points": int(account.frozen_points),
        "consumable_points": int(account.consumable_points),
    }


def _build_status_payload(
    *,
    today: date,
    account: UserAccount,
    record: CheckinRecord | None,
    base_points: int,
    bonus_points: int,
    total_points: int,
    member_bonus_enabled: bool,
) -> Dict[str, Any]:
    return {
        "today": today,
        "checked_in": record is not None,
        "continuous_days": int(record.continuous_days) if record else 0,
        "base_points": base_points,
        "bonus_points": bonus_points,
        "total_points": total_points,
        "member_bonus_enabled": member_bonus_enabled,
        "checkin_recorded_at": record.created_at if record else None,
        "account": _build_account_summary(account),
    }


def _build_execute_payload(
    *,
    account: UserAccount,
    record: CheckinRecord,
    ledger: PointsLedger | None,
) -> Dict[str, Any]:
    return {
        "today": record.checkin_date,
        "checked_in": True,
        "continuous_days": int(record.continuous_days),
        "base_points": int(record.base_points),
        "bonus_points": int(record.bonus_points),
        "total_points": int(record.total_points),
        "ledger_id": str(ledger.id) if ledger else "",
        "account": _build_account_summary(account),
        "checkin_recorded_at": record.created_at,
    }
