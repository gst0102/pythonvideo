"""Stage 2 game task reward service."""

from __future__ import annotations

import hashlib
import secrets
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
from core.timezone import bj_day_bounds_utc, today_bj
from services.config_service import ConfigService
from services.points_account_service import PointsAccountService

VALID_GAME_CODES = {"rps"}
VALID_RESULTS = {"win", "lose", "draw"}
VALID_RPS_CHOICES = {"rock", "scissors", "paper"}
DEFAULT_TASK_CONFIG = {
    "daily_game_task_limit_normal": 10,
    "daily_game_task_limit_member_month": 100,
    "daily_game_task_limit_member_quarter": 150,
    "daily_game_task_limit_member_year": 200,
}
DEFAULT_POINTS_CONFIG = {
    "game_base_points_min": -2,
    "game_base_points_max": 4,
    "game_rps_win_points": 4,
    "game_rps_lose_points": -2,
    "game_ad_multiplier": 2,
}


class GameTaskService:
    """Game task query and reward service."""

    @staticmethod
    async def get_status(session: AsyncSession, user: User) -> Dict[str, Any]:
        today = today_bj()
        account, _ = await PointsAccountService.ensure_user_account(session, user.id)
        stat = await _get_or_create_daily_task_stat(session, user, today)
        today_estimated_points = await _get_today_estimated_points(session, user.id, today)

        return {
            "today": today,
            "today_points": int(today_estimated_points),
            "today_estimated_points": int(today_estimated_points),
            "today_used": int(stat.game_tasks_used),
            "today_limit": int(stat.game_tasks_limit),
            "today_remaining": max(int(stat.game_tasks_limit) - int(stat.game_tasks_used), 0),
            "member_bonus_enabled": bool(user.is_vip),
            "reward_notice": "猜拳赢了可领4分，平局0分，输了扣2分；赢局完整观看广告后记录积分。",
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
        result: str | None = None,
        user_choice: str | None = None,
        ad_event_id: str | None = None,
    ) -> Tuple[Dict[str, Any], bool]:
        normalized_game_code = game_code.strip().lower()
        if normalized_game_code not in VALID_GAME_CODES:
            raise ValueError("unsupported game code")
        if ad_event_id and ad_event_id.strip():
            raise ValueError("ad bonus must be claimed separately")

        normalized_choice = (user_choice or "").strip().lower()
        system_choice: str | None = None
        if normalized_choice:
            normalized_result, system_choice = _resolve_rps_round(normalized_choice)
        else:
            normalized_result = (result or "").strip().lower()
            if normalized_result not in VALID_RESULTS:
                raise ValueError("unsupported game result")

        today = today_bj()
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

        round_record = GameRound(
            user_id=user.id,
            round_id=round_id,
            game_code=normalized_game_code,
            result=normalized_result,
            base_points=base_points,
            bonus_points=bonus_points,
            total_points=0,
            ad_event_id=None,
            status="pending_ad" if base_points > 0 else "completed_no_reward",
            ledger_id=None,
            played_date=today,
        )
        session.add(round_record)

        stat.game_tasks_used += 1
        stat.updated_at = datetime.utcnow()

        ledger = None
        if base_points < 0:
            ledger, account, created = await PointsAccountService.add_points(
                session=session,
                user_id=user.id,
                points=base_points,
                source="game",
                change_type="game_penalty",
                availability="consumable",
                idempotency_key=f"game_task_penalty:{user.id}:{round_id}",
                related_type="game_round",
                related_id=round_record.round_id,
                remark=f"{round_record.game_code} lose penalty",
            )
            if created:
                round_record.total_points = base_points
                round_record.ledger_id = ledger.id
                round_record.status = "penalty_applied"
                round_record.updated_at = datetime.utcnow()

        await session.flush()
        return _build_round_payload(
            account=account,
            stat=stat,
            round_record=round_record,
            ledger=ledger,
            user_choice=normalized_choice or None,
            system_choice=system_choice,
        ), True

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

        stat = await _get_or_create_daily_task_stat(session, user, today_bj())
        account, _ = await PointsAccountService.ensure_user_account(session, user.id)

        existing_ledger = await PointsAccountService.get_ledger_by_idempotency_key(
            session,
            _build_ad_bonus_idempotency_key(user.id, normalized_round_id, normalized_ad_event_id),
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

        if int(round_record.total_points) > 0 or round_record.ad_event_id:
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

        estimated_points = int(round_record.base_points)
        if estimated_points <= 0:
            payload = _build_round_ad_bonus_payload(
                account=account,
                stat=stat,
                round_record=round_record,
                ledger=None,
                rewarded=False,
            )
            return payload, False

        ledger, account, created = await PointsAccountService.add_points(
            session=session,
            user_id=user.id,
            points=estimated_points,
            source="game",
            change_type="game_estimated",
            availability="consumable",
            idempotency_key=_build_ad_bonus_idempotency_key(user.id, normalized_round_id, normalized_ad_event_id),
            related_type="game_round",
            related_id=round_record.round_id,
            remark=f"{round_record.game_code} estimated reward",
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

        round_record.total_points = estimated_points
        round_record.ad_event_id = normalized_ad_event_id
        round_record.ledger_id = ledger.id
        round_record.status = "estimated_rewarded"
        round_record.updated_at = datetime.utcnow()
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
                reward_points=float(estimated_points),
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
    if result == "win":
        return int(config.get("game_rps_win_points") or config.get("game_base_points_max") or 4)
    if result == "lose":
        return int(config.get("game_rps_lose_points") or config.get("game_base_points_min") or -2)
    return 0


def _resolve_rps_round(user_choice: str) -> tuple[str, str]:
    if user_choice not in VALID_RPS_CHOICES:
        raise ValueError("unsupported rps choice")
    system_choice = secrets.choice(("rock", "scissors", "paper"))
    if user_choice == system_choice:
        return "draw", system_choice
    if (
        (user_choice == "rock" and system_choice == "scissors")
        or (user_choice == "scissors" and system_choice == "paper")
        or (user_choice == "paper" and system_choice == "rock")
    ):
        return "win", system_choice
    return "lose", system_choice


async def _get_today_estimated_points(session: AsyncSession, user_id, today) -> int:
    start_at, end_at = bj_day_bounds_utc(today)
    stmt = select(PointsLedger).where(
        PointsLedger.user_id == user_id,
        PointsLedger.source == "game",
        PointsLedger.availability == "consumable",
        PointsLedger.related_type == "game_round",
        PointsLedger.created_at >= start_at,
        PointsLedger.created_at < end_at,
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return sum(int(row.points_delta) for row in rows)


def _build_ad_bonus_idempotency_key(user_id, round_id: str, ad_event_id: str) -> str:
    raw = f"{user_id}:{round_id}:{ad_event_id}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()
    return f"game_task_ad_bonus:{digest}"


def _build_points_range(config: Dict[str, Any]) -> str:
    win_points = int(config.get("game_rps_win_points") or config.get("game_base_points_max") or 4)
    lose_points = int(config.get("game_rps_lose_points") or config.get("game_base_points_min") or -2)
    return f"赢+{win_points} / 平0 / 输{lose_points}"


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
    user_choice: str | None = None,
    system_choice: str | None = None,
) -> Dict[str, Any]:
    remaining = max(int(stat.game_tasks_limit) - int(stat.game_tasks_used), 0)
    estimated_points = int(round_record.base_points)
    rewarded = bool(ledger or round_record.ledger_id or int(round_record.total_points) > 0)
    return {
        "success": True,
        "game_code": round_record.game_code,
        "round_id": round_record.round_id,
        "result": round_record.result,
        "user_choice": user_choice,
        "system_choice": system_choice,
        "points_added": int(ledger.points_delta) if ledger else int(round_record.total_points),
        "base_points": estimated_points,
        "bonus_points": int(round_record.bonus_points),
        "estimated_points": estimated_points,
        "ad_required": estimated_points > 0,
        "rewarded": rewarded,
        "today_points": int(account.consumable_points),
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
        "today_points": int(account.consumable_points),
        "today_estimated_points": int(account.consumable_points),
        "today_used": int(stat.game_tasks_used),
        "today_limit": int(stat.game_tasks_limit),
        "today_remaining": remaining,
        "account": _build_account_summary(account),
        "ledger_id": str(ledger.id) if ledger else "",
        "created_at": round_record.updated_at,
    }
