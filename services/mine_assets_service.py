"""Stage 2 mine/assets aggregation service."""

from __future__ import annotations

from typing import Any, Dict

from sqlalchemy import func
from sqlmodel import select

from models.netdisk_favorite import NetdiskFavorite
from models.netdisk_repair import NetdiskRepair
from models.netdisk_upload import NetdiskUpload
from models.user import User
from services.config_service import ConfigService
from services.points_account_service import PointsAccountService
from services.points_summary_service import PointsSummaryService
from services.task_overview_service import TaskOverviewService


class MineAssetsService:
    """Aggregate mine page assets for stage 2."""

    @staticmethod
    async def get_assets(session, user: User) -> Dict[str, Any]:
        overview = await TaskOverviewService.get_overview(session, user)
        account_model, _ = await PointsAccountService.ensure_user_account(session, user.id)
        points_config = await ConfigService.get(session, "stage2_points_config")
        summary = await PointsSummaryService.build_summary(session, user.id, today=overview["today"])

        exchange_rate = max(int(points_config.get("exchange_rate", 100) or 100), 1)
        display_unit = str(points_config.get("display_unit") or "积分")
        withdrawable_points = int(account_model.withdrawable_points)

        return {
            "user": overview["user"],
            "member": overview["member"],
            "account": overview["account"],
            "legacy_wallet": {
                "balance": round(float(user.balance), 2),
                "frozen_balance": round(float(user.frozen_balance), 2),
                "available_balance": round(max(float(user.balance) - float(user.frozen_balance), 0.0), 2),
                "total_income": round(float(user.total_income), 2),
                "total_withdrawn": round(float(user.total_withdrawn), 2),
            },
            "points_wallet": {
                "display_unit": display_unit,
                "exchange_rate": exchange_rate,
                "total_points": int(account_model.total_points),
                "today_estimated_points": int(summary["today_estimated_points"]),
                "yesterday_settled_points": int(summary["yesterday_settled_points"]),
                "withdrawable_points": withdrawable_points,
                "frozen_points": int(account_model.frozen_points),
                "locked_withdraw_points": int(account_model.locked_withdraw_points),
                "consumable_points": int(account_model.consumable_points),
                "withdrawn_points": int(account_model.withdrawn_points),
                "convertible_amount": round(withdrawable_points / exchange_rate, 2),
                "withdrawable_amount": round(withdrawable_points / exchange_rate, 2),
            },
            "invite_summary": {
                "invite_code": user.invite_code,
                "direct_count": int(user.invite_count),
                "indirect_count": int(user.indirect_count),
                "team_count": int(user.team_count),
            },
            "netdisk_stats": await _build_netdisk_stats(session, user, overview),
            "quick_actions": [
                {
                    "code": "withdrawal",
                    "title": "立即提现",
                    "subtitle": f"仅已结算积分可提现，当前约 {round(withdrawable_points / exchange_rate, 2):.2f} 元",
                },
                {
                    "code": "vip",
                    "title": "会员中心",
                    "subtitle": "查看互动次数和会员权益",
                },
                {
                    "code": "invite",
                    "title": "邀请好友",
                    "subtitle": f"当前邀请码 {user.invite_code}",
                },
                {
                    "code": "income",
                    "title": "我的收益",
                    "subtitle": f"累计收入 {round(float(user.total_income), 2):.2f} 元",
                },
            ],
        }


async def _build_netdisk_stats(session, user: User, overview: Dict[str, Any]) -> Dict[str, int]:
    favorite_count = await _count_rows(session, NetdiskFavorite, NetdiskFavorite.user_id == user.id)
    upload_count = await _count_rows(session, NetdiskUpload, NetdiskUpload.user_id == user.id)
    repair_count = await _count_rows(session, NetdiskRepair, NetdiskRepair.user_id == user.id)
    game_task = overview.get("game_task") or {}
    today_remaining = int(game_task.get("today_remaining") or 0)
    max_points = _resolve_max_game_points(game_task)

    return {
        "favorite_count": favorite_count,
        "upload_count": upload_count,
        "repair_count": repair_count,
        "today_can_earn": max(today_remaining * max_points, 0),
    }


async def _count_rows(session, model, condition) -> int:
    result = await session.execute(select(func.count()).select_from(model).where(condition))
    return int(result.scalar_one() or 0)


def _resolve_max_game_points(game_task: Dict[str, Any]) -> int:
    games = game_task.get("games") or []
    if not games:
        return 2
    points_range = str(games[0].get("points_range") or "1-2")
    try:
        return max(int(part) for part in points_range.split("-") if part.strip().isdigit())
    except ValueError:
        return 2
