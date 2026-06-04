"""Stage 2 home overview aggregation service."""

from __future__ import annotations

from typing import Any, Dict

from models.user import User
from services.task_overview_service import TaskOverviewService


class HomeOverviewService:
    """Aggregate home page overview data for stage 2."""

    @staticmethod
    async def get_overview(session, user: User) -> Dict[str, Any]:
        overview = await TaskOverviewService.get_overview(session, user)
        checkin = overview["checkin"]
        game_task = overview["game_task"]
        account = overview["account"]

        return {
            "today": overview["today"],
            "user": overview["user"],
            "member": overview["member"],
            "account": account,
            "welfare_card": {
                "checked_in": bool(checkin["checked_in"]),
                "continuous_days": int(checkin["continuous_days"]),
                "total_points": int(account["total_points"]),
                "today_points": int(overview["today_points"]),
                "game_remaining": int(game_task["today_remaining"]),
                "game_limit": int(game_task["today_limit"]),
                "next_checkin_points": int(checkin["total_points"]),
            },
            "checkin": checkin,
            "game_task": game_task,
            "quick_entries": [
                {
                    "code": "anime",
                    "title": "影视福利",
                    "subtitle": "追更提醒和片库入口",
                },
                {
                    "code": "game",
                    "title": "互动任务",
                    "subtitle": f"今日剩余 {int(game_task['today_remaining'])} 次",
                },
                {
                    "code": "invite",
                    "title": "邀请好友",
                    "subtitle": "邀请解锁更多权益",
                    "badge": user.invite_code,
                },
            ],
        }
