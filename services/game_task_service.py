"""Stage 2 game task reward service."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Tuple

from sqlalchemy import desc
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from models.ad_event import AdEventRecord
from models.daily_task_stat import DailyTaskStat
from models.game_round import GameRound
from models.order import Order
from models.points_ledger import PointsLedger
from models.user import User
from models.user_account import UserAccount
from services.config_service import ConfigService
from services.points_account_service import PointsAccountService

VALID_GAME_CODES = {"rps"}
VALID_RESULTS = {"win", "lose", "draw"}
DEFAULT_TASK_CONFIG = {
    "daily_game_task_limit_normal": 10,
    "daily_game_task_limit_member_month": 100,
    "daily_game_task_limit_member_quarter": 150,
    "daily_game_task_limit_member_year": 200,
}
DEFAULT_POINTS_CONFIG = {
    "game_base_points_min": 1,
    "game_base_points_max": 2,
    "game_ad_multiplier": 2,
}


class GameTaskService:
    """Game task query and reward service."""

    @staticmethod
    async def get_status(session: AsyncSession, user: User) -> Dict[str, Any]:
        today = datetime.utcnow().date()
        account, _ = await PointsAccountService.ensure_user_account(session, user.id)
        stat = await _get_or_create_daily_task_stat(session, user, today)

        return {
            "today": today,
            "today_points": int(stat.today_points),
            "today_used": int(stat.game_tasks_used),
            "today_limit": int(stat.game_tasks_limit),
            "today_remaining": max(int(stat.game_tasks_limit) - int(stat.game_tasks_used), 0),
            "member_bonus_enabled": bool(user.is_vip),
            "account": _build_account_summary(account),
            "games": [
                {
                    "code": "rps",
                    "name": "石头剪刀布",
                    "status": "available",
                    "points_range": _build_points_range(await _get_points_config(session)),
                }
            ],
        }

    @staticmethod
    async def complete_round(
        session: AsyncSession,
        user: User,
        *,
        game_code: str,
        round_id: str,
        result: str,
        ad_event_id: str | None = None,
    ) -> Tuple[Dict[str, Any], bool]:
        normalized_game_code = game_code.strip().lower()
        normalized_result = result.strip().lower()
        if normalized_game_code not in VALID_GAME_CODES:
            raise ValueError("unsupported game code")
        if normalized_result not in VALID_RESULTS:
            raise ValueError("unsupported game result")
        if ad_event_id and ad_event_id.strip():
            raise ValueError("ad bonus must be claimed separately")

        today = datetime.utcnow().date()
        existing = await _get_game_round(session, round_id)
        account, _ = await PointsAccountService.ensure_user_account(session, user.id)
        stat = await _get_or_create_daily_task_stat(session, user, today)
        points_config = await _get_points_config(session)

        if existing:
            ledger = await PointsAccountService.get_ledger_by_idempotency_key(
                session,
                f"game_task:{user.id}:{round_id}",
            )
            payload = _build_round_payload(account=account, stat=stat, round_record=existing, ledger=ledger)
            return payload, False

        if stat.game_tasks_used >= stat.game_tasks_limit:
            raise RuntimeError("daily game task limit reached")

        base_points = _resolve_base_points(points_config, normalized_result)
        bonus_points = 0
        total_points = base_points

        ledger, account, _ = await PointsAccountService.add_points(
            session=session,
            user_id=user.id,
            points=total_points,
            source="game_task",
            change_type="earn",
            availability="withdrawable",
            idempotency_key=f"game_task:{user.id}:{round_id}",
            related_type="game_round",
            related_id=round_id,
            remark=f"{normalized_game_code} reward",
        )

        round_record = GameRound(
            user_id=user.id,
            round_id=round_id,
            game_code=normalized_game_code,
            result=normalized_result,
            base_points=base_points,
            bonus_points=bonus_points,
            total_points=total_points,
            ad_event_id=None,
            status="completed",
            ledger_id=ledger.id,
            played_date=today,
        )
        session.add(round_record)

        stat.game_tasks_used += 1
        stat.today_points += total_points
        stat.updated_at = datetime.utcnow()

        await session.flush()
        return _build_round_payload(account=account, stat=stat, round_record=round_record, ledger=ledger), True

    @staticmethod
    async def claim_round_ad_bonus(
        session: AsyncSession,
        user: User,
        *,
        round_id: str,
        ad_event_id: str,
    ) -> Tuple[Dict[str, Any], bool]:
        normalized_round_id = round_id.strip()
        normalized_ad_event_id = ad_event_id.strip()
        if not normalized_round_id:
            raise ValueError("round_id is required")
        if not normalized_ad_event_id:
            raise ValueError("ad_event_id is required")
        if f":{normalized_round_id}:" not in normalized_ad_event_id:
            raise RuntimeError("ad event does not match game round")

        round_record = await _get_game_round(session, normalized_round_id)
        if not round_record or round_record.user_id != user.id:
            raise RuntimeError("game round not found")

        stat = await _get_or_create_daily_task_stat(session, user, datetime.utcnow().date())
        account, _ = await PointsAccountService.ensure_user_account(session, user.id)
        points_config = await _get_points_config(session)

        existing_ledger = await PointsAccountService.get_ledger_by_idempotency_key(
            session,
            f"game_task_ad_bonus:{user.id}:{normalized_round_id}:{normalized_ad_event_id}",
        )
        if existing_ledger:
            payload = _build_round_ad_bonus_payload(
                account=account,
                stat=stat,
                round_record=round_record,
                ledger=existing_ledger,
                rewarded=False,
            )
            return payload, False

        if int(round_record.bonus_points) > 0 or round_record.ad_event_id:
            payload = _build_round_ad_bonus_payload(
                account=account,
                stat=stat,
                round_record=round_record,
                ledger=None,
                rewarded=False,
            )
            return payload, False

        completed_event = await _get_completed_ad_event(session, user.id, normalized_ad_event_id)
        if not completed_event:
            raise RuntimeError("ad event not completed")
        if await _has_rewarded_ad_event(session, user.id, normalized_ad_event_id):
            payload = _build_round_ad_bonus_payload(
                account=account,
                stat=stat,
                round_record=round_record,
                ledger=None,
                rewarded=False,
            )
            return payload, False

        bonus_points = _resolve_bonus_points(points_config, int(round_record.base_points), normalized_ad_event_id)
        if bonus_points <= 0:
            raise RuntimeError("ad bonus is disabled")

        ledger, account, created = await PointsAccountService.add_points(
            session=session,
            user_id=user.id,
            points=bonus_points,
            source="game_task",
            change_type="ad_bonus",
            availability="withdrawable",
            idempotency_key=f"game_task_ad_bonus:{user.id}:{normalized_round_id}:{normalized_ad_event_id}",
            related_type="ad_event",
            related_id=normalized_ad_event_id,
            remark=f"{round_record.game_code} ad bonus",
        )
        if not created:
            payload = _build_round_ad_bonus_payload(
                account=account,
                stat=stat,
                round_record=round_record,
                ledger=ledger,
                rewarded=False,
            )
            return payload, False

        round_record.bonus_points = int(round_record.bonus_points) + bonus_points
        round_record.total_points = int(round_record.total_points) + bonus_points
        round_record.ad_event_id = normalized_ad_event_id
        round_record.updated_at = datetime.utcnow()

        stat.today_points += bonus_points
        stat.updated_at = datetime.utcnow()

        session.add(
            AdEventRecord(
                event_id=normalized_ad_event_id,
                user_id=user.id,
                openid=user.openid,
                module=completed_event.module,
                section=completed_event.section,
                scene=completed_event.scene,
                ad_unit_id=completed_event.ad_unit_id,
                event_type="reward",
                is_completed=True,
                reward_points=float(bonus_points),
                reward_amount=0.0,
                date_key=completed_event.date_key,
                week_key=completed_event.week_key,
                month_key=completed_event.month_key,
            )
        )

        await session.flush()
        payload = _build_round_ad_bonus_payload(
            account=account,
            stat=stat,
            round_record=round_record,
            ledger=ledger,
            rewarded=True,
        )
        return payload, True


async def _get_task_config(session: AsyncSession) -> Dict[str, Any]:
    config = await ConfigService.get(session, "stage2_task_config")
    return {**DEFAULT_TASK_CONFIG, **(config or {})}


async def _get_points_config(session: AsyncSession) -> Dict[str, Any]:
    config = await ConfigService.get(session, "stage2_points_config")
    return {**DEFAULT_POINTS_CONFIG, **(config or {})}


async def _get_game_round(session: AsyncSession, round_id: str) -> GameRound | None:
    stmt = select(GameRound).where(GameRound.round_id == round_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _get_completed_ad_event(session: AsyncSession, user_id, ad_event_id: str) -> AdEventRecord | None:
    scene_prefix = ad_event_id.split(":", 1)[0].strip().lower()
    allowed_scenes = {"game_bonus", "game_jump"}
    scene_name = scene_prefix if scene_prefix in allowed_scenes else "game_bonus"
    stmt = (
        select(AdEventRecord)
        .where(
            AdEventRecord.user_id == user_id,
            AdEventRecord.event_id == ad_event_id,
            AdEventRecord.scene == scene_name,
            ((AdEventRecord.event_type == "complete") | (AdEventRecord.is_completed.is_(True))),
        )
        .order_by(desc(AdEventRecord.created_at))
    )
    result = await session.execute(stmt)
    return result.scalars().first()


async def _has_rewarded_ad_event(session: AsyncSession, user_id, ad_event_id: str) -> bool:
    stmt = select(AdEventRecord).where(
        AdEventRecord.user_id == user_id,
        AdEventRecord.event_id == ad_event_id,
        AdEventRecord.event_type == "reward",
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def _get_or_create_daily_task_stat(
    session: AsyncSession,
    user: User,
    stat_day,
) -> DailyTaskStat:
    stmt = select(DailyTaskStat).where(
        DailyTaskStat.user_id == user.id,
        DailyTaskStat.stat_date == stat_day,
    )
    result = await session.execute(stmt)
    stat = result.scalar_one_or_none()
    if stat:
        expected_limit = await _resolve_daily_limit(session, user)
        if stat.game_tasks_limit != expected_limit:
            stat.game_tasks_limit = expected_limit
            stat.updated_at = datetime.utcnow()
            await session.flush()
        return stat

    stat = DailyTaskStat(
        user_id=user.id,
        stat_date=stat_day,
        game_tasks_limit=await _resolve_daily_limit(session, user),
    )
    session.add(stat)
    await session.flush()
    return stat


async def _resolve_daily_limit(session: AsyncSession, user: User) -> int:
    config = await _get_task_config(session)
    if not user.is_vip:
        return int(config["daily_game_task_limit_normal"])

    period = await _resolve_vip_period(session, user.id)
    if period == "year":
        return int(config["daily_game_task_limit_member_year"])
    if period == "quarter":
        return int(config["daily_game_task_limit_member_quarter"])
    return int(config["daily_game_task_limit_member_month"])


async def _resolve_vip_period(session: AsyncSession, user_id) -> str:
    stmt = (
        select(Order)
        .where(Order.user_id == user_id, Order.status == "paid")
        .order_by(desc(Order.paid_at), desc(Order.created_at))
    )
    result = await session.execute(stmt)
    order = result.scalars().first()
    if not order or not order.period:
        return "month"
    period = str(order.period).strip().lower()
    if period not in {"month", "quarter", "year"}:
        return "month"
    return period


def _resolve_base_points(config: Dict[str, Any], result: str) -> int:
    min_points = int(config["game_base_points_min"])
    max_points = int(config["game_base_points_max"])
    if result == "win":
        return max_points
    return min_points


def _resolve_bonus_points(config: Dict[str, Any], base_points: int, ad_event_id: str | None) -> int:
    if not ad_event_id:
        return 0
    multiplier = max(int(config.get("game_ad_multiplier", 2)), 1)
    return base_points * (multiplier - 1)


def _build_points_range(config: Dict[str, Any]) -> str:
    return f"{int(config['game_base_points_min'])}-{int(config['game_base_points_max'])}"


def _build_account_summary(account: UserAccount) -> Dict[str, int]:
    return {
        "total_points": int(account.total_points),
        "withdrawable_points": int(account.withdrawable_points),
        "frozen_points": int(account.frozen_points),
        "consumable_points": int(account.consumable_points),
    }


def _build_round_payload(
    *,
    account: UserAccount,
    stat: DailyTaskStat,
    round_record: GameRound,
    ledger: PointsLedger | None,
) -> Dict[str, Any]:
    remaining = max(int(stat.game_tasks_limit) - int(stat.game_tasks_used), 0)
    return {
        "success": True,
        "game_code": round_record.game_code,
        "round_id": round_record.round_id,
        "result": round_record.result,
        "points_added": int(round_record.total_points),
        "base_points": int(round_record.base_points),
        "bonus_points": int(round_record.bonus_points),
        "today_used": int(stat.game_tasks_used),
        "today_limit": int(stat.game_tasks_limit),
        "today_remaining": remaining,
        "account": _build_account_summary(account),
        "ledger_id": str(ledger.id) if ledger else str(round_record.ledger_id or ""),
        "created_at": round_record.created_at,
    }


def _build_round_ad_bonus_payload(
    *,
    account: UserAccount,
    stat: DailyTaskStat,
    round_record: GameRound,
    ledger: PointsLedger | None,
    rewarded: bool,
) -> Dict[str, Any]:
    remaining = max(int(stat.game_tasks_limit) - int(stat.game_tasks_used), 0)
    return {
        "rewarded": rewarded,
        "round_id": round_record.round_id,
        "ad_event_id": round_record.ad_event_id,
        "points_added": int(ledger.points_delta) if ledger else 0,
        "base_points": int(round_record.base_points),
        "bonus_points": int(round_record.bonus_points),
        "total_points": int(round_record.total_points),
        "today_points": int(stat.today_points),
        "today_used": int(stat.game_tasks_used),
        "today_limit": int(stat.game_tasks_limit),
        "today_remaining": remaining,
        "account": _build_account_summary(account),
        "ledger_id": str(ledger.id) if ledger else "",
        "created_at": round_record.updated_at,
    }
