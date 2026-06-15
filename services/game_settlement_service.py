"""Stage 2 daily game settlement service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import desc, func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from models.ad_event import AdEventRecord
from models.game_round import GameRound
from models.game_settlement_batch import GameSettlementBatch
from models.game_user_settlement import GameUserSettlement
from models.order import Order
from models.user import User
from services.config_service import ConfigService
from services.points_account_service import PointsAccountService

DEFAULT_SETTLEMENT_CONFIG = {
    "rolling_average_days": 7,
    "default_ecpm": 30.0,
    "normal_factor": 0.2,
    "month_factor": 0.4,
    "quarter_factor": 0.6,
    "year_factor": 0.8,
}


@dataclass
class _UserSettlementPreview:
    user: User
    membership_level: str
    factor_value: float
    estimated_points: int
    round_count: int
    ad_pv: int
    valid_clicks: int
    settled_points: int


class GameSettlementService:
    """Persist and execute daily game settlements."""

    @staticmethod
    async def get_daily_detail(session: AsyncSession, settlement_day: date) -> dict[str, Any]:
        batch = await _get_batch(session, settlement_day)
        previews = await _build_previews(session, settlement_day, batch)
        details = await _list_user_settlements(session, settlement_day)

        return {
            "settlement_date": settlement_day.isoformat(),
            "batch": _serialize_batch(batch),
            "preview": {
                "user_count": len(previews),
                "total_estimated_points": sum(item.estimated_points for item in previews),
                "total_settled_points": sum(item.settled_points for item in previews),
                "total_adjustment_points": sum(item.settled_points - item.estimated_points for item in previews),
                "users": [
                    {
                        "user_id": str(item.user.id),
                        "nickname": item.user.nickname,
                        "membership_level": item.membership_level,
                        "factor_value": item.factor_value,
                        "estimated_points": item.estimated_points,
                        "settled_points": item.settled_points,
                        "adjustment_points": item.settled_points - item.estimated_points,
                        "round_count": item.round_count,
                        "ad_pv": item.ad_pv,
                        "valid_clicks": item.valid_clicks,
                    }
                    for item in previews[:100]
                ],
            },
            "settlements": details,
        }

    @staticmethod
    async def save_daily_input(
        session: AsyncSession,
        *,
        settlement_day: date,
        ecpm_value: float | None,
        ad_pv: int | None,
        valid_clicks: int | None,
        total_revenue: float | None,
        note: str | None = None,
    ) -> dict[str, Any]:
        batch = await _get_batch(session, settlement_day)
        if not batch:
            batch = GameSettlementBatch(settlement_date=settlement_day)
            session.add(batch)

        if ecpm_value is not None:
            batch.ecpm_value = round(float(ecpm_value), 4)
            batch.ecpm_source = "manual"
        if ad_pv is not None:
            batch.ad_pv = max(int(ad_pv), 0)
        if valid_clicks is not None:
            batch.valid_clicks = max(int(valid_clicks), 0)
        if total_revenue is not None:
            batch.total_revenue = round(float(total_revenue), 4)
        if note is not None:
            batch.note = note.strip() or None
        batch.updated_at = datetime.utcnow()

        await session.flush()
        return _serialize_batch(batch)

    @staticmethod
    async def trigger_daily_settlement(
        session: AsyncSession,
        *,
        settlement_day: date,
        allow_fallback: bool = True,
        force_recalculate: bool = False,
    ) -> dict[str, Any]:
        batch = await _get_batch(session, settlement_day)
        if not batch:
            batch = GameSettlementBatch(settlement_date=settlement_day)
            session.add(batch)
            await session.flush()

        if batch.status in {"settled", "adjusted"} and not force_recalculate:
            return await GameSettlementService.get_daily_detail(session, settlement_day)

        batch.ecpm_value, batch.ecpm_source = await _resolve_batch_ecpm(
            session,
            batch,
            allow_fallback=allow_fallback,
        )
        previews = await _build_previews(session, settlement_day, batch)
        derived_ad_pv = sum(item.ad_pv for item in previews)
        derived_valid_clicks = sum(item.valid_clicks for item in previews)
        if int(batch.ad_pv) <= 0:
            batch.ad_pv = derived_ad_pv
        if int(batch.valid_clicks) <= 0:
            batch.valid_clicks = derived_valid_clicks
        if float(batch.total_revenue or 0) <= 0 and float(batch.ecpm_value or 0) > 0:
            batch.total_revenue = round((int(batch.ad_pv) * float(batch.ecpm_value or 0)) / 1000, 4)

        total_adjustment_points = 0
        settled_user_count = 0
        total_estimated_points = 0
        total_settled_points = 0

        for preview in previews:
            settled_user_count += 1
            total_estimated_points += preview.estimated_points
            total_settled_points += preview.settled_points

            existing = await _get_user_settlement(session, settlement_day, preview.user.id)
            if not existing:
                if preview.estimated_points > 0:
                    await PointsAccountService.record_neutral_event(
                        session=session,
                        user_id=preview.user.id,
                        idempotency_key=f"game_settlement_transfer:{settlement_day}:{preview.user.id}",
                        related_type="game_settlement",
                        related_id=str(batch.id),
                        remark=f"{settlement_day.isoformat()} game settlement confirmed",
                        source="game",
                        change_type="game_settlement",
                        availability="consumable",
                    )

                delta = preview.settled_points - preview.estimated_points
                if delta != 0:
                    total_adjustment_points += delta
                    await PointsAccountService.adjust_consumable_points(
                        session=session,
                        user_id=preview.user.id,
                        points_delta=delta,
                        idempotency_key=f"game_adjustment:{settlement_day}:{preview.user.id}:{preview.settled_points}",
                        related_type="game_settlement",
                        related_id=str(batch.id),
                        remark=f"{settlement_day.isoformat()} game settlement adjustment",
                        change_type="game_adjust_add" if delta > 0 else "game_adjust_sub",
                    )

                existing = GameUserSettlement(
                    batch_id=batch.id,
                    settlement_date=settlement_day,
                    user_id=preview.user.id,
                    membership_level=preview.membership_level,
                    factor_value=preview.factor_value,
                    estimated_points=preview.estimated_points,
                    settled_points=preview.settled_points,
                    adjustment_points=delta,
                    round_count=preview.round_count,
                    ad_pv=preview.ad_pv,
                    valid_clicks=preview.valid_clicks,
                    status="settled" if delta == 0 else "adjusted",
                )
                session.add(existing)
                continue

            delta = preview.settled_points - int(existing.settled_points)
            if delta != 0:
                total_adjustment_points += delta
                await PointsAccountService.adjust_consumable_points(
                    session=session,
                    user_id=preview.user.id,
                    points_delta=delta,
                    idempotency_key=f"game_adjustment:{settlement_day}:{preview.user.id}:{preview.settled_points}",
                    related_type="game_settlement",
                    related_id=str(batch.id),
                    remark=f"{settlement_day.isoformat()} game settlement rerun",
                    change_type="game_adjust_add" if delta > 0 else "game_adjust_sub",
                )

            existing.batch_id = batch.id
            existing.membership_level = preview.membership_level
            existing.factor_value = preview.factor_value
            existing.estimated_points = preview.estimated_points
            existing.settled_points = preview.settled_points
            existing.adjustment_points += delta
            existing.round_count = preview.round_count
            existing.ad_pv = preview.ad_pv
            existing.valid_clicks = preview.valid_clicks
            existing.status = "settled" if int(existing.adjustment_points) == 0 else "adjusted"
            existing.updated_at = datetime.utcnow()

        batch.settled_user_count = settled_user_count
        batch.total_estimated_points = total_estimated_points
        batch.total_settled_points = total_settled_points
        batch.total_adjustment_points += total_adjustment_points
        batch.status = "settled" if batch.total_adjustment_points == 0 else "adjusted"
        batch.settled_at = datetime.utcnow()
        batch.updated_at = datetime.utcnow()

        await session.flush()
        return await GameSettlementService.get_daily_detail(session, settlement_day)


async def _get_batch(session: AsyncSession, settlement_day: date) -> GameSettlementBatch | None:
    result = await session.execute(
        select(GameSettlementBatch).where(GameSettlementBatch.settlement_date == settlement_day)
    )
    return result.scalar_one_or_none()


async def _get_user_settlement(session: AsyncSession, settlement_day: date, user_id) -> GameUserSettlement | None:
    result = await session.execute(
        select(GameUserSettlement).where(
            GameUserSettlement.settlement_date == settlement_day,
            GameUserSettlement.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def _list_user_settlements(session: AsyncSession, settlement_day: date) -> list[dict[str, Any]]:
    stmt = (
        select(GameUserSettlement, User)
        .join(User, User.id == GameUserSettlement.user_id)
        .where(GameUserSettlement.settlement_date == settlement_day)
        .order_by(desc(GameUserSettlement.settled_points), desc(GameUserSettlement.updated_at))
    )
    result = await session.execute(stmt)
    rows = result.all()
    return [
        {
            "user_id": str(user.id),
            "nickname": user.nickname,
            "membership_level": row.membership_level,
            "factor_value": float(row.factor_value),
            "estimated_points": int(row.estimated_points),
            "settled_points": int(row.settled_points),
            "adjustment_points": int(row.adjustment_points),
            "round_count": int(row.round_count),
            "ad_pv": int(row.ad_pv),
            "valid_clicks": int(row.valid_clicks),
            "status": row.status,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
        for row, user in rows
    ]


async def _build_previews(
    session: AsyncSession,
    settlement_day: date,
    batch: GameSettlementBatch | None,
) -> list[_UserSettlementPreview]:
    rounds = await _load_rewarded_rounds(session, settlement_day)
    if not rounds:
        return []

    config = await _get_settlement_config(session)
    preview_ecpm = float(batch.ecpm_value or 0) if batch and batch.ecpm_value is not None else float(config["default_ecpm"])
    grouped: dict[Any, list[GameRound]] = {}
    for row in rounds:
        grouped.setdefault(row.user_id, []).append(row)

    user_ids = list(grouped.keys())
    users_result = await session.execute(select(User).where(User.id.in_(user_ids)))
    users = {item.id: item for item in users_result.scalars().all()}

    previews: list[_UserSettlementPreview] = []
    for user_id, user_rounds in grouped.items():
        user = users.get(user_id)
        if not user:
            continue
        membership_level = await _resolve_membership_level(session, user)
        factor_value = _get_membership_factor(config, membership_level)
        estimated_points = sum(max(int(item.total_points), 0) for item in user_rounds)
        ad_stats = await _get_user_ad_stats(session, user_id, settlement_day)
        user_pv = max(ad_stats["show_count"], len(user_rounds))
        valid_clicks = max(ad_stats["complete_count"], len(user_rounds))
        settled_points = _calculate_settled_points(
            user_pv=user_pv,
            ecpm_value=preview_ecpm,
            factor_value=factor_value,
        )
        previews.append(
            _UserSettlementPreview(
                user=user,
                membership_level=membership_level,
                factor_value=factor_value,
                estimated_points=estimated_points,
                round_count=len(user_rounds),
                ad_pv=user_pv,
                valid_clicks=valid_clicks,
                settled_points=settled_points,
            )
        )
    previews.sort(key=lambda item: (item.settled_points, item.estimated_points), reverse=True)
    return previews


async def _load_rewarded_rounds(session: AsyncSession, settlement_day: date) -> list[GameRound]:
    stmt = (
        select(GameRound)
        .where(
            GameRound.played_date == settlement_day,
            GameRound.total_points > 0,
        )
        .order_by(GameRound.user_id, GameRound.created_at)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def _get_user_ad_stats(session: AsyncSession, user_id, settlement_day: date) -> dict[str, int]:
    day_key = settlement_day.isoformat()

    show_stmt = (
        select(func.count(func.distinct(AdEventRecord.event_id)))
        .where(
            AdEventRecord.user_id == user_id,
            AdEventRecord.date_key == day_key,
            AdEventRecord.scene.in_(["game_bonus", "game_jump"]),
            AdEventRecord.event_type == "show",
        )
    )
    complete_stmt = (
        select(func.count(func.distinct(AdEventRecord.event_id)))
        .where(
            AdEventRecord.user_id == user_id,
            AdEventRecord.date_key == day_key,
            AdEventRecord.scene.in_(["game_bonus", "game_jump"]),
            (AdEventRecord.event_type == "complete") | (AdEventRecord.is_completed.is_(True)),
        )
    )
    show_result = await session.execute(show_stmt)
    complete_result = await session.execute(complete_stmt)
    return {
        "show_count": int(show_result.scalar_one() or 0),
        "complete_count": int(complete_result.scalar_one() or 0),
    }


async def _resolve_batch_ecpm(
    session: AsyncSession,
    batch: GameSettlementBatch,
    *,
    allow_fallback: bool,
) -> tuple[float, str]:
    if batch.ecpm_value is not None:
        return float(batch.ecpm_value), batch.ecpm_source or "manual"
    if not allow_fallback:
        raise ValueError("ecpm_value is required before settlement trigger")

    config = await _get_settlement_config(session)
    rolling_days = max(int(config["rolling_average_days"]), 1)
    stmt = (
        select(GameSettlementBatch)
        .where(
            GameSettlementBatch.settlement_date < batch.settlement_date,
            GameSettlementBatch.ecpm_value.is_not(None),
            GameSettlementBatch.status.in_(["settled", "adjusted"]),
        )
        .order_by(desc(GameSettlementBatch.settlement_date))
        .limit(rolling_days)
    )
    result = await session.execute(stmt)
    recent_batches = result.scalars().all()
    if recent_batches:
        average = sum(float(item.ecpm_value or 0) for item in recent_batches) / len(recent_batches)
        return round(average, 4), "rolling_average"

    ad_revenue_config = await ConfigService.get(session, "ad_revenue_settings")
    fallback_ecpm = float(ad_revenue_config.get("default_ecpm", config["default_ecpm"]) or config["default_ecpm"])
    return round(fallback_ecpm, 4), "default_revenue_config"


async def _get_settlement_config(session: AsyncSession) -> dict[str, Any]:
    config = await ConfigService.get(session, "stage2_game_settlement_config")
    return {**DEFAULT_SETTLEMENT_CONFIG, **(config or {})}


async def _resolve_membership_level(session: AsyncSession, user: User) -> str:
    if not user.is_vip:
        return "normal"
    result = await session.execute(
        select(Order)
        .where(Order.user_id == user.id, Order.status == "paid")
        .order_by(desc(Order.paid_at), desc(Order.created_at))
    )
    order = result.scalars().first()
    period = str(order.period).strip().lower() if order and order.period else "month"
    if period not in {"month", "quarter", "year"}:
        return "month"
    return period


def _get_membership_factor(config: dict[str, Any], membership_level: str) -> float:
    if membership_level == "year":
        return float(config["year_factor"])
    if membership_level == "quarter":
        return float(config["quarter_factor"])
    if membership_level == "month":
        return float(config["month_factor"])
    return float(config["normal_factor"])


def _calculate_settled_points(*, user_pv: int, ecpm_value: float, factor_value: float) -> int:
    if user_pv <= 0 or ecpm_value <= 0 or factor_value <= 0:
        return 0
    raw_points = Decimal(str(user_pv)) * Decimal(str(ecpm_value)) * Decimal("0.1") * Decimal(str(factor_value))
    return int(raw_points.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _serialize_batch(batch: GameSettlementBatch | None) -> dict[str, Any] | None:
    if not batch:
        return None
    return {
        "id": str(batch.id),
        "settlement_date": batch.settlement_date.isoformat(),
        "status": batch.status,
        "ecpm_value": float(batch.ecpm_value or 0),
        "ecpm_source": batch.ecpm_source,
        "ad_pv": int(batch.ad_pv),
        "valid_clicks": int(batch.valid_clicks),
        "total_revenue": float(batch.total_revenue or 0),
        "settled_user_count": int(batch.settled_user_count),
        "total_estimated_points": int(batch.total_estimated_points),
        "total_settled_points": int(batch.total_settled_points),
        "total_adjustment_points": int(batch.total_adjustment_points),
        "note": batch.note or "",
        "settled_at": batch.settled_at.isoformat() if batch.settled_at else None,
        "updated_at": batch.updated_at.isoformat() if batch.updated_at else None,
    }
