"""Stage 2 game rewarded-ad slot selection service."""

from __future__ import annotations

import os
import random
from datetime import datetime
from typing import Any

from sqlalchemy import case, func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from models.ad_event import AdEventRecord
from models.user import User
from services.ad_analytics_service import now_keys
from services.config_service import ConfigService

DEFAULT_GAME_BONUS_AD_CONFIG: dict[str, Any] = {
    "scene": "game_bonus",
    "instances": [
        {
            "ad_code": "reward_game_01",
            "ad_unit_id": os.getenv("WX_REWARDED_AD_GAME_BONUS_1", "adunit-e66ca7039925b740"),
            "status": "active",
            "weight": 100,
            "daily_user_show_limit": 5,
            "daily_user_complete_limit": 5,
        }
    ],
}


class GameAdService:
    """Select available rewarded-ad slots for game ad bonus flow."""

    @staticmethod
    async def select_available_slot(
        session: AsyncSession,
        user: User,
        *,
        round_id: str,
    ) -> dict[str, Any]:
        normalized_round_id = round_id.strip()
        if not normalized_round_id:
            raise ValueError("round_id is required")

        config = await ConfigService.get(session, "stage2_game_bonus_ad_config")
        scene = str(config.get("scene") or DEFAULT_GAME_BONUS_AD_CONFIG["scene"]).strip() or "game_bonus"
        instances = _normalize_instances(config.get("instances"))
        if not instances:
            return {
                "available": False,
                "scene": scene,
                "message": "当前奖励广告暂不可用",
            }

        date_key, _, _ = now_keys()
        eligible: list[dict[str, Any]] = []
        for item in instances:
            counts = await _get_user_counts(session, user.id, scene, item["ad_unit_id"], date_key)
            show_limit = item.get("daily_user_show_limit")
            complete_limit = item.get("daily_user_complete_limit")
            if show_limit is not None and counts["show_count"] >= int(show_limit):
                continue
            if complete_limit is not None and counts["complete_count"] >= int(complete_limit):
                continue
            eligible.append(item)

        if not eligible:
            return {
                "available": False,
                "scene": scene,
                "message": "今日广告加倍次数已用完",
            }

        selected = _weighted_choice(eligible)
        event_id = f"{scene}:{normalized_round_id}:{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
        return {
            "available": True,
            "scene": scene,
            "ad_event_id": event_id,
            "ad_unit_id": selected["ad_unit_id"],
            "ad_code": selected["ad_code"],
            "daily_user_show_limit": selected.get("daily_user_show_limit"),
            "daily_user_complete_limit": selected.get("daily_user_complete_limit"),
        }


def _normalize_instances(raw_instances: Any) -> list[dict[str, Any]]:
    instances = raw_instances if isinstance(raw_instances, list) and raw_instances else DEFAULT_GAME_BONUS_AD_CONFIG["instances"]
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(instances):
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "active").strip().lower()
        ad_unit_id = str(item.get("ad_unit_id") or "").strip()
        if status != "active" or not ad_unit_id:
            continue
        normalized.append(
            {
                "ad_code": str(item.get("ad_code") or f"reward_game_{index + 1:02d}").strip(),
                "ad_unit_id": ad_unit_id,
                "status": status,
                "weight": max(int(item.get("weight") or 1), 1),
                "daily_user_show_limit": _normalize_optional_positive_int(item.get("daily_user_show_limit")),
                "daily_user_complete_limit": _normalize_optional_positive_int(item.get("daily_user_complete_limit")),
            }
        )
    return normalized


def _normalize_optional_positive_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    normalized = int(value)
    return normalized if normalized > 0 else None


async def _get_user_counts(
    session: AsyncSession,
    user_id,
    scene: str,
    ad_unit_id: str,
    date_key: str,
) -> dict[str, int]:
    stmt = select(
        func.coalesce(func.sum(case((AdEventRecord.event_type == "show", 1), else_=0)), 0),
        func.coalesce(func.sum(case((AdEventRecord.event_type == "complete", 1), else_=0)), 0),
    ).where(
        AdEventRecord.user_id == user_id,
        AdEventRecord.scene == scene,
        AdEventRecord.ad_unit_id == ad_unit_id,
        AdEventRecord.date_key == date_key,
    )
    result = await session.execute(stmt)
    row = result.one()
    return {
        "show_count": int(row[0] or 0),
        "complete_count": int(row[1] or 0),
    }


def _weighted_choice(items: list[dict[str, Any]]) -> dict[str, Any]:
    total_weight = sum(int(item["weight"]) for item in items)
    pick = random.uniform(0, float(total_weight))
    cursor = 0.0
    for item in items:
        cursor += float(item["weight"])
        if pick <= cursor:
            return item
    return items[-1]
