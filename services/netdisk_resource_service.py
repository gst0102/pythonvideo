"""Netdisk resource unlock service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Literal

from sqlalchemy import and_, func, or_
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from models.netdisk_favorite import NetdiskFavorite
from models.netdisk_repair import NetdiskRepair
from models.netdisk_request import NetdiskRequest
from models.netdisk_resource import NetdiskResource as NetdiskResourceModel
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
    async def list_resources(
        session: AsyncSession,
        keyword: str | None = None,
        pan: str | None = None,
        category: str | None = None,
        level: str | None = None,
        time: str | None = None,
        sort: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        await _ensure_seed_resources(session)

        selected_keyword = (keyword or "").strip()
        selected_pan = (pan or "").strip()
        selected_category = (category or "").strip()
        selected_level = _normalize_level(level)
        selected_time = (time or "all").strip()
        selected_sort = (sort or "latest").strip()
        current_page = max(1, int(page or 1))
        current_page_size = max(1, min(50, int(page_size or 20)))

        filters = [NetdiskResourceModel.is_active == True]  # noqa: E712
        if selected_keyword:
            keyword_like = f"%{selected_keyword}%"
            filters.append(
                or_(
                    NetdiskResourceModel.title.ilike(keyword_like),
                    NetdiskResourceModel.category.ilike(keyword_like),
                    NetdiskResourceModel.pan.ilike(keyword_like),
                    NetdiskResourceModel.level.ilike(keyword_like),
                    NetdiskResourceModel.description.ilike(keyword_like),
                )
            )
        if selected_pan and selected_pan != "全部":
            filters.append(NetdiskResourceModel.pan == selected_pan)
        if selected_category and selected_category != "全部分类":
            filters.append(NetdiskResourceModel.category == selected_category)
        if selected_level and selected_level != "all":
            filters.append(NetdiskResourceModel.level == selected_level)
        if selected_time and selected_time != "all":
            time_start = _time_filter_start(selected_time)
            if time_start:
                filters.append(NetdiskResourceModel.verified_at >= time_start)

        total_result = await session.execute(
            select(func.count()).select_from(NetdiskResourceModel).where(and_(*filters))
        )
        total = int(total_result.scalar_one() or 0)
        start = (current_page - 1) * current_page_size
        end = start + current_page_size
        result = await session.execute(
            select(NetdiskResourceModel)
            .where(and_(*filters))
            .order_by(*_resource_order_by(selected_sort))
            .offset(start)
            .limit(current_page_size)
        )
        page_items = result.scalars().all()
        return {
            "resources": [_build_resource_payload(resource) for resource in page_items],
            "total": total,
            "page": current_page,
            "page_size": current_page_size,
            "has_more": end < total,
        }

    @staticmethod
    async def get_resource_detail(session: AsyncSession, resource_id: str) -> dict:
        await _ensure_seed_resources(session)
        resource = await _get_resource_or_raise(session, resource_id)
        return _build_resource_payload(resource)

    @staticmethod
    async def get_resource_access(
        session: AsyncSession,
        user: User,
        resource_id: str,
    ) -> dict:
        await _ensure_seed_resources(session)
        resource = await _get_resource_or_raise(session, resource_id)

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
        await _ensure_seed_resources(session)
        resource = await _get_resource_or_raise(session, resource_id)

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
        resource_map = await _get_resource_map(session, [favorite.resource_id for favorite in favorites])
        return {
            "favorites": [
                _build_favorite_payload(favorite, resource_map[favorite.resource_id])
                for favorite in favorites
                if favorite.resource_id in resource_map
            ]
        }

    @staticmethod
    async def favorite_resource(
        session: AsyncSession,
        user: User,
        resource_id: str,
    ) -> tuple[dict, bool]:
        await _ensure_seed_resources(session)
        resource = await _get_resource_or_raise(session, resource_id)
        existing = await _get_favorite(session, user.id, resource.id)
        if existing:
            return _build_favorite_payload(existing, resource), False

        favorite = NetdiskFavorite(user_id=user.id, resource_id=resource.id)
        session.add(favorite)
        resource.favorites = int(resource.favorites) + 1
        await session.flush()
        await session.refresh(favorite)
        return _build_favorite_payload(favorite, resource), True

    @staticmethod
    async def unfavorite_resource(
        session: AsyncSession,
        user: User,
        resource_id: str,
    ) -> dict:
        await _ensure_seed_resources(session)
        resource = await _get_resource_or_raise(session, resource_id)
        favorite = await _get_favorite(session, user.id, resource.id)
        if favorite:
            await session.delete(favorite)
            resource.favorites = max(int(resource.favorites) - 1, 0)
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

    @staticmethod
    async def list_repairs(session: AsyncSession, user: User | None = None) -> dict:
        result = await session.execute(
            select(NetdiskRepair).order_by(NetdiskRepair.created_at.desc()).limit(100)
        )
        items = result.scalars().all()
        user_id = user.id if user else None
        return {"repairs": [_build_repair_payload(item, user_id) for item in items]}

    @staticmethod
    async def list_my_repairs(session: AsyncSession, user: User) -> dict:
        result = await session.execute(
            select(NetdiskRepair)
            .where(NetdiskRepair.user_id == user.id)
            .order_by(NetdiskRepair.created_at.desc())
            .limit(100)
        )
        return {"repairs": [_build_repair_payload(item, user.id) for item in result.scalars().all()]}

    @staticmethod
    async def create_repair(
        session: AsyncSession,
        user: User,
        resource_id: str,
        mode: str,
        pan: str,
        link: str,
        extract_code: str,
        unzip_code: str,
        note: str,
    ) -> dict:
        await _ensure_seed_resources(session)
        resource = await _get_resource_or_raise(session, resource_id)
        clean_mode = (mode or "").strip()
        clean_pan = (pan or "").strip()
        clean_link = (link or "").strip()
        clean_note = (note or "").strip()
        if clean_mode not in {"repair", "report"}:
            raise ValueError("mode must be repair or report")
        if not clean_pan:
            raise ValueError("pan is required")
        if clean_mode == "repair" and not clean_link:
            raise ValueError("link is required")
        if not clean_note:
            raise ValueError("note is required")

        reward_points = 5 if clean_mode == "repair" else 0
        item = NetdiskRepair(
            user_id=user.id,
            resource_id=resource.id,
            resource_title=resource.title,
            mode=clean_mode,
            pan=clean_pan[:32],
            link=clean_link[:500],
            extract_code=(extract_code or "").strip()[:64],
            unzip_code=(unzip_code or "").strip()[:64],
            note=clean_note[:500],
            status="pending",
            reward_points=reward_points,
            audit_note="已提交补链，等待审核。" if clean_mode == "repair" else "已提交投诉，等待核验。",
        )
        session.add(item)
        await session.flush()
        await session.refresh(item)
        return {"repair": _build_repair_payload(item, user.id)}


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


async def _get_resource_or_raise(session: AsyncSession, resource_id: str) -> NetdiskResourceModel:
    resource_key = (resource_id or "").strip()
    result = await session.execute(
        select(NetdiskResourceModel).where(
            NetdiskResourceModel.id == resource_key,
            NetdiskResourceModel.is_active == True,  # noqa: E712
        )
    )
    resource = result.scalar_one_or_none()
    if not resource:
        raise ValueError("resource not found")
    return resource


async def _get_resource_map(session: AsyncSession, resource_ids: list[str]) -> dict[str, NetdiskResourceModel]:
    clean_ids = [resource_id for resource_id in dict.fromkeys(resource_ids) if resource_id]
    if not clean_ids:
        return {}
    result = await session.execute(
        select(NetdiskResourceModel).where(
            NetdiskResourceModel.id.in_(clean_ids),
            NetdiskResourceModel.is_active == True,  # noqa: E712
        )
    )
    return {resource.id: resource for resource in result.scalars().all()}


async def _ensure_seed_resources(session: AsyncSession) -> None:
    result = await session.execute(select(func.count()).select_from(NetdiskResourceModel))
    if int(result.scalar_one() or 0) > 0:
        return

    now = datetime.utcnow()
    verified_offsets = {
        "r1": timedelta(hours=2),
        "r2": timedelta(hours=6),
        "r3": timedelta(days=1),
    }
    for resource in NETDISK_RESOURCE_CATALOG.values():
        session.add(
            NetdiskResourceModel(
                id=resource.id,
                title=resource.title,
                category=resource.category,
                pan=resource.pan,
                level=resource.level,
                cost_points=resource.cost_points,
                verified_at=now - verified_offsets.get(resource.id, timedelta(days=1)),
                downloads=resource.downloads,
                favorites=resource.favorites,
                description=resource.description,
                link=resource.link,
                extract_code=resource.extract_code,
                unzip_code=resource.unzip_code,
                is_active=True,
            )
        )
    await session.flush()


def _normalize_level(level: str | None) -> str:
    selected = (level or "").strip()
    level_map = {
        "普通": "normal",
        "精选": "featured",
        "官方": "official",
        "normal": "normal",
        "featured": "featured",
        "official": "official",
        "全部标签": "all",
        "all": "all",
    }
    return level_map.get(selected, selected)


def _time_filter_start(time_filter: str) -> datetime | None:
    now = datetime.utcnow()
    if time_filter == "today":
        return datetime.combine(now.date(), time.min)
    if time_filter == "recent":
        return now - timedelta(days=3)
    if time_filter == "week":
        return now - timedelta(days=7)
    if time_filter == "yesterday":
        return datetime.combine(now.date() - timedelta(days=1), time.min)
    return None


def _resource_order_by(sort: str):
    if sort == "hot":
        return [NetdiskResourceModel.downloads.desc(), NetdiskResourceModel.verified_at.desc()]
    if sort == "pointsAsc":
        return [NetdiskResourceModel.cost_points.asc(), NetdiskResourceModel.verified_at.desc()]
    if sort == "pointsDesc":
        return [NetdiskResourceModel.cost_points.desc(), NetdiskResourceModel.verified_at.desc()]
    return [NetdiskResourceModel.verified_at.desc(), NetdiskResourceModel.created_at.desc()]


def _format_verified_at(value) -> str:
    if not value:
        return ""
    if isinstance(value, str):
        return value
    now = datetime.utcnow()
    verified = value.replace(tzinfo=None) if getattr(value, "tzinfo", None) else value
    delta = now - verified
    if delta.total_seconds() < 3600:
        return "刚刚"
    if delta.total_seconds() < 86400:
        return f"{max(1, int(delta.total_seconds() // 3600))}小时前"
    if delta.days == 1:
        return "昨天"
    return verified.strftime("%Y-%m-%d")


def _build_resource_payload(resource: NetdiskResource | NetdiskResourceModel) -> dict:
    return {
        "id": resource.id,
        "title": resource.title,
        "category": resource.category,
        "pan": resource.pan,
        "level": resource.level,
        "cost_points": resource.cost_points,
        "verified_at": _format_verified_at(resource.verified_at),
        "downloads": resource.downloads,
        "favorites": resource.favorites,
        "description": resource.description,
    }


def _build_favorite_payload(favorite: NetdiskFavorite, resource: NetdiskResourceModel) -> dict:
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


def _build_repair_payload(item: NetdiskRepair, user_id=None) -> dict:
    return {
        "id": str(item.id),
        "resource_id": item.resource_id,
        "resource_title": item.resource_title,
        "mode": item.mode,
        "pan": item.pan,
        "status": item.status,
        "reward_points": int(item.reward_points),
        "audit_note": item.audit_note,
        "note": item.note,
        "created_at": item.created_at,
        "mine": bool(user_id and item.user_id == user_id),
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
