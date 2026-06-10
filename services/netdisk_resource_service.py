"""Netdisk resource unlock service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlmodel.ext.asyncio.session import AsyncSession

from models.points_ledger import PointsLedger
from models.user import User
from models.user_account import UserAccount
from services.invite_reward_service import InviteRewardService
from services.points_account_service import PointsAccountService

ResourceLevel = Literal["normal", "featured", "official"]


@dataclass(frozen=True)
class NetdiskResource:
    id: str
    title: str
    pan: str
    level: ResourceLevel
    cost_points: int
    link: str
    extract_code: str = ""
    unzip_code: str = ""


NETDISK_RESOURCE_CATALOG: dict[str, NetdiskResource] = {
    "r1": NetdiskResource(
        id="r1",
        title="私域运营资料包",
        pan="夸克",
        level="featured",
        cost_points=10,
        link="https://pan.quark.cn/s/mock-yuexiang-r1",
        extract_code="yx10",
        unzip_code="yx2026",
    ),
    "r2": NetdiskResource(
        id="r2",
        title="Excel 模板合集",
        pan="百度",
        level="normal",
        cost_points=5,
        link="https://pan.baidu.com/s/mock-yuexiang-r2",
        extract_code="yx05",
    ),
    "r3": NetdiskResource(
        id="r3",
        title="官方资料合集",
        pan="阿里",
        level="official",
        cost_points=20,
        link="https://www.aliyundrive.com/s/mock-yuexiang-r3",
        extract_code="yx20",
    ),
}


class NetdiskResourceService:
    """Unlock resources by consuming points and writing idempotent ledger rows."""

    @staticmethod
    async def unlock_resource(
        session: AsyncSession,
        user: User,
        resource_id: str,
    ) -> tuple[dict, bool]:
        resource_key = (resource_id or "").strip()
        resource = NETDISK_RESOURCE_CATALOG.get(resource_key)
        if not resource:
            raise ValueError("resource not found")

        ledger, account, unlocked_now = await PointsAccountService.consume_consumable_points(
            session=session,
            user_id=user.id,
            points=resource.cost_points,
            source="netdisk",
            change_type="resource_unlock",
            idempotency_key=f"netdisk_unlock:{user.id}:{resource.id}",
            related_type="netdisk_resource",
            related_id=resource.id,
            remark=f"unlock netdisk resource: {resource.title}",
        )

        invite_reward = None
        if unlocked_now:
            reward_ledger, reward_account, reward_created = await InviteRewardService.grant_first_resource_reward(
                session=session,
                invitee_id=user.id,
                resource_id=resource.id,
            )
            invite_reward = _build_invite_reward_payload(reward_ledger, reward_account, reward_created)

        await session.flush()
        return _build_unlock_payload(resource, ledger, account, invite_reward), unlocked_now


def _build_unlock_payload(
    resource: NetdiskResource,
    ledger: PointsLedger,
    account: UserAccount,
    invite_reward: dict | None,
) -> dict:
    return {
        "resource": {
            "id": resource.id,
            "title": resource.title,
            "pan": resource.pan,
            "level": resource.level,
            "cost_points": resource.cost_points,
        },
        "unlock": {
            "unlocked": True,
            "ledger_id": str(ledger.id),
            "points_delta": int(ledger.points_delta),
            "link": resource.link,
            "extract_code": resource.extract_code,
            "unzip_code": resource.unzip_code,
        },
        "account": {
            "total_points": int(account.total_points),
            "withdrawable_points": int(account.withdrawable_points),
            "frozen_points": int(account.frozen_points),
            "consumable_points": int(account.consumable_points),
        },
        "invite_reward": invite_reward,
    }


def _build_invite_reward_payload(
    ledger: PointsLedger | None,
    account: UserAccount | None,
    created: bool,
) -> dict | None:
    if not ledger or not account:
        return None
    return {
        "created": created,
        "ledger_id": str(ledger.id),
        "points_delta": int(ledger.points_delta),
        "inviter_consumable_points": int(account.consumable_points),
    }
