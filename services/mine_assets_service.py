"""Stage 2 mine/assets aggregation service."""

from __future__ import annotations

from typing import Any, Dict

from models.user import User
from services.config_service import ConfigService
from services.points_account_service import PointsAccountService
from services.task_overview_service import TaskOverviewService


class MineAssetsService:
    """Aggregate mine page assets for stage 2."""

    @staticmethod
    async def get_assets(session, user: User) -> Dict[str, Any]:
        overview = await TaskOverviewService.get_overview(session, user)
        account_model, _ = await PointsAccountService.ensure_user_account(session, user.id)
        points_config = await ConfigService.get(session, "stage2_points_config")

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
                "withdrawable_points": withdrawable_points,
                "frozen_points": int(account_model.frozen_points),
                "consumable_points": int(account_model.consumable_points),
                "convertible_amount": round(withdrawable_points / exchange_rate, 2),
                "withdrawable_amount": round(withdrawable_points / exchange_rate, 2),
            },
            "invite_summary": {
                "invite_code": user.invite_code,
                "direct_count": int(user.invite_count),
                "indirect_count": int(user.indirect_count),
                "team_count": int(user.team_count),
            },
            "quick_actions": [
                {
                    "code": "withdrawal",
                    "title": "立即提现",
                    "subtitle": f"可兑换 {round(withdrawable_points / exchange_rate, 2):.2f} 元",
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
