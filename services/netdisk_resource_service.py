"""Netdisk resource unlock service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from models.netdisk_favorite import NetdiskFavorite
from models.netdisk_request import NetdiskRequest
from models.netdisk_upload import NetdiskUpload
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
    category: str
    pan: str
    level: ResourceLevel
    cost_points: int
    verified_at: str
    downloads: int
    favorites: int
    description: str
    link: str
    extract_code: str = ""
    unzip_code: str = ""


NETDISK_RESOURCE_CATALOG: dict[str, NetdiskResource] = {
    "r1": NetdiskResource(
        id="r1",
        title="社区团购接龙模板与群公告话术合集",
        category="自媒体素材",
        pan="夸克",
        level="featured",
        cost_points=10,
        verified_at="2小时前",
        downloads=128,
        favorites=33,
        description="包含接龙表格、群公告、促销提醒和售后沟通模板，适合社区团购日常运营。",
        link="https://pan.quark.cn/s/mock-yuexiang-r1",
        extract_code="yx10",
        unzip_code="yx2026",
    ),
    "r2": NetdiskResource(
        id="r2",
        title="Excel 进销存台账与库存预警模板",
        category="学习办公",
        pan="百度",
        level="normal",
        cost_points=5,
        verified_at="今天",
        downloads=46,
        favorites=9,
        description="适合小店、团购和仓储场景，包含库存、采购、销售和利润汇总表。",
        link="https://pan.baidu.com/s/mock-yuexiang-r2",
        extract_code="yx05",
    ),
    "r3": NetdiskResource(
        id="r3",
        title="自媒体账号运营选题库与脚本结构模板",
        category="自媒体素材",
        pan="阿里",
        level="official",
        cost_points=20,
        verified_at="昨天",
        downloads=221,
        favorites=68,
        description="覆盖账号定位、爆款拆解、脚本文案、封面标题和发布复盘表。",
        link="https://www.aliyundrive.com/s/mock-yuexiang-r3",
        extract_code="yx20",
    ),
}


class NetdiskResourceService:
    """Unlock resources by consuming points and writing idempotent ledger rows."""

    @staticmethod
    def list_resources(pan: str | None = None) -> list[dict]:
        selected_pan = (pan or "").strip()
        resources = NETDISK_RESOURCE_CATALOG.values()
        if selected_pan and selected_pan != "全部":
            resources = [resource for resource in resources if resource.pan == selected_pan]
        return [_build_resource_payload(resource) for resource in resources]

    @staticmethod
    def get_resource_detail(resource_id: str) -> dict:
        resource_key = (resource_id or "").strip()
        resource = NETDISK_RESOURCE_CATALOG.get(resource_key)
        if not resource:
            raise ValueError("resource not found")
        return _build_resource_payload(resource)

    @staticmethod
    async def get_resource_access(
        session: AsyncSession,
        user: User,
        resource_id: str,
    ) -> dict:
        resource_key = (resource_id or "").strip()
        resource = NETDISK_RESOURCE_CATALOG.get(resource_key)
        if not resource:
            raise ValueError("resource not found")

        account, _ = await PointsAccountService.ensure_user_account(session, user.id)
        ledger = await _get_unlock_ledger(session, user.id, resource.id)
        if not ledger:
            return _build_access_payload(resource, None, account)
        return _build_access_payload(resource, ledger, account)

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

    @staticmethod
    async def list_favorites(
        session: AsyncSession,
        user: User,
    ) -> dict:
        result = await session.execute(
            select(NetdiskFavorite)
            .where(NetdiskFavorite.user_id == user.id)
            .order_by(NetdiskFavorite.created_at.desc())
        )
        favorites = result.scalars().all()
        return {
            "favorites": [
                _build_favorite_payload(favorite)
                for favorite in favorites
                if favorite.resource_id in NETDISK_RESOURCE_CATALOG
            ]
        }

    @staticmethod
    async def favorite_resource(
        session: AsyncSession,
        user: User,
        resource_id: str,
    ) -> tuple[dict, bool]:
        resource = _get_resource_or_raise(resource_id)
        existing = await _get_favorite(session, user.id, resource.id)
        if existing:
            return _build_favorite_payload(existing), False

        favorite = NetdiskFavorite(user_id=user.id, resource_id=resource.id)
        session.add(favorite)
        await session.flush()
        await session.refresh(favorite)
        return _build_favorite_payload(favorite), True

    @staticmethod
    async def unfavorite_resource(
        session: AsyncSession,
        user: User,
        resource_id: str,
    ) -> dict:
        resource = _get_resource_or_raise(resource_id)
        favorite = await _get_favorite(session, user.id, resource.id)
        if favorite:
            await session.delete(favorite)
            await session.flush()

        return {"resource": _build_resource_payload(resource), "favorited": False}

    @staticmethod
    async def list_requests(session: AsyncSession, user: User | None = None) -> dict:
        result = await session.execute(
            select(NetdiskRequest).order_by(NetdiskRequest.created_at.desc()).limit(100)
        )
        items = result.scalars().all()
        user_id = user.id if user else None
        return {"requests": [_build_request_payload(item, user_id) for item in items]}

    @staticmethod
    async def list_my_requests(session: AsyncSession, user: User) -> dict:
        result = await session.execute(
            select(NetdiskRequest)
            .where(NetdiskRequest.user_id == user.id)
            .order_by(NetdiskRequest.created_at.desc())
            .limit(100)
        )
        return {"requests": [_build_request_payload(item, user.id) for item in result.scalars().all()]}

    @staticmethod
    async def create_request(
        session: AsyncSession,
        user: User,
        title: str,
        pans: list[str],
        category: str,
        bounty_points: int,
        note: str,
    ) -> dict:
        clean_title = (title or "").strip()
        clean_pans = [item.strip() for item in pans if item and item.strip()]
        clean_category = (category or "").strip()
        clean_note = (note or "").strip()
        if not clean_title:
            raise ValueError("title is required")
        if not clean_pans:
            raise ValueError("pans is required")
        if not clean_category:
            raise ValueError("category is required")

        item = NetdiskRequest(
            user_id=user.id,
            title=clean_title[:120],
            pans=" / ".join(clean_pans[:4]),
            category=clean_category[:64],
            bounty_points=max(5, min(50, int(bounty_points or 5))),
            note=clean_note[:500],
            status="open",
            deadline_text="3天后",
        )
        session.add(item)
        await session.flush()
        await session.refresh(item)
        return {"request": _build_request_payload(item, user.id)}

    @staticmethod
    async def list_my_uploads(session: AsyncSession, user: User) -> dict:
        result = await session.execute(
            select(NetdiskUpload)
            .where(NetdiskUpload.user_id == user.id)
            .order_by(NetdiskUpload.created_at.desc())
            .limit(100)
        )
        return {"uploads": [_build_upload_payload(item) for item in result.scalars().all()]}

    @staticmethod
    async def create_upload(
        session: AsyncSession,
        user: User,
        title: str,
        category: str,
        pan: str,
        link: str,
        extract_code: str,
        unzip_code: str,
        description: str,
    ) -> dict:
        clean_title = (title or "").strip()
        clean_category = (category or "").strip()
        clean_pan = (pan or "").strip()
        clean_link = (link or "").strip()
        clean_description = (description or "").strip()
        if not clean_title:
            raise ValueError("title is required")
        if not clean_category:
            raise ValueError("category is required")
        if not clean_pan:
            raise ValueError("pan is required")
        if not clean_link:
            raise ValueError("link is required")
        if not clean_description:
            raise ValueError("description is required")

        item = NetdiskUpload(
            user_id=user.id,
            title=clean_title[:120],
            category=clean_category[:64],
            pan=clean_pan[:32],
            link=clean_link[:500],
            extract_code=(extract_code or "").strip()[:64],
            unzip_code=(unzip_code or "").strip()[:64],
            description=clean_description[:800],
            status="pending",
            reward_points=5,
            audit_note="系统正在校验链接有效性和内容匹配度。",
        )
        session.add(item)
        await session.flush()
        await session.refresh(item)
        return {"upload": _build_upload_payload(item)}


async def _get_unlock_ledger(session: AsyncSession, user_id, resource_id: str) -> PointsLedger | None:
    result = await session.execute(
        select(PointsLedger).where(
            PointsLedger.user_id == user_id,
            PointsLedger.idempotency_key == f"netdisk_unlock:{user_id}:{resource_id}",
        )
    )
    return result.scalar_one_or_none()


async def _get_favorite(session: AsyncSession, user_id, resource_id: str) -> NetdiskFavorite | None:
    result = await session.execute(
        select(NetdiskFavorite).where(
            NetdiskFavorite.user_id == user_id,
            NetdiskFavorite.resource_id == resource_id,
        )
    )
    return result.scalar_one_or_none()


def _get_resource_or_raise(resource_id: str) -> NetdiskResource:
    resource_key = (resource_id or "").strip()
    resource = NETDISK_RESOURCE_CATALOG.get(resource_key)
    if not resource:
        raise ValueError("resource not found")
    return resource


def _build_resource_payload(resource: NetdiskResource) -> dict:
    return {
        "id": resource.id,
        "title": resource.title,
        "category": resource.category,
        "pan": resource.pan,
        "level": resource.level,
        "cost_points": resource.cost_points,
        "verified_at": resource.verified_at,
        "downloads": resource.downloads,
        "favorites": resource.favorites,
        "description": resource.description,
    }


def _build_favorite_payload(favorite: NetdiskFavorite) -> dict:
    resource = NETDISK_RESOURCE_CATALOG[favorite.resource_id]
    return {
        "resource": _build_resource_payload(resource),
        "favorite_at": favorite.created_at,
        "favorited": True,
    }


def _build_request_payload(item: NetdiskRequest, user_id=None) -> dict:
    return {
        "id": str(item.id),
        "title": item.title,
        "pans": item.pans,
        "category": item.category,
        "bounty_points": int(item.bounty_points),
        "note": item.note,
        "status": item.status,
        "submissions_count": int(item.submissions_count),
        "deadline_text": item.deadline_text,
        "created_at": item.created_at,
        "mine": bool(user_id and item.user_id == user_id),
    }


def _build_upload_payload(item: NetdiskUpload) -> dict:
    return {
        "id": str(item.id),
        "title": item.title,
        "category": item.category,
        "pan": item.pan,
        "status": item.status,
        "reward_points": int(item.reward_points),
        "audit_note": item.audit_note,
        "created_at": item.created_at,
    }


def _build_account_payload(account: UserAccount) -> dict:
    return {
        "total_points": int(account.total_points),
        "withdrawable_points": int(account.withdrawable_points),
        "frozen_points": int(account.frozen_points),
        "consumable_points": int(account.consumable_points),
    }


def _build_access_payload(
    resource: NetdiskResource,
    ledger: PointsLedger | None,
    account: UserAccount,
) -> dict:
    access = {
        "unlocked": bool(ledger),
        "ledger_id": str(ledger.id) if ledger else "",
        "points_delta": int(ledger.points_delta) if ledger else 0,
        "link": resource.link if ledger else "",
        "extract_code": resource.extract_code if ledger else "",
        "unzip_code": resource.unzip_code if ledger else "",
    }
    return {
        "resource": _build_resource_payload(resource),
        "access": access,
        "account": _build_account_payload(account),
    }


def _build_unlock_payload(
    resource: NetdiskResource,
    ledger: PointsLedger,
    account: UserAccount,
    invite_reward: dict | None,
) -> dict:
    return {
        "resource": _build_resource_payload(resource),
        "unlock": {
            "unlocked": True,
            "ledger_id": str(ledger.id),
            "points_delta": int(ledger.points_delta),
            "link": resource.link,
            "extract_code": resource.extract_code,
            "unzip_code": resource.unzip_code,
        },
        "account": _build_account_payload(account),
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
