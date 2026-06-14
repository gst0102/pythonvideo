"""Netdisk resource unlock service."""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy import and_, func, or_, text, update as sql_update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from models.netdisk_favorite import NetdiskFavorite
from models.netdisk_feedback import NetdiskFeedback
from models.netdisk_collected_resource import NetdiskCollectedResource
from models.netdisk_repair import NetdiskRepair
from models.netdisk_request import NetdiskRequest
from models.netdisk_resource import NetdiskResource as NetdiskResourceModel
from models.netdisk_risk_record import NetdiskRiskRecord
from models.netdisk_upload import NetdiskUpload
from models.netdisk_user_notification import NetdiskUserNotification
from models.points_ledger import PointsLedger
from models.user import User
from models.user_quality_profile import UserQualityProfile
from models.user_account import UserAccount
from services.invite_reward_service import InviteRewardService
from services.config_service import ConfigService
from services.points_account_service import PointsAccountService
from services.resource_classification_service import ClassificationResult, media_level_and_cost, normalize_resource_title

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
        await _attach_resource_quality_labels(session, page_items)
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
        await _attach_resource_quality_labels(session, [resource])
        return _build_resource_payload(resource)

    @staticmethod
    async def get_resource_access(
        session: AsyncSession,
        user: User,
        resource_id: str,
    ) -> dict:
        await _ensure_seed_resources(session)
        resource = await _get_resource_or_raise(session, resource_id)
        await _attach_resource_quality_labels(session, [resource])

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
        await _attach_resource_quality_labels(session, [resource])

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
        creator_reward = None
        platform_recovered_points = 0
        if unlocked_now:
            resource.downloads = int(resource.downloads) + 1
            reward_ledger, reward_account, reward_created = await InviteRewardService.grant_first_resource_reward(
                session=session,
                invitee_id=user.id,
                resource_id=resource.id,
            )
            invite_reward = _build_invite_reward_payload(reward_ledger, reward_account, reward_created)
            creator_reward, platform_recovered_points = await _grant_creator_share_for_unlock(
                session=session,
                resource=resource,
                unlock_user=user,
            )
            resource.quality_score = await _calculate_resource_quality_score_with_profile(session, resource)

        await session.flush()
        return _build_unlock_payload(resource, ledger, account, invite_reward, creator_reward, platform_recovered_points), unlocked_now

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
        await _attach_resource_quality_labels(session, list(resource_map.values()))
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
        bounty = max(5, min(50, int(bounty_points or 5)))
        if not clean_title:
            raise ValueError("请填写需求标题")
        if not clean_pans:
            raise ValueError("请选择期望网盘")
        if not clean_category:
            raise ValueError("请选择内容分类")
        await _ensure_user_not_negative(session, user, "当前积分为负，暂不能发布悬赏")
        account, _ = await PointsAccountService.ensure_user_account(session, user.id)
        if int(account.consumable_points) < bounty:
            raise ValueError("可用积分不足，无法发布悬赏")

        item = NetdiskRequest(
            user_id=user.id,
            title=clean_title[:120],
            pans=" / ".join(clean_pans[:4]),
            category=clean_category[:64],
            bounty_points=bounty,
            note=clean_note[:500],
            status="open",
            bounty_status="frozen",
            deadline_text="3天后",
            expires_at=datetime.utcnow() + timedelta(days=3),
        )
        session.add(item)
        await session.flush()
        await PointsAccountService.freeze_consumable_points(
            session=session,
            user_id=user.id,
            points=bounty,
            idempotency_key=f"request_bounty_freeze:{item.id}",
            related_type="netdisk_request",
            related_id=str(item.id),
            remark=f"发布求资源悬赏冻结：{item.title}",
        )
        await session.refresh(item)
        return {"request": _build_request_payload(item, user.id)}

    @staticmethod
    async def list_request_submissions(session: AsyncSession, user: User, request_id: str) -> dict:
        request = await _get_request_by_id(session, request_id)
        if not request:
            raise ValueError("悬赏不存在")
        if request.user_id == user.id:
            stmt = select(NetdiskUpload).where(NetdiskUpload.request_id == request.id)
        else:
            stmt = select(NetdiskUpload).where(NetdiskUpload.request_id == request.id, NetdiskUpload.user_id == user.id)
        result = await session.execute(stmt.order_by(NetdiskUpload.created_at.desc()).limit(100))
        return {"submissions": [_build_upload_payload(item) for item in result.scalars().all()]}

    @staticmethod
    async def accept_request_submission(
        session: AsyncSession,
        user: User,
        request_id: str,
        upload_id: str,
    ) -> dict:
        request = await _get_request_by_id(session, request_id, for_update=True)
        if not request:
            raise ValueError("悬赏不存在")
        if request.user_id != user.id:
            raise ValueError("只能采纳自己发布的悬赏")
        if request.status != "open" or request.bounty_status != "frozen":
            raise ValueError("该悬赏已处理，不能重复采纳")

        upload = await _get_upload_by_id(session, upload_id)
        if not upload or upload.request_id != request.id:
            raise ValueError("投稿不存在")
        if upload.user_id == user.id:
            raise ValueError("不能采纳自己的投稿")

        now = datetime.utcnow()
        request.status = "accepted"
        request.bounty_status = "paid"
        request.accepted_upload_id = upload.id
        request.accepted_at = now
        request.closed_at = now
        request.updated_at = now
        upload.accepted_at = now
        upload.status = "approved"
        upload.audit_note = "悬赏发布者已采纳，悬赏积分已到账。"
        upload.updated_at = now

        await PointsAccountService.award_frozen_bounty_to_user(
            session=session,
            payer_user_id=request.user_id,
            receiver_user_id=upload.user_id,
            points=int(request.bounty_points),
            idempotency_key=f"request_bounty_award:{request.id}",
            related_type="netdisk_request",
            related_id=str(request.id),
            remark=f"求资源悬赏采纳：{request.title}",
        )
        await session.flush()
        await session.refresh(request)
        return {"request": _build_request_payload(request, user.id)}

    @staticmethod
    async def cancel_request(session: AsyncSession, user: User, request_id: str) -> dict:
        request = await _get_request_by_id(session, request_id, for_update=True)
        if not request:
            raise ValueError("悬赏不存在")
        if request.user_id != user.id:
            raise ValueError("只能取消自己发布的悬赏")
        if request.status != "open" or request.bounty_status != "frozen":
            raise ValueError("该悬赏已处理，不能取消")

        await _return_request_bounty(session, request, status="canceled", remark_prefix="取消求资源悬赏退回")
        await session.refresh(request)
        return {"request": _build_request_payload(request, user.id)}

    @staticmethod
    async def expire_requests(session: AsyncSession) -> dict:
        now = datetime.utcnow()
        result = await session.execute(
            select(NetdiskRequest)
            .where(
                NetdiskRequest.status == "open",
                NetdiskRequest.bounty_status == "frozen",
                NetdiskRequest.expires_at <= now,
            )
            .order_by(NetdiskRequest.expires_at.asc())
            .limit(100)
        )
        expired_count = 0
        returned_points = 0
        for item in result.scalars().all():
            await _return_request_bounty(session, item, status="expired", remark_prefix="求资源悬赏过期退回")
            expired_count += 1
            returned_points += int(item.bounty_points)
        return {"expired_count": expired_count, "returned_points": returned_points}

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
        request_id: str | None = None,
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
        await _ensure_user_can_upload(session, user)

        request = None
        if request_id:
            request = await _get_request_by_id(session, request_id, for_update=True)
            if not request:
                raise ValueError("悬赏不存在")
            if request.status != "open" or request.bounty_status != "frozen":
                raise ValueError("该悬赏已结束，不能投稿")
            if request.user_id == user.id:
                raise ValueError("不能给自己发布的悬赏投稿")
            existing_result = await session.execute(
                select(NetdiskUpload).where(
                    NetdiskUpload.request_id == request.id,
                    NetdiskUpload.user_id == user.id,
                    NetdiskUpload.status != "rejected",
                )
            )
            if existing_result.scalar_one_or_none():
                raise ValueError("你已提交过该悬赏")

        config = await _get_netdisk_audit_config(session)
        item = NetdiskUpload(
            user_id=user.id,
            request_id=request.id if request else None,
            title=clean_title[:120],
            category=clean_category[:64],
            pan=clean_pan[:32],
            link=clean_link[:500],
            extract_code=(extract_code or "").strip()[:64],
            unzip_code=(unzip_code or "").strip()[:64],
            description=clean_description[:800],
            status="pending",
            reward_points=int(config["upload_reward_points"]),
            reward_released_points=0,
            valid_days_rewarded=0,
            audit_note=(
                f"上传有效资源最高得{int(config['upload_reward_points'])}分；"
                f"审核通过先得{int(config['upload_approved_points'])}分，链接有效满7天再得{int(config['upload_valid_7d_points'])}分。"
            ),
        )
        if request:
            item.reward_points = 0
            item.audit_note = "已提交给悬赏发布者，等待采纳。"
            request.submissions_count = int(request.submissions_count) + 1
            request.updated_at = datetime.utcnow()
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

        config = await _get_netdisk_audit_config(session)
        reward_points = _repair_reward_for_resource(resource, config) if clean_mode == "repair" else 0
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
            audit_note=(
                "已记录待验证奖励，验证通过后释放为可用积分。"
                if clean_mode == "repair"
                else "已提交投诉，等待核验。"
            ),
        )
        session.add(item)
        await session.flush()
        await _grant_repair_frozen_reward(session, user, item)
        if clean_mode == "report" and config["auto_hide_on_report"]:
            resource.report_count = int(getattr(resource, "report_count", 0) or 0) + 1
            resource.quality_score = _calculate_resource_quality_score(resource)
            await _hide_resource_after_report_threshold(session, resource.id, int(config["report_hide_threshold"]))
        await session.refresh(item)
        return {"repair": _build_repair_payload(item, user.id)}

    @staticmethod
    async def list_my_feedbacks(session: AsyncSession, user: User) -> dict:
        result = await session.execute(
            select(NetdiskFeedback)
            .where(NetdiskFeedback.user_id == user.id)
            .order_by(NetdiskFeedback.created_at.desc())
            .limit(100)
        )
        return {"feedbacks": [_build_feedback_payload(item, user.id) for item in result.scalars().all()]}

    @staticmethod
    async def create_feedback(
        session: AsyncSession,
        user: User,
        feedback_type: str,
        content: str,
        contact: str = "",
    ) -> dict:
        clean_type = (feedback_type or "").strip()
        clean_content = (content or "").strip()
        clean_contact = (contact or "").strip()
        if clean_type not in {"resource", "points", "feature"}:
            raise ValueError("feedback type is invalid")
        if not clean_content:
            raise ValueError("content is required")

        item = NetdiskFeedback(
            user_id=user.id,
            feedback_type=clean_type,
            content=clean_content[:800],
            contact=clean_contact[:120],
            status="pending",
            auto_reply="已收到，后台会尽快处理。",
        )
        session.add(item)
        await session.flush()
        await session.refresh(item)
        return {"feedback": _build_feedback_payload(item, user.id)}

    @staticmethod
    async def list_admin_feedbacks(
        session: AsyncSession,
        status: str | None = None,
        feedback_type: str | None = None,
        feedback_id: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        query = select(NetdiskFeedback)
        if feedback_id:
            try:
                query = query.where(NetdiskFeedback.id == UUID(feedback_id))
            except ValueError:
                return _build_admin_list_payload("feedbacks", [], 0, page, page_size)
        if status:
            query = query.where(NetdiskFeedback.status == status)
        if feedback_type:
            query = query.where(NetdiskFeedback.feedback_type == feedback_type)

        total = (await session.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
        items = (
            await session.execute(
                query.order_by(NetdiskFeedback.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()
        return _build_admin_list_payload("feedbacks", [_build_feedback_payload(item) for item in items], total, page, page_size)

    @staticmethod
    async def update_admin_feedback(
        session: AsyncSession,
        feedback_id: str,
        status: str | None = None,
        admin_reply: str = "",
    ) -> dict:
        try:
            feedback_uuid = UUID(feedback_id)
        except ValueError as exc:
            raise ValueError("feedback not found") from exc

        item = await session.get(NetdiskFeedback, feedback_uuid)
        if not item:
            raise ValueError("feedback not found")
        if status:
            clean_status = status.strip()
            if clean_status not in {"pending", "processing", "resolved", "rejected"}:
                raise ValueError("feedback status is invalid")
            item.status = clean_status
        if admin_reply:
            item.admin_reply = admin_reply.strip()[:800]
        item.updated_at = datetime.utcnow()
        await session.flush()
        await session.refresh(item)
        return {"feedback": _build_feedback_payload(item)}

    @staticmethod
    async def list_admin_collected_resources(
        session: AsyncSession,
        status: str | None = "pending",
        bucket: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        query = select(NetdiskCollectedResource)
        if status and status != "all":
            query = query.where(NetdiskCollectedResource.status == status)
        clean_bucket = (bucket or "all").strip()
        if clean_bucket == "low_confidence":
            query = query.where(
                or_(
                    NetdiskCollectedResource.ingest_action == "review_required",
                    NetdiskCollectedResource.confidence < 75,
                )
            )
        elif clean_bucket == "duplicate":
            query = query.where(NetdiskCollectedResource.duplicate_status.in_(["same_link", "same_title_same_pan"]))
        elif clean_bucket == "supplement":
            query = query.where(NetdiskCollectedResource.duplicate_status == "supplement_pan")
        if keyword and keyword.strip():
            kw = f"%{keyword.strip()}%"
            query = query.where(
                or_(
                    NetdiskCollectedResource.title.ilike(kw),
                    NetdiskCollectedResource.category.ilike(kw),
                    NetdiskCollectedResource.pan.ilike(kw),
                    NetdiskCollectedResource.normalized_title.ilike(kw),
                )
            )

        total = (await session.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
        items = (
            await session.execute(
                query.order_by(NetdiskCollectedResource.updated_at.desc(), NetdiskCollectedResource.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()
        return _build_admin_list_payload("collected_resources", [_build_collected_payload(item) for item in items], total, page, page_size)

    @staticmethod
    async def handle_admin_collected_resource(
        session: AsyncSession,
        candidate_id: str,
        action: Literal["approve", "skip", "merge"],
        note: str = "",
    ) -> dict:
        try:
            item_id = UUID(candidate_id)
        except ValueError as exc:
            raise ValueError("采集候选不存在") from exc

        item = await session.get(NetdiskCollectedResource, item_id)
        if not item:
            raise ValueError("采集候选不存在")
        if item.status not in {"pending", "skipped"} and action != "skip":
            return {"candidate": _build_collected_payload(item), "resource": None, "message": "该候选已处理"}

        if action == "skip":
            item.status = "skipped"
            item.ingest_action = "skip_duplicate" if item.duplicate_status != "none" else "manual_skip"
            item.error = (note or "运营跳过").strip()[:300]
            item.updated_at = datetime.utcnow()
            await session.flush()
            await session.refresh(item)
            return {"candidate": _build_collected_payload(item), "resource": None, "message": "已跳过"}

        same_link = await _get_resource_by_link(session, item.link)
        if same_link:
            item.status = "merged" if action == "merge" else "skipped"
            item.ingest_action = "merge_existing_link" if action == "merge" else "skip_duplicate"
            item.error = (note or "同链接资源已存在").strip()[:300]
            item.updated_at = datetime.utcnow()
            await session.flush()
            await session.refresh(item)
            return {"candidate": _build_collected_payload(item), "resource": _build_resource_payload(same_link), "message": "同链接已存在，未重复入库"}

        if action == "approve" and item.duplicate_status in {"same_title_same_pan"}:
            raise ValueError("同标题同网盘疑似重复，请跳过或合并")

        classification = ClassificationResult(
            category=item.category,
            tags=_parse_json_list(item.tags),
            confidence=int(item.confidence or 0),
            used_deepseek=False,
        )
        resource = await _publish_collected_candidate(session, item, classification, action)
        item.status = "merged" if action == "merge" else "published"
        item.ingest_action = "manual_merge" if action == "merge" else "manual_publish"
        item.error = (note or "").strip()[:300]
        item.updated_at = datetime.utcnow()
        await session.flush()
        await session.refresh(item)
        await session.refresh(resource)
        return {"candidate": _build_collected_payload(item), "resource": _build_resource_payload(resource), "message": "已入库"}

    @staticmethod
    async def list_admin_uploads(
        session: AsyncSession,
        status: str | None = None,
        upload_id: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        query = select(NetdiskUpload)
        if upload_id:
            try:
                query = query.where(NetdiskUpload.id == UUID(upload_id))
            except ValueError:
                return _build_admin_list_payload("uploads", [], 0, page, page_size)
        if status:
            query = query.where(NetdiskUpload.status == status)

        total = (await session.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
        items = (
            await session.execute(
                query.order_by(NetdiskUpload.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()
        return _build_admin_list_payload("uploads", [_build_upload_payload(item) for item in items], total, page, page_size)

    @staticmethod
    async def list_admin_repairs(
        session: AsyncSession,
        status: str | None = None,
        mode: str | None = None,
        repair_id: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        query = select(NetdiskRepair)
        if repair_id:
            try:
                query = query.where(NetdiskRepair.id == UUID(repair_id))
            except ValueError:
                return _build_admin_list_payload("repairs", [], 0, page, page_size)
        if status:
            query = query.where(NetdiskRepair.status == status)
        if mode:
            query = query.where(NetdiskRepair.mode == mode)

        total = (await session.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
        items = (
            await session.execute(
                query.order_by(NetdiskRepair.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()
        return _build_admin_list_payload("repairs", [_build_repair_payload(item) for item in items], total, page, page_size)

    @staticmethod
    async def approve_upload(
        session: AsyncSession,
        upload_id: str,
        note: str = "",
        resource_level: str | None = None,
        cost_points: int | None = None,
    ) -> dict:
        item = await _get_upload_or_raise(session, upload_id)
        if item.status in {"rejected", "invalid_confirmed", "deleted", "canceled"}:
            raise ValueError(f"upload is already {item.status}")

        level, cost = _normalize_resource_level_and_cost(resource_level, cost_points)
        previous_status = item.status
        item.status = "approved"
        item.audit_note = note.strip() or f"系统验证通过，资源等级为{_resource_level_label(level)}，解锁消耗 {cost} 积分。"
        item.updated_at = datetime.utcnow()
        await _release_upload_approved_reward(session, item)
        resource = await _ensure_resource_from_upload(session, item, level, cost)
        await _adjust_quality_profile(
            session,
            item.user_id,
            credit_delta=1,
            contribution_delta=5,
            idempotency_key=f"netdisk_upload_quality_approved:{item.id}",
            related_type="netdisk_upload",
            related_id=str(item.id),
            remark=f"上传资源审核通过：{item.title}",
        )
        resource.quality_score = await _calculate_resource_quality_score_with_profile(session, resource)
        if previous_status != "approved":
            await _create_user_notification(
                session=session,
                user_id=item.user_id,
                notice_type="netdisk_upload_approved",
                title="上传审核通过",
                content=(
                    f"你上传的资源「{item.title}」已通过审核，等级为{_resource_level_label(level)}，解锁消耗 {cost} 积分；"
                    f"审核通过奖励已发放，链接有效满7天后可继续获得奖励。"
                ),
                related_type="netdisk_upload",
                related_id=str(item.id),
            )
        await session.flush()
        await session.refresh(item)
        return {"upload": _build_upload_payload(item), "resource": _build_resource_payload(resource)}

    @staticmethod
    async def reject_upload(session: AsyncSession, upload_id: str, note: str = "") -> dict:
        item = await _get_upload_or_raise(session, upload_id)
        if item.status == "approved":
            raise ValueError("approved upload cannot be rejected; confirm invalid instead")
        if item.status != "rejected":
            item.status = "rejected"
            item.audit_note = note.strip() or "系统审核未通过，待验证奖励已扣回。"
            item.updated_at = datetime.utcnow()
            await _clawback_upload_reward(session, item, "upload_reward_rejected")
            await _create_user_notification(
                session=session,
                user_id=item.user_id,
                notice_type="netdisk_upload_rejected",
                title="上传审核未通过",
                content=f"你上传的资源「{item.title}」未通过审核，待验证奖励不会释放。原因：{item.audit_note}",
                related_type="netdisk_upload",
                related_id=str(item.id),
            )
        await session.flush()
        await session.refresh(item)
        return {"upload": _build_upload_payload(item)}

    @staticmethod
    async def confirm_upload_invalid(session: AsyncSession, upload_id: str, note: str = "") -> dict:
        item = await _get_upload_or_raise(session, upload_id)
        if item.status != "invalid_confirmed":
            item.status = "invalid_confirmed"
            item.audit_note = note.strip() or "资源确认失效，奖励已扣回或处罚。"
            item.updated_at = datetime.utcnow()
            await _clawback_upload_reward(session, item, "upload_reward_invalid")
            await _create_user_notification(
                session=session,
                user_id=item.user_id,
                notice_type="netdisk_upload_invalid",
                title="上传资源确认失效",
                content=f"你上传的资源「{item.title}」已被确认失效，奖励将按规则扣回或进入待追缴。",
                related_type="netdisk_upload",
                related_id=str(item.id),
            )
        await session.flush()
        await session.refresh(item)
        return {"upload": _build_upload_payload(item)}

    @staticmethod
    async def approve_repair(session: AsyncSession, repair_id: str, note: str = "") -> dict:
        item = await _get_repair_or_raise(session, repair_id)
        if item.status in {"rejected", "invalid_confirmed", "deleted", "canceled"}:
            raise ValueError(f"repair is already {item.status}")

        previous_status = item.status
        item.status = "approved"
        item.audit_note = note.strip() or (
            "系统验证通过，待验证奖励已释放为可用积分。"
            if item.mode == "repair"
            else "投诉已核验通过。"
        )
        item.updated_at = datetime.utcnow()
        if item.mode == "repair":
            await _release_repair_reward(session, item)
            resource = await session.get(NetdiskResourceModel, item.resource_id)
            if resource:
                resource.is_active = True
                resource.verified_at = datetime.utcnow()
                resource.updated_at = datetime.utcnow()
                resource.quality_score = await _calculate_resource_quality_score_with_profile(session, resource)
            await _adjust_quality_profile(
                session,
                item.user_id,
                credit_delta=1,
                contribution_delta=5,
                idempotency_key=f"netdisk_repair_quality_approved:{item.id}",
                related_type="netdisk_repair",
                related_id=str(item.id),
                remark=f"补链审核通过：{item.resource_title}",
            )
        if previous_status != "approved":
            await _create_user_notification(
                session=session,
                user_id=item.user_id,
                notice_type="netdisk_repair_approved" if item.mode == "repair" else "netdisk_report_approved",
                title="补链审核通过" if item.mode == "repair" else "投诉核验通过",
                content=(
                    f"你提交的「{item.resource_title}」补链已通过审核，待验证奖励已释放为可用积分。"
                    if item.mode == "repair"
                    else f"你提交的「{item.resource_title}」投诉已核验通过，资源已进入处理流程。"
                ),
                related_type="netdisk_repair",
                related_id=str(item.id),
            )
        await session.flush()
        await session.refresh(item)
        return {"repair": _build_repair_payload(item)}

    @staticmethod
    async def reject_repair(session: AsyncSession, repair_id: str, note: str = "") -> dict:
        item = await _get_repair_or_raise(session, repair_id)
        if item.status == "approved" and item.mode == "repair":
            raise ValueError("approved repair cannot be rejected; confirm invalid instead")
        if item.status != "rejected":
            item.status = "rejected"
            item.audit_note = note.strip() or (
                "补链审核未通过，待验证奖励已扣回。"
                if item.mode == "repair"
                else "投诉未通过核验。"
            )
            item.updated_at = datetime.utcnow()
            if item.mode == "repair":
                await _clawback_repair_reward(session, item, "repair_reward_rejected")
            elif item.mode == "report":
                await _restore_resource_if_report_below_threshold(session, item.resource_id)
            await _create_user_notification(
                session=session,
                user_id=item.user_id,
                notice_type="netdisk_repair_rejected" if item.mode == "repair" else "netdisk_report_rejected",
                title="补链审核未通过" if item.mode == "repair" else "投诉未通过核验",
                content=(
                    f"你提交的「{item.resource_title}」补链未通过审核，待验证奖励不会释放。原因：{item.audit_note}"
                    if item.mode == "repair"
                    else f"你提交的「{item.resource_title}」投诉未通过核验。原因：{item.audit_note}"
                ),
                related_type="netdisk_repair",
                related_id=str(item.id),
            )
        await session.flush()
        await session.refresh(item)
        return {"repair": _build_repair_payload(item)}

    @staticmethod
    async def confirm_repair_invalid(session: AsyncSession, repair_id: str, note: str = "") -> dict:
        item = await _get_repair_or_raise(session, repair_id)
        if item.status != "invalid_confirmed":
            item.status = "invalid_confirmed"
            item.audit_note = note.strip() or (
                "补链确认失效，奖励已扣回或处罚。"
                if item.mode == "repair"
                else "投诉确认有效，资源已隐藏等待处理。"
            )
            item.updated_at = datetime.utcnow()
            result = await session.execute(select(NetdiskResourceModel).where(NetdiskResourceModel.id == item.resource_id))
            resource = result.scalar_one_or_none()
            if not resource:
                raise ValueError("resource not found")
            resource.is_active = False
            resource.updated_at = datetime.utcnow()
            if item.mode == "repair":
                await _clawback_repair_reward(session, item, "repair_reward_invalid")
            await _create_user_notification(
                session=session,
                user_id=item.user_id,
                notice_type="netdisk_repair_invalid" if item.mode == "repair" else "netdisk_report_confirmed",
                title="补链确认失效" if item.mode == "repair" else "投诉确认有效",
                content=(
                    f"你补链的资源「{item.resource_title}」已确认失效，奖励将按规则扣回或进入待追缴。"
                    if item.mode == "repair"
                    else f"你投诉的资源「{item.resource_title}」已确认失效，资源已隐藏等待处理。"
                ),
                related_type="netdisk_repair",
                related_id=str(item.id),
            )
        await session.flush()
        await session.refresh(item)
        return {"repair": _build_repair_payload(item)}

    @staticmethod
    async def restore_resource(session: AsyncSession, resource_id: str, note: str = "") -> dict:
        result = await session.execute(select(NetdiskResourceModel).where(NetdiskResourceModel.id == resource_id))
        resource = result.scalar_one_or_none()
        if not resource:
            raise ValueError("resource not found")

        resource.is_active = True
        resource.updated_at = datetime.utcnow()
        await session.flush()
        await session.refresh(resource)
        return {"resource": _build_resource_payload(resource), "note": note.strip()}

    @staticmethod
    async def restore_hidden_kdocs_resources(session: AsyncSession, note: str = "") -> dict:
        before = (
            await session.execute(
                text(
                    """
                    SELECT
                        count(*) AS total,
                        count(*) FILTER (WHERE is_active) AS active,
                        count(DISTINCT lower(coalesce(nullif(link, ''), id))) AS unique_links
                    FROM netdisk_resources
                    WHERE source_type = 'kdocs' OR source_upload_id LIKE 'kdocs:%'
                    """
                )
            )
        ).mappings().one()

        result = await session.execute(
            text(
                """
                WITH ranked AS (
                    SELECT
                        id,
                        row_number() OVER (
                            PARTITION BY lower(coalesce(nullif(link, ''), id))
                            ORDER BY
                                is_active DESC,
                                (source_type = 'kdocs') DESC,
                                verified_at DESC NULLS LAST,
                                updated_at DESC NULLS LAST,
                                created_at DESC NULLS LAST,
                                id ASC
                        ) AS rn
                    FROM netdisk_resources
                    WHERE source_type = 'kdocs' OR source_upload_id LIKE 'kdocs:%'
                ),
                updated AS (
                    UPDATE netdisk_resources AS resource
                    SET
                        is_active = (ranked.rn = 1),
                        source_type = 'kdocs',
                        updated_at = now()
                    FROM ranked
                    WHERE resource.id = ranked.id
                      AND (
                        resource.is_active IS DISTINCT FROM (ranked.rn = 1)
                        OR resource.source_type IS DISTINCT FROM 'kdocs'
                      )
                    RETURNING resource.id
                )
                SELECT count(*) AS updated_count FROM updated
                """
            )
        )
        updated_count = int(result.scalar_one() or 0)
        await session.flush()
        after = (
            await session.execute(
                text(
                    """
                    SELECT
                        count(*) AS total,
                        count(*) FILTER (WHERE is_active) AS active,
                        count(*) FILTER (WHERE NOT is_active) AS hidden_duplicates,
                        count(DISTINCT lower(coalesce(nullif(link, ''), id))) AS unique_links
                    FROM netdisk_resources
                    WHERE source_type = 'kdocs' OR source_upload_id LIKE 'kdocs:%'
                    """
                )
            )
        ).mappings().one()
        return {
            "candidate_count": int(before["total"] or 0),
            "active_before": int(before["active"] or 0),
            "unique_link_count": int(after["unique_links"] or 0),
            "active_after": int(after["active"] or 0),
            "hidden_duplicate_count": int(after["hidden_duplicates"] or 0),
            "updated_count": updated_count,
            "restored_count": max(0, int(after["active"] or 0) - int(before["active"] or 0)),
            "note": note.strip(),
        }

    @staticmethod
    async def cleanup_hidden_duplicate_resources(session: AsyncSession, execute: bool = False, note: str = "") -> dict:
        duplicate_where = """
            h.is_active = false
            AND nullif(trim(h.link), '') IS NOT NULL
            AND EXISTS (
                SELECT 1
                FROM netdisk_resources a
                WHERE a.is_active = true
                  AND a.id <> h.id
                  AND lower(trim(a.link)) = lower(trim(h.link))
            )
        """
        protected_where = """
            h.downloads > 0
            OR h.favorites > 0
            OR h.report_count > 0
            OR h.invalid_count > 0
            OR EXISTS (
                SELECT 1 FROM netdisk_favorites f
                WHERE f.resource_id = h.id
            )
            OR EXISTS (
                SELECT 1 FROM points_ledgers l
                WHERE l.related_type = 'netdisk_resource'
                  AND l.related_id = h.id
            )
            OR EXISTS (
                SELECT 1 FROM netdisk_repairs r
                WHERE r.resource_id = h.id
            )
            OR EXISTS (
                SELECT 1 FROM netdisk_quality_alerts qa
                WHERE qa.resource_id = h.id
            )
            OR EXISTS (
                SELECT 1 FROM netdisk_quality_daily_stats qs
                WHERE qs.resource_id = h.id
            )
        """
        overview = (
            await session.execute(
                text(
                    f"""
                    SELECT
                        count(*) AS duplicate_count,
                        count(*) FILTER (WHERE NOT ({protected_where})) AS deletable_count,
                        count(*) FILTER (WHERE ({protected_where})) AS protected_count,
                        count(DISTINCT lower(trim(h.link))) AS duplicate_link_count
                    FROM netdisk_resources h
                    WHERE {duplicate_where}
                    """
                )
            )
        ).mappings().one()

        samples = (
            await session.execute(
                text(
                    f"""
                    SELECT
                        h.id,
                        h.title,
                        h.pan,
                        h.link,
                        h.updated_at,
                        (
                            SELECT a.id
                            FROM netdisk_resources a
                            WHERE a.is_active = true
                              AND a.id <> h.id
                              AND lower(trim(a.link)) = lower(trim(h.link))
                            ORDER BY a.updated_at DESC NULLS LAST, a.created_at DESC NULLS LAST, a.id ASC
                            LIMIT 1
                        ) AS active_resource_id
                    FROM netdisk_resources h
                    WHERE {duplicate_where}
                      AND NOT ({protected_where})
                    ORDER BY h.updated_at DESC NULLS LAST, h.created_at DESC NULLS LAST
                    LIMIT 10
                    """
                )
            )
        ).mappings().all()

        deleted_count = 0
        if execute:
            deleted_count = int(
                (
                    await session.execute(
                        text(
                            f"""
                            WITH deletable AS (
                                SELECT h.id
                                FROM netdisk_resources h
                                WHERE {duplicate_where}
                                  AND NOT ({protected_where})
                            ),
                            deleted AS (
                                DELETE FROM netdisk_resources r
                                USING deletable d
                                WHERE r.id = d.id
                                RETURNING r.id
                            )
                            SELECT count(*) FROM deleted
                            """
                        )
                    )
                ).scalar_one()
                or 0
            )
            await session.flush()

        return {
            "duplicate_count": int(overview["duplicate_count"] or 0),
            "duplicate_link_count": int(overview["duplicate_link_count"] or 0),
            "deletable_count": int(overview["deletable_count"] or 0),
            "protected_count": int(overview["protected_count"] or 0),
            "deleted_count": deleted_count,
            "execute": bool(execute),
            "note": note.strip(),
            "samples": [
                {
                    "id": row["id"],
                    "title": row["title"],
                    "pan": row["pan"],
                    "link": row["link"],
                    "active_resource_id": row["active_resource_id"],
                    "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
                }
                for row in samples
            ],
        }

    @staticmethod
    async def confirm_resource_invalid(session: AsyncSession, resource_id: str, note: str = "") -> dict:
        result = await session.execute(select(NetdiskResourceModel).where(NetdiskResourceModel.id == resource_id))
        resource = result.scalar_one_or_none()
        if not resource:
            raise ValueError("resource not found")

        clean_note = note.strip() or "资源确认失效，进入待追缴流程。"
        resource.is_active = False
        resource.invalid_count = int(getattr(resource, "invalid_count", 0) or 0) + 1
        resource.last_invalid_at = datetime.utcnow()
        resource.updated_at = datetime.utcnow()
        invalid_policy = _invalid_policy_for_resource(resource)
        resource.quality_score = await _calculate_resource_quality_score_with_profile(session, resource)

        approved_repairs = (
            await session.execute(
                select(NetdiskRepair).where(
                    NetdiskRepair.resource_id == resource_id,
                    NetdiskRepair.mode == "repair",
                    NetdiskRepair.status == "approved",
                )
            )
        ).scalars().all()
        config = await _get_netdisk_audit_config(session)
        risk_records_created = 0
        source_upload = await _get_source_upload_for_resource(session, resource)
        if source_upload and source_upload.status == "approved" and int(source_upload.reward_points or 0) > 0:
            source_upload.status = "invalid_confirmed"
            source_upload.audit_note = _append_note(source_upload.audit_note, clean_note)
            source_upload.updated_at = datetime.utcnow()
            upload_penalty_points = int(invalid_policy["penalty_points"])
            await _adjust_quality_profile(
                session,
                source_upload.user_id,
                credit_delta=int(invalid_policy["credit_delta"]),
                contribution_delta=-5,
                short_invalid_delta=1 if invalid_policy["bucket"] == "within_7d" else 0,
                idempotency_key=f"netdisk_upload_quality_invalid:{resource_id}:{source_upload.id}",
                related_type="netdisk_upload",
                related_id=str(source_upload.id),
                remark=f"上传资源确认失效：{resource.title}",
            )
            if upload_penalty_points > 0:
                await _deduct_consumable_penalty(
                    session=session,
                    user_id=source_upload.user_id,
                    points=upload_penalty_points,
                    idempotency_key=f"netdisk_upload_invalid_penalty:{resource_id}:{source_upload.id}",
                    related_type="netdisk_upload",
                    related_id=str(source_upload.id),
                    change_type="invalid_penalty",
                    remark=f"{clean_note} 失效处罚 {upload_penalty_points} 分；关联资源：{resource.title}",
                )
            if upload_penalty_points > 0:
                created = await _create_risk_record(
                    session=session,
                    user_id=source_upload.user_id,
                    related_type="netdisk_upload",
                    related_id=str(source_upload.id),
                    reason="resource_invalid_pending_penalty",
                    points_due=upload_penalty_points,
                    points_collected=upload_penalty_points,
                    idempotency_key=f"netdisk_resource_invalid_risk:{resource_id}:upload:{source_upload.id}",
                    note=f"{clean_note} 已按负积分规则扣罚 {upload_penalty_points} 分；关联资源：{resource.title}",
                )
                if created:
                    risk_records_created += 1
                    await _create_user_notification(
                        session=session,
                        user_id=source_upload.user_id,
                        notice_type="netdisk_risk_pending",
                        title="上传资源确认失效",
                        content=f"你上传的资源「{resource.title}」已被确认失效，系统已按规则扣罚 {upload_penalty_points} 分。",
                        related_type="netdisk_upload",
                        related_id=str(source_upload.id),
                    )
        for repair in approved_repairs:
            reward_points = int(repair.reward_points or 0)
            if reward_points <= 0:
                continue
            penalty_points = max(0, min(reward_points, int(invalid_policy["penalty_points"])))
            repair.status = "invalid_confirmed"
            repair.audit_note = _append_note(repair.audit_note, clean_note)
            repair.updated_at = datetime.utcnow()
            await _adjust_quality_profile(
                session,
                repair.user_id,
                credit_delta=int(invalid_policy["credit_delta"]),
                contribution_delta=-3,
                idempotency_key=f"netdisk_repair_quality_invalid:{resource_id}:{repair.id}",
                related_type="netdisk_repair",
                related_id=str(repair.id),
                remark=f"补链资源确认失效：{resource.title}",
            )
            if penalty_points > 0:
                await _deduct_consumable_penalty(
                    session=session,
                    user_id=repair.user_id,
                    points=penalty_points,
                    idempotency_key=f"netdisk_repair_invalid_penalty:{resource_id}:{repair.id}",
                    related_type="netdisk_repair",
                    related_id=str(repair.id),
                    change_type="invalid_penalty",
                    remark=f"{clean_note} 补链失效处罚 {penalty_points} 分；关联资源：{resource.title}",
                )
            if penalty_points > 0:
                created = await _create_risk_record(
                    session=session,
                    user_id=repair.user_id,
                    related_type="netdisk_repair",
                    related_id=str(repair.id),
                    reason="resource_invalid_pending_penalty",
                    points_due=penalty_points,
                    points_collected=penalty_points,
                    idempotency_key=f"netdisk_resource_invalid_risk:{resource_id}:repair:{repair.id}",
                    note=f"{clean_note} 已按负积分规则扣罚 {penalty_points} 分；关联资源：{resource.title}",
                )
                if created:
                    risk_records_created += 1
                    await _create_user_notification(
                        session=session,
                        user_id=repair.user_id,
                        notice_type="netdisk_risk_pending",
                        title="补链资源确认失效",
                        content=f"你补链的资源「{resource.title}」已被确认失效，系统已按规则扣罚 {penalty_points} 分。",
                        related_type="netdisk_repair",
                        related_id=str(repair.id),
                    )

        await session.flush()
        await session.refresh(resource)
        return {
            "resource": _build_resource_payload(resource),
            "risk_records_created": risk_records_created,
            "affected_repairs": len(approved_repairs),
            "affected_upload": bool(source_upload),
            "note": clean_note,
        }

    @staticmethod
    async def list_admin_resources(
        session: AsyncSession,
        active: bool | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        query = select(NetdiskResourceModel)
        if active is not None:
            query = query.where(NetdiskResourceModel.is_active == active)
        clean_keyword = (keyword or "").strip()
        if clean_keyword:
            like = f"%{clean_keyword}%"
            query = query.where(
                or_(
                    NetdiskResourceModel.id.ilike(like),
                    NetdiskResourceModel.title.ilike(like),
                    NetdiskResourceModel.category.ilike(like),
                    NetdiskResourceModel.pan.ilike(like),
                )
            )

        total = (await session.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
        items = (
            await session.execute(
                query.order_by(NetdiskResourceModel.updated_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()
        return _build_admin_list_payload("resources", [_build_resource_payload(item) for item in items], total, page, page_size)

    @staticmethod
    async def list_risk_records(
        session: AsyncSession,
        status: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        query = select(NetdiskRiskRecord)
        if status:
            query = query.where(NetdiskRiskRecord.status == status)
        total = (await session.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
        items = (
            await session.execute(
                query.order_by(NetdiskRiskRecord.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()
        return _build_admin_list_payload("risk_records", [_build_risk_payload(item) for item in items], total, page, page_size)

    @staticmethod
    async def release_valid_7d_upload_rewards(session: AsyncSession, limit: int = 200) -> dict:
        config = await _get_netdisk_audit_config(session)
        reward_points = int(config["upload_valid_7d_points"])
        if reward_points <= 0:
            return {"released_count": 0, "released_points": 0}

        cutoff = datetime.utcnow() - timedelta(days=7)
        result = await session.execute(
            select(NetdiskUpload)
            .where(
                NetdiskUpload.status == "approved",
                NetdiskUpload.valid_days_rewarded < 7,
                NetdiskUpload.updated_at <= cutoff,
            )
            .order_by(NetdiskUpload.updated_at.asc())
            .limit(max(1, min(int(limit or 200), 1000)))
        )
        uploads = result.scalars().all()

        released_count = 0
        released_points = 0
        for upload in uploads:
            resource = await _get_resource_by_upload(session, upload)
            if not resource or not resource.is_active:
                continue
            if int(getattr(resource, "invalid_count", 0) or 0) > 0:
                continue

            remaining = max(0, int(upload.reward_points or 0) - int(upload.reward_released_points or 0))
            points = min(reward_points, remaining)
            if points <= 0:
                upload.valid_days_rewarded = 7
                resource.valid_days_rewarded = max(int(getattr(resource, "valid_days_rewarded", 0) or 0), 7)
                continue

            ledger, _, created = await PointsAccountService.add_points(
                session=session,
                user_id=upload.user_id,
                points=points,
                source="netdisk",
                change_type="upload_reward_valid_7d",
                availability="consumable",
                idempotency_key=f"netdisk_upload_valid_7d:{upload.id}",
                related_type="netdisk_upload",
                related_id=str(upload.id),
                remark=f"资源持续有效7天奖励：{upload.title}",
            )
            if not created:
                upload.valid_days_rewarded = 7
                resource.valid_days_rewarded = max(int(getattr(resource, "valid_days_rewarded", 0) or 0), 7)
                continue

            if ledger:
                upload.reward_released_points = int(upload.reward_released_points or 0) + points
                upload.valid_days_rewarded = 7
                upload.audit_note = _append_note(upload.audit_note, "资源持续有效满7天，长期有效奖励已发放。")
                upload.updated_at = datetime.utcnow()
                resource.valid_days_rewarded = max(int(getattr(resource, "valid_days_rewarded", 0) or 0), 7)
                resource.quality_score = await _calculate_resource_quality_score_with_profile(session, resource)
                resource.updated_at = datetime.utcnow()
                await _adjust_quality_profile(
                    session,
                    upload.user_id,
                    credit_delta=1,
                    contribution_delta=5,
                    idempotency_key=f"netdisk_upload_quality_valid_7d:{upload.id}",
                    related_type="netdisk_upload",
                    related_id=str(upload.id),
                    remark=f"资源持续有效7天：{upload.title}",
                )
                released_count += 1
                released_points += points

        await session.flush()
        return {"released_count": released_count, "released_points": released_points}


async def _get_unlock_ledger(session: AsyncSession, user_id, resource_id: str) -> PointsLedger | None:
    result = await session.execute(
        select(PointsLedger).where(
            PointsLedger.user_id == user_id,
            PointsLedger.idempotency_key == f"netdisk_unlock:{user_id}:{resource_id}",
        )
    )
    return result.scalar_one_or_none()


def _normalize_resource_level_and_cost(resource_level: str | None, cost_points: int | None) -> tuple[str, int]:
    cost_by_level = {"normal": 5, "featured": 10, "official": 20}
    level = (resource_level or "normal").strip()
    if level not in cost_by_level:
        raise ValueError("invalid resource level")
    cost = int(cost_points or cost_by_level[level])
    if cost != cost_by_level[level]:
        raise ValueError("resource level and cost points do not match")
    return level, cost


def _resource_level_label(level: str) -> str:
    return {"normal": "普通", "featured": "精选", "official": "官方"}.get(level, level)


async def _ensure_resource_from_upload(
    session: AsyncSession,
    item: NetdiskUpload,
    resource_level: str = "normal",
    cost_points: int = 5,
) -> NetdiskResourceModel:
    resource_id = f"upload-{str(item.id).replace('-', '')[:24]}"
    result = await session.execute(select(NetdiskResourceModel).where(NetdiskResourceModel.source_upload_id == str(item.id)))
    resource = result.scalar_one_or_none()
    if not resource:
        resource = await session.get(NetdiskResourceModel, resource_id)
    if resource:
        resource.title = item.title
        resource.category = item.category
        resource.pan = item.pan
        resource.level = resource_level
        resource.cost_points = int(cost_points)
        resource.description = item.description
        resource.link = item.link
        resource.extract_code = item.extract_code
        resource.unzip_code = item.unzip_code
        resource.tags = json.dumps([item.category, item.pan], ensure_ascii=False)
        resource.source_type = "upload"
        resource.source_ref = str(item.id)
        resource.normalized_title = normalize_resource_title(item.title)
        resource.source_upload_id = str(item.id)
        resource.uploader_user_id = item.user_id
        resource.is_active = True
        resource.verified_at = datetime.utcnow()
        resource.updated_at = datetime.utcnow()
        resource.quality_score = await _calculate_resource_quality_score_with_profile(session, resource)
        await session.flush()
        return resource

    resource = NetdiskResourceModel(
        id=resource_id,
        title=item.title,
        category=item.category,
        pan=item.pan,
        level=resource_level,
        cost_points=int(cost_points),
        downloads=0,
        favorites=0,
        description=item.description,
        link=item.link,
        extract_code=item.extract_code,
        unzip_code=item.unzip_code,
        tags=json.dumps([item.category, item.pan], ensure_ascii=False),
        source_type="upload",
        source_ref=str(item.id),
        normalized_title=normalize_resource_title(item.title),
        source_upload_id=str(item.id),
        uploader_user_id=item.user_id,
        is_active=True,
        verified_at=datetime.utcnow(),
    )
    session.add(resource)
    await session.flush()
    resource.quality_score = await _calculate_resource_quality_score_with_profile(session, resource)
    await session.flush()
    return resource


async def _get_source_upload_for_resource(session: AsyncSession, resource: NetdiskResourceModel) -> NetdiskUpload | None:
    if not resource.source_upload_id:
        return None
    try:
        return await session.get(NetdiskUpload, UUID(resource.source_upload_id))
    except ValueError:
        return None


async def _get_resource_by_upload(session: AsyncSession, upload: NetdiskUpload) -> NetdiskResourceModel | None:
    result = await session.execute(select(NetdiskResourceModel).where(NetdiskResourceModel.source_upload_id == str(upload.id)))
    resource = result.scalar_one_or_none()
    if resource:
        return resource
    resource_id = f"upload-{str(upload.id).replace('-', '')[:24]}"
    return await session.get(NetdiskResourceModel, resource_id)


async def _create_user_notification(
    session: AsyncSession,
    user_id,
    notice_type: str,
    title: str,
    content: str,
    related_type: str,
    related_id: str,
) -> None:
    session.add(
        NetdiskUserNotification(
            user_id=user_id,
            notice_type=notice_type,
            title=title,
            content=content,
            related_type=related_type,
            related_id=related_id,
            status="unread",
        )
    )


async def _grant_upload_frozen_reward(
    session: AsyncSession,
    user: User,
    item: NetdiskUpload,
) -> None:
    reward_points = int(item.reward_points)
    if reward_points <= 0:
        return

    await PointsAccountService.add_points(
        session=session,
        user_id=user.id,
        points=reward_points,
        source="netdisk",
        change_type="upload_reward_frozen",
        availability="frozen",
        idempotency_key=f"netdisk_upload_frozen:{item.id}",
        related_type="netdisk_upload",
        related_id=str(item.id),
        remark=f"网盘上传待验证奖励：{item.title}",
    )


async def _grant_repair_frozen_reward(
    session: AsyncSession,
    user: User,
    item: NetdiskRepair,
) -> None:
    reward_points = int(item.reward_points)
    if item.mode != "repair" or reward_points <= 0:
        return

    await PointsAccountService.add_points(
        session=session,
        user_id=user.id,
        points=reward_points,
        source="netdisk",
        change_type="repair_reward_frozen",
        availability="frozen",
        idempotency_key=f"netdisk_repair_frozen:{item.id}",
        related_type="netdisk_repair",
        related_id=str(item.id),
        remark=f"网盘补链待验证奖励：{item.resource_title}",
    )


async def _release_upload_reward(session: AsyncSession, item: NetdiskUpload) -> None:
    reward_points = int(item.reward_points)
    if reward_points <= 0:
        return

    await _ensure_upload_frozen_reward(session, item)
    await PointsAccountService.move_frozen_to_consumable(
        session=session,
        user_id=item.user_id,
        points=reward_points,
        source="netdisk",
        change_type="upload_reward_release",
        idempotency_key=f"netdisk_upload_release:{item.id}",
        related_type="netdisk_upload",
        related_id=str(item.id),
        remark=f"网盘上传奖励释放：{item.title}",
    )


async def _release_upload_approved_reward(session: AsyncSession, item: NetdiskUpload) -> None:
    config = await _get_netdisk_audit_config(session)
    approved_points = min(int(config["upload_approved_points"]), int(item.reward_points or 0))
    if approved_points <= 0:
        return
    if int(getattr(item, "reward_released_points", 0) or 0) >= approved_points:
        return

    ledger, _, created = await PointsAccountService.add_points(
        session=session,
        user_id=item.user_id,
        points=approved_points,
        source="netdisk",
        change_type="upload_reward_approved_part1",
        availability="consumable",
        idempotency_key=f"netdisk_upload_approved_part1:{item.id}",
        related_type="netdisk_upload",
        related_id=str(item.id),
        remark=f"网盘上传审核通过首段奖励：{item.title}",
    )
    if created or ledger:
        item.reward_released_points = max(int(getattr(item, "reward_released_points", 0) or 0), approved_points)


async def _release_repair_reward(session: AsyncSession, item: NetdiskRepair) -> None:
    reward_points = int(item.reward_points)
    if item.mode != "repair" or reward_points <= 0:
        return

    await _ensure_repair_frozen_reward(session, item)
    await PointsAccountService.move_frozen_to_consumable(
        session=session,
        user_id=item.user_id,
        points=reward_points,
        source="netdisk",
        change_type="repair_reward_release",
        idempotency_key=f"netdisk_repair_release:{item.id}",
        related_type="netdisk_repair",
        related_id=str(item.id),
        remark=f"网盘补链奖励释放：{item.resource_title}",
    )


async def _grant_creator_share_for_unlock(
    session: AsyncSession,
    resource: NetdiskResourceModel,
    unlock_user: User,
) -> tuple[dict | None, int]:
    cost_points = int(resource.cost_points or 0)
    share_points = _creator_share_points(resource)
    creator_id = getattr(resource, "uploader_user_id", None)
    if not creator_id or creator_id == unlock_user.id or share_points <= 0:
        platform_recovered = max(cost_points, 0)
        await _record_platform_recovery(session, unlock_user.id, resource, platform_recovered)
        return None, platform_recovered

    remaining_share = await _creator_daily_share_remaining(session, creator_id, resource.id)
    actual_share = max(0, min(share_points, remaining_share))
    creator_reward = None
    if actual_share > 0:
        ledger, account, created = await PointsAccountService.add_points(
            session=session,
            user_id=creator_id,
            points=actual_share,
            source="netdisk",
            change_type="resource_creator_share",
            availability="consumable",
            idempotency_key=f"netdisk_creator_share:{unlock_user.id}:{resource.id}",
            related_type="netdisk_resource",
            related_id=resource.id,
            remark=f"资源被解锁分成：{resource.title}",
        )
        await _adjust_quality_profile(
            session,
            creator_id,
            credit_delta=0,
            contribution_delta=1,
            idempotency_key=f"netdisk_creator_share_quality:{unlock_user.id}:{resource.id}",
            related_type="netdisk_resource",
            related_id=resource.id,
            remark=f"资源被解锁增加贡献：{resource.title}",
        )
        creator_reward = {
            "created": created,
            "ledger_id": str(ledger.id),
            "points_delta": int(ledger.points_delta),
            "creator_consumable_points": int(account.consumable_points),
        }

    platform_recovered = max(cost_points - actual_share, 0)
    await _record_platform_recovery(session, unlock_user.id, resource, platform_recovered)
    return creator_reward, platform_recovered


def _creator_share_points(resource: NetdiskResourceModel) -> int:
    return {"normal": 1, "featured": 2, "official": 0}.get(resource.level, 0)


async def _creator_daily_share_remaining(session: AsyncSession, creator_id, resource_id: str) -> int:
    today_start = datetime.combine(datetime.utcnow().date(), time.min)
    result = await session.execute(
        select(func.coalesce(func.sum(PointsLedger.points_delta), 0)).where(
            PointsLedger.user_id == creator_id,
            PointsLedger.change_type == "resource_creator_share",
            PointsLedger.related_type == "netdisk_resource",
            PointsLedger.related_id == resource_id,
            PointsLedger.created_at >= today_start,
        )
    )
    used = int(result.scalar_one() or 0)
    return max(0, 10 - used)


async def _record_platform_recovery(session: AsyncSession, user_id, resource: NetdiskResourceModel, points: int) -> None:
    recovered = int(points)
    if recovered <= 0:
        return
    await PointsAccountService.record_neutral_event(
        session=session,
        user_id=user_id,
        source="netdisk",
        change_type="platform_recovery",
        availability="platform",
        idempotency_key=f"netdisk_platform_recovery:{user_id}:{resource.id}",
        related_type="netdisk_resource",
        related_id=resource.id,
        remark=f"平台回收积分 {recovered}：{resource.title}",
    )


async def _get_or_create_quality_profile(session: AsyncSession, user_id) -> UserQualityProfile:
    result = await session.execute(select(UserQualityProfile).where(UserQualityProfile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if profile:
        return profile
    profile = UserQualityProfile(user_id=user_id)
    session.add(profile)
    await session.flush()
    return profile


async def _ensure_user_not_negative(session: AsyncSession, user: User, message: str) -> None:
    account, _ = await PointsAccountService.ensure_user_account(session, user.id)
    if int(account.consumable_points) < 0:
        raise ValueError(message)


async def _ensure_user_can_upload(session: AsyncSession, user: User) -> None:
    await _ensure_user_not_negative(session, user, "negative points users cannot upload resources")
    profile = await _get_or_create_quality_profile(session, user.id)
    restricted_until = getattr(profile, "upload_restricted_until", None)
    if restricted_until:
        restricted_value = restricted_until.replace(tzinfo=None) if getattr(restricted_until, "tzinfo", None) else restricted_until
        if restricted_value > datetime.utcnow():
            raise ValueError("upload permission is temporarily restricted")
    if profile.risk_level == "high":
        raise ValueError("high risk users cannot upload resources")


async def _adjust_quality_profile(
    session: AsyncSession,
    user_id,
    *,
    credit_delta: int = 0,
    contribution_delta: int = 0,
    short_invalid_delta: int = 0,
    idempotency_key: str,
    related_type: str,
    related_id: str,
    remark: str,
) -> UserQualityProfile:
    existing = await PointsAccountService.get_ledger_by_idempotency_key(session, idempotency_key)
    profile = await _get_or_create_quality_profile(session, user_id)
    if existing:
        return profile

    profile.credit_score = max(0, min(120, int(profile.credit_score) + int(credit_delta)))
    profile.contribution_score = max(0, int(profile.contribution_score) + int(contribution_delta))
    profile.short_invalid_count = max(0, int(profile.short_invalid_count) + int(short_invalid_delta))
    profile.risk_level = _quality_risk_level(profile)
    profile.updated_at = datetime.utcnow()
    await PointsAccountService.record_neutral_event(
        session=session,
        user_id=user_id,
        source="netdisk_quality",
        change_type="credit_adjustment",
        availability="quality",
        idempotency_key=idempotency_key,
        related_type=related_type,
        related_id=related_id,
        remark=f"{remark}；信用变化 {credit_delta}，贡献变化 {contribution_delta}",
    )
    return profile


def _quality_risk_level(profile: UserQualityProfile) -> str:
    if int(profile.credit_score) < 60 or int(profile.short_invalid_count) >= 3:
        return "high"
    if int(profile.credit_score) < 80:
        return "watch"
    return "normal"


def _credit_level(profile: UserQualityProfile | None) -> str:
    if not profile:
        return "normal"
    if int(profile.credit_score) >= 105:
        return "excellent"
    if int(profile.credit_score) >= 90:
        return "good"
    if int(profile.credit_score) >= 70:
        return "normal"
    return "watch"


async def _get_quality_profile(session: AsyncSession, user_id) -> UserQualityProfile | None:
    if not user_id:
        return None
    result = await session.execute(select(UserQualityProfile).where(UserQualityProfile.user_id == user_id))
    return result.scalar_one_or_none()


async def _calculate_resource_quality_score_with_profile(session: AsyncSession, resource: NetdiskResourceModel) -> int:
    profile = await _get_quality_profile(session, getattr(resource, "uploader_user_id", None))
    return _calculate_resource_quality_score(resource, profile)


def _calculate_resource_quality_score(resource: NetdiskResourceModel, profile: UserQualityProfile | None = None) -> int:
    level_bonus = {"normal": 0, "featured": 12, "official": 24}.get(resource.level, 0)
    valid_days = _resource_valid_days(resource)
    long_valid_bonus = min(valid_days, 30) // 7 * 3
    profile_bonus = 0
    if profile:
        profile_bonus = int(profile.credit_score) // 10 + min(int(profile.contribution_score) // 10, 20)
    return max(
        0,
        int(resource.downloads or 0)
        + int(resource.favorites or 0) * 2
        + level_bonus
        + long_valid_bonus
        + profile_bonus
        - int(getattr(resource, "report_count", 0) or 0) * 10
        - int(getattr(resource, "invalid_count", 0) or 0) * 20,
    )


def _resource_valid_days(resource: NetdiskResourceModel) -> int:
    verified_at = getattr(resource, "verified_at", None)
    if not verified_at:
        return 0
    value = verified_at.replace(tzinfo=None) if getattr(verified_at, "tzinfo", None) else verified_at
    return max(0, (datetime.utcnow() - value).days)


def _invalid_policy_for_resource(resource: NetdiskResourceModel) -> dict:
    age_days = max(0, (datetime.utcnow() - resource.created_at.replace(tzinfo=None)).days) if resource.created_at else 0
    if age_days < 7:
        return {"bucket": "within_7d", "penalty_points": 5, "credit_delta": -3}
    if age_days < 30:
        return {"bucket": "within_30d", "penalty_points": 5, "credit_delta": -2}
    return {"bucket": "after_30d", "penalty_points": 2, "credit_delta": -1}


def _repair_reward_for_resource(resource: NetdiskResourceModel, config: dict) -> int:
    by_level = config.get("repair_reward_points_by_level", {})
    return int(by_level.get(resource.level, config["repair_reward_points"]))


async def _clawback_upload_reward(session: AsyncSession, item: NetdiskUpload, reason: str) -> None:
    await _clawback_netdisk_reward(
        session=session,
        user_id=item.user_id,
        points=int(item.reward_points),
        related_type="netdisk_upload",
        related_id=str(item.id),
        release_idempotency_key=f"netdisk_upload_release:{item.id}",
        clawback_idempotency_key=f"netdisk_upload_clawback:{item.id}:{reason}",
        penalty_idempotency_key=f"netdisk_upload_penalty:{item.id}:{reason}",
        clawback_change_type=reason,
        penalty_change_type=reason,
        remark=f"网盘上传奖励扣回：{item.title}",
    )


async def _clawback_repair_reward(session: AsyncSession, item: NetdiskRepair, reason: str) -> None:
    await _clawback_netdisk_reward(
        session=session,
        user_id=item.user_id,
        points=int(item.reward_points),
        related_type="netdisk_repair",
        related_id=str(item.id),
        release_idempotency_key=f"netdisk_repair_release:{item.id}",
        clawback_idempotency_key=f"netdisk_repair_clawback:{item.id}:{reason}",
        penalty_idempotency_key=f"netdisk_repair_penalty:{item.id}:{reason}",
        clawback_change_type=reason,
        penalty_change_type=reason,
        remark=f"网盘补链奖励扣回：{item.resource_title}",
    )


async def _clawback_netdisk_reward(
    session: AsyncSession,
    user_id,
    points: int,
    related_type: str,
    related_id: str,
    release_idempotency_key: str,
    clawback_idempotency_key: str,
    penalty_idempotency_key: str,
    clawback_change_type: str,
    penalty_change_type: str,
    remark: str,
) -> None:
    reward_points = int(points)
    if reward_points <= 0:
        return

    release_ledger = await PointsAccountService.get_ledger_by_idempotency_key(session, release_idempotency_key)
    if release_ledger:
        config = await _get_netdisk_audit_config(session)
        penalty_points = reward_points * int(config["invalid_penalty_multiplier"])
        await _deduct_consumable_penalty(
            session=session,
            user_id=user_id,
            points=penalty_points,
            idempotency_key=penalty_idempotency_key,
            related_type=related_type,
            related_id=related_id,
            change_type=penalty_change_type,
            remark=remark,
        )
        return

    clawback_ledger = await PointsAccountService.get_ledger_by_idempotency_key(session, clawback_idempotency_key)
    if clawback_ledger:
        return

    frozen_ledger_key = _frozen_reward_key_for_related(related_type, related_id)
    frozen_ledger = await PointsAccountService.get_ledger_by_idempotency_key(session, frozen_ledger_key)
    if not frozen_ledger:
        return

    await PointsAccountService.deduct_frozen_points(
        session=session,
        user_id=user_id,
        points=reward_points,
        source="netdisk",
        change_type=clawback_change_type,
        idempotency_key=clawback_idempotency_key,
        related_type=related_type,
        related_id=related_id,
        remark=remark,
    )


async def _ensure_upload_frozen_reward(session: AsyncSession, item: NetdiskUpload) -> None:
    reward_points = int(item.reward_points)
    if reward_points <= 0:
        return
    existing = await PointsAccountService.get_ledger_by_idempotency_key(session, f"netdisk_upload_frozen:{item.id}")
    if existing:
        return
    await PointsAccountService.add_points(
        session=session,
        user_id=item.user_id,
        points=reward_points,
        source="netdisk",
        change_type="upload_reward_frozen",
        availability="frozen",
        idempotency_key=f"netdisk_upload_frozen:{item.id}",
        related_type="netdisk_upload",
        related_id=str(item.id),
        remark=f"网盘上传历史待审奖励补记：{item.title}",
    )


async def _ensure_repair_frozen_reward(session: AsyncSession, item: NetdiskRepair) -> None:
    reward_points = int(item.reward_points)
    if item.mode != "repair" or reward_points <= 0:
        return
    existing = await PointsAccountService.get_ledger_by_idempotency_key(session, f"netdisk_repair_frozen:{item.id}")
    if existing:
        return
    await PointsAccountService.add_points(
        session=session,
        user_id=item.user_id,
        points=reward_points,
        source="netdisk",
        change_type="repair_reward_frozen",
        availability="frozen",
        idempotency_key=f"netdisk_repair_frozen:{item.id}",
        related_type="netdisk_repair",
        related_id=str(item.id),
        remark=f"网盘补链历史待审奖励补记：{item.resource_title}",
    )


def _frozen_reward_key_for_related(related_type: str, related_id: str) -> str:
    if related_type == "netdisk_upload":
        return f"netdisk_upload_frozen:{related_id}"
    if related_type == "netdisk_repair":
        return f"netdisk_repair_frozen:{related_id}"
    return ""


def _append_note(old_note: str, new_note: str) -> str:
    if not new_note:
        return old_note or ""
    if not old_note:
        return new_note
    return f"{old_note}\n{new_note}"


async def _deduct_consumable_penalty(
    session: AsyncSession,
    user_id,
    points: int,
    idempotency_key: str,
    related_type: str,
    related_id: str,
    change_type: str,
    remark: str,
) -> None:
    target_points = int(points)
    if target_points <= 0:
        return

    await PointsAccountService.consume_consumable_points_allow_negative(
        session=session,
        user_id=user_id,
        points=target_points,
        source="netdisk",
        change_type=change_type,
        idempotency_key=idempotency_key,
        related_type=related_type,
        related_id=related_id,
        remark=remark,
    )


async def _hide_resource_after_report_threshold(session: AsyncSession, resource_id: str, threshold: int = 3) -> None:
    report_count = (
        await session.execute(
            select(func.count()).select_from(NetdiskRepair).where(
                NetdiskRepair.resource_id == resource_id,
                NetdiskRepair.mode == "report",
                NetdiskRepair.status != "rejected",
            )
        )
    ).scalar() or 0
    if int(report_count) < threshold:
        return

    result = await session.execute(select(NetdiskResourceModel).where(NetdiskResourceModel.id == resource_id))
    resource = result.scalar_one_or_none()
    if resource:
        resource.is_active = False
        resource.updated_at = datetime.utcnow()


async def _restore_resource_if_report_below_threshold(session: AsyncSession, resource_id: str) -> None:
    config = await _get_netdisk_audit_config(session)
    report_count = (
        await session.execute(
            select(func.count()).select_from(NetdiskRepair).where(
                NetdiskRepair.resource_id == resource_id,
                NetdiskRepair.mode == "report",
                NetdiskRepair.status != "rejected",
            )
        )
    ).scalar() or 0
    if int(report_count) >= int(config["report_hide_threshold"]):
        return

    result = await session.execute(select(NetdiskResourceModel).where(NetdiskResourceModel.id == resource_id))
    resource = result.scalar_one_or_none()
    if resource:
        resource.is_active = True
        resource.updated_at = datetime.utcnow()


async def _create_risk_record(
    session: AsyncSession,
    user_id,
    related_type: str,
    related_id: str,
    reason: str,
    points_due: int,
    points_collected: int,
    idempotency_key: str,
    note: str,
) -> bool:
    existing = (
        await session.execute(select(NetdiskRiskRecord).where(NetdiskRiskRecord.idempotency_key == idempotency_key))
    ).scalar_one_or_none()
    if existing:
        return False

    item = NetdiskRiskRecord(
        user_id=user_id,
        related_type=related_type,
        related_id=related_id,
        reason=reason,
        points_due=int(points_due),
        points_collected=int(points_collected),
        status="open",
        note=note,
        idempotency_key=idempotency_key,
    )
    session.add(item)
    await session.flush()
    return True


async def _get_netdisk_audit_config(session: AsyncSession) -> dict:
    raw = await ConfigService.get(session, "netdisk_audit_config")
    return _normalize_netdisk_audit_config(raw)


def _normalize_netdisk_audit_config(raw: dict | None) -> dict:
    data = dict(raw or {})
    upload_reward_points = max(0, int(data.get("upload_reward_points", 5) or 0))
    upload_approved_points = max(0, int(data.get("upload_approved_points", 2) or 0))
    upload_valid_7d_points = max(0, int(data.get("upload_valid_7d_points", upload_reward_points - upload_approved_points) or 0))
    return {
        "upload_reward_points": upload_reward_points,
        "upload_approved_points": min(upload_approved_points, upload_reward_points),
        "upload_valid_7d_points": min(upload_valid_7d_points, upload_reward_points),
        "repair_reward_points": max(0, int(data.get("repair_reward_points", 5) or 0)),
        "repair_reward_points_by_level": {
            "normal": max(0, int(data.get("repair_reward_normal", 5) or 0)),
            "featured": max(0, int(data.get("repair_reward_featured", 8) or 0)),
            "official": max(0, int(data.get("repair_reward_official", 10) or 0)),
        },
        "report_hide_threshold": max(1, int(data.get("report_hide_threshold", 3) or 3)),
        "invalid_penalty_multiplier": max(1, int(data.get("invalid_penalty_multiplier", 1) or 1)),
        "auto_hide_on_report": bool(data.get("auto_hide_on_report", True)),
    }


async def _get_upload_or_raise(session: AsyncSession, upload_id: str) -> NetdiskUpload:
    try:
        item_id = UUID(upload_id)
    except ValueError as exc:
        raise ValueError("invalid upload id") from exc

    item = await session.get(NetdiskUpload, item_id)
    if not item:
        raise ValueError("upload not found")
    return item


async def _get_repair_or_raise(session: AsyncSession, repair_id: str) -> NetdiskRepair:
    try:
        item_id = UUID(repair_id)
    except ValueError as exc:
        raise ValueError("invalid repair id") from exc

    item = await session.get(NetdiskRepair, item_id)
    if not item:
        raise ValueError("repair not found")
    return item


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
    now = datetime.utcnow()
    verified_offsets = {
        "r1": timedelta(hours=2),
        "r2": timedelta(hours=6),
        "r3": timedelta(days=1),
    }
    rows = []
    for resource in NETDISK_RESOURCE_CATALOG.values():
        seed = {
            "id": resource.id,
            "title": resource.title,
            "category": resource.category,
            "pan": resource.pan,
            "level": resource.level,
            "cost_points": resource.cost_points,
            "verified_at": now - verified_offsets.get(resource.id, timedelta(days=1)),
            "downloads": resource.downloads,
            "favorites": resource.favorites,
            "description": resource.description,
            "link": resource.link,
            "extract_code": resource.extract_code,
            "unzip_code": resource.unzip_code,
            "tags": "[]",
            "source_type": "seed",
            "source_ref": f"seed:{resource.id}",
            "normalized_title": normalize_resource_title(resource.title),
            "is_active": True,
        }
        seed["quality_score"] = _calculate_resource_quality_score(
            NetdiskResourceModel(**seed)
        )
        rows.append(seed)
    if rows:
        statement = pg_insert(NetdiskResourceModel).values(rows).on_conflict_do_nothing(
            index_elements=["id"]
        )
        await session.execute(statement)
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
    if sort in {"hot", "recommend", "featured"}:
        return [
            NetdiskResourceModel.quality_score.desc(),
            NetdiskResourceModel.downloads.desc(),
            NetdiskResourceModel.favorites.desc(),
            NetdiskResourceModel.verified_at.desc(),
        ]
    if sort in {"pointsAsc", "low_cost"}:
        return [NetdiskResourceModel.cost_points.asc(), NetdiskResourceModel.verified_at.desc()]
    if sort in {"pointsDesc", "high_cost"}:
        return [NetdiskResourceModel.cost_points.desc(), NetdiskResourceModel.verified_at.desc()]
    return [NetdiskResourceModel.verified_at.desc(), NetdiskResourceModel.created_at.desc()]


async def _attach_resource_quality_labels(session: AsyncSession, resources: list[NetdiskResourceModel]) -> None:
    user_ids = [resource.uploader_user_id for resource in resources if getattr(resource, "uploader_user_id", None)]
    if not user_ids:
        for resource in resources:
            setattr(resource, "_uploader_credit_level", "good" if resource.level == "official" else "normal")
            setattr(resource, "_uploader_credit_score", 100)
            setattr(resource, "_uploader_nickname", "官方整理" if resource.level == "official" else "平台精选")
            setattr(resource, "_uploader_avatar", "")
        return
    result = await session.execute(select(UserQualityProfile).where(UserQualityProfile.user_id.in_(user_ids)))
    profiles = {profile.user_id: profile for profile in result.scalars().all()}
    user_result = await session.execute(select(User).where(User.id.in_(user_ids)))
    users = {user.id: user for user in user_result.scalars().all()}
    for resource in resources:
        uploader_id = getattr(resource, "uploader_user_id", None)
        profile = profiles.get(uploader_id)
        uploader = users.get(uploader_id)
        setattr(resource, "_uploader_credit_level", _credit_level(profile))
        setattr(resource, "_uploader_credit_score", int(profile.credit_score) if profile else 100)
        setattr(resource, "_uploader_nickname", uploader.nickname if uploader and uploader.nickname else ("官方整理" if resource.level == "official" else "平台精选"))
        setattr(resource, "_uploader_avatar", uploader.avatar if uploader else "")


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


def _format_published_at(value) -> str:
    if not value:
        return ""
    if isinstance(value, str):
        return value
    now = datetime.utcnow()
    created = value.replace(tzinfo=None) if getattr(value, "tzinfo", None) else value
    if created.date() == now.date():
        return "今天"
    if created.date() == (now.date() - timedelta(days=1)):
        return "昨天"
    return created.strftime("%Y-%m-%d")


def _resource_tags(resource: NetdiskResource | NetdiskResourceModel) -> list[str]:
    raw = getattr(resource, "tags", "[]") or "[]"
    if isinstance(raw, list):
        return [str(tag) for tag in raw if str(tag).strip()]
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        parsed = []
    if not isinstance(parsed, list):
        return []
    return [str(tag).strip()[:20] for tag in parsed if str(tag).strip()]


def _parse_json_list(raw: str | list | None) -> list[str]:
    if isinstance(raw, list):
        return [str(item).strip()[:20] for item in raw if str(item).strip()]
    try:
        parsed = json.loads(raw or "[]")
    except (TypeError, json.JSONDecodeError):
        parsed = []
    if not isinstance(parsed, list):
        return []
    return [str(item).strip()[:20] for item in parsed if str(item).strip()]


def _build_collected_payload(item: NetdiskCollectedResource) -> dict:
    return {
        "id": str(item.id),
        "title": item.title,
        "category": item.category,
        "pan": item.pan,
        "link": item.link,
        "extract_code": item.extract_code,
        "tags": _parse_json_list(item.tags),
        "normalized_title": item.normalized_title,
        "source_type": item.source_type,
        "source_ref": item.source_ref,
        "source_url": item.source_url,
        "confidence": int(item.confidence or 0),
        "duplicate_status": item.duplicate_status,
        "duplicate_text": _duplicate_status_text(item.duplicate_status),
        "ingest_action": item.ingest_action,
        "status": item.status,
        "error": item.error,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _duplicate_status_text(value: str) -> str:
    if value == "same_link":
        return "同链接重复"
    if value == "same_title_same_pan":
        return "同标题同网盘"
    if value == "supplement_pan":
        return "新增网盘补充"
    return "非重复"


async def _get_resource_by_link(session: AsyncSession, link: str) -> NetdiskResourceModel | None:
    clean_link = (link or "").strip()
    if not clean_link:
        return None
    result = await session.execute(select(NetdiskResourceModel).where(NetdiskResourceModel.link == clean_link).limit(1))
    return result.scalar_one_or_none()


async def _publish_collected_candidate(
    session: AsyncSession,
    item: NetdiskCollectedResource,
    classification: ClassificationResult,
    action: str,
) -> NetdiskResourceModel:
    source_ref = item.source_ref or f"{item.source_type}:{item.id}"
    existing = (
        await session.execute(select(NetdiskResourceModel).where(NetdiskResourceModel.source_ref == source_ref).limit(1))
    ).scalar_one_or_none()
    level, cost_points, media_tags = media_level_and_cost(item.title) if item.category == "影视剧" else ("normal", 5, [])
    tags = sorted(set([*classification.tags, *media_tags, item.pan]))
    normalized_title = item.normalized_title or normalize_resource_title(item.title)
    if existing:
        resource = existing
        resource.title = item.title[:120]
        resource.category = item.category
        resource.pan = item.pan[:32]
        resource.level = level
        resource.cost_points = cost_points
        resource.description = _collected_resource_description(item, action)
        resource.link = item.link
        resource.extract_code = item.extract_code or ""
        resource.tags = json.dumps(tags, ensure_ascii=False)
        resource.source_type = item.source_type or "linuxdo"
        resource.source_ref = source_ref
        resource.normalized_title = normalized_title
        resource.source_upload_id = f"{item.source_type}:{item.id}"
        resource.is_active = True
        resource.verified_at = datetime.utcnow()
        resource.updated_at = datetime.utcnow()
    else:
        resource = NetdiskResourceModel(
            id=f"{item.source_type or 'collect'}-{hashlib.sha1(source_ref.encode('utf-8')).hexdigest()[:20]}",
            title=item.title[:120],
            category=item.category,
            pan=item.pan[:32],
            level=level,
            cost_points=cost_points,
            downloads=0,
            favorites=0,
            description=_collected_resource_description(item, action),
            link=item.link,
            extract_code=item.extract_code or "",
            unzip_code="",
            tags=json.dumps(tags, ensure_ascii=False),
            source_type=item.source_type or "linuxdo",
            source_ref=source_ref,
            normalized_title=normalized_title,
            source_upload_id=f"{item.source_type}:{item.id}",
            uploader_user_id=None,
            is_active=True,
            verified_at=datetime.utcnow(),
        )
        session.add(resource)
    resource.quality_score = _calculate_resource_quality_score(resource)
    return resource


def _collected_resource_description(item: NetdiskCollectedResource, action: str) -> str:
    action_text = "运营合并入库" if action == "merge" else "运营审核入库"
    return f"{action_text}的采集资源，来源：{item.source_url or item.source_type}。"


def _build_resource_payload(resource: NetdiskResource | NetdiskResourceModel) -> dict:
    valid_days = _resource_valid_days(resource) if isinstance(resource, NetdiskResourceModel) else 0
    created_at = getattr(resource, "created_at", None)
    return {
        "id": resource.id,
        "title": resource.title,
        "category": resource.category,
        "pan": resource.pan,
        "level": resource.level,
        "cost_points": resource.cost_points,
        "verified_at": _format_verified_at(resource.verified_at),
        "created_at": created_at.isoformat() if created_at and hasattr(created_at, "isoformat") else "",
        "published_at": _format_published_at(created_at),
        "downloads": resource.downloads,
        "favorites": resource.favorites,
        "description": resource.description,
        "tags": _resource_tags(resource),
        "source_type": getattr(resource, "source_type", "seed") or "seed",
        "source_ref": getattr(resource, "source_ref", "") or "",
        "is_active": bool(getattr(resource, "is_active", True)),
        "source_upload_id": getattr(resource, "source_upload_id", ""),
        "quality_score": int(getattr(resource, "quality_score", 0) or 0),
        "uploader_credit_level": getattr(resource, "_uploader_credit_level", "normal"),
        "uploader_credit_score": int(getattr(resource, "_uploader_credit_score", 100) or 100),
        "uploader_nickname": getattr(resource, "_uploader_nickname", "官方整理" if resource.level == "official" else "平台精选"),
        "uploader_avatar": getattr(resource, "_uploader_avatar", ""),
        "valid_days": valid_days,
        "report_count": int(getattr(resource, "report_count", 0) or 0),
        "invalid_count": int(getattr(resource, "invalid_count", 0) or 0),
    }


def _build_favorite_payload(favorite: NetdiskFavorite, resource: NetdiskResourceModel) -> dict:
    return {
        "resource": _build_resource_payload(resource),
        "favorite_at": favorite.created_at,
        "favorited": True,
    }


async def _get_request_by_id(session: AsyncSession, request_id: str, for_update: bool = False) -> NetdiskRequest | None:
    try:
        request_uuid = UUID(str(request_id))
    except (TypeError, ValueError):
        return None
    stmt = select(NetdiskRequest).where(NetdiskRequest.id == request_uuid)
    if for_update:
        stmt = stmt.with_for_update()
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _get_upload_by_id(session: AsyncSession, upload_id: str) -> NetdiskUpload | None:
    try:
        upload_uuid = UUID(str(upload_id))
    except (TypeError, ValueError):
        return None
    result = await session.execute(select(NetdiskUpload).where(NetdiskUpload.id == upload_uuid))
    return result.scalar_one_or_none()


async def _return_request_bounty(
    session: AsyncSession,
    request: NetdiskRequest,
    *,
    status: str,
    remark_prefix: str,
) -> None:
    now = datetime.utcnow()
    request.status = status
    request.bounty_status = "returned"
    request.closed_at = now
    request.updated_at = now
    await PointsAccountService.return_frozen_to_consumable(
        session=session,
        user_id=request.user_id,
        points=int(request.bounty_points),
        idempotency_key=f"request_bounty_return:{request.id}:{status}",
        related_type="netdisk_request",
        related_id=str(request.id),
        remark=f"{remark_prefix}：{request.title}",
    )
    await session.flush()


def _build_request_payload(item: NetdiskRequest, user_id=None) -> dict:
    return {
        "id": str(item.id),
        "title": item.title,
        "pans": item.pans,
        "category": item.category,
        "bounty_points": int(item.bounty_points),
        "note": item.note,
        "status": item.status,
        "bounty_status": getattr(item, "bounty_status", "frozen"),
        "accepted_upload_id": str(item.accepted_upload_id) if getattr(item, "accepted_upload_id", None) else None,
        "submissions_count": int(item.submissions_count),
        "deadline_text": item.deadline_text,
        "expires_at": getattr(item, "expires_at", None),
        "accepted_at": getattr(item, "accepted_at", None),
        "closed_at": getattr(item, "closed_at", None),
        "created_at": item.created_at,
        "mine": bool(user_id and item.user_id == user_id),
        "can_submit": bool((not user_id or item.user_id != user_id) and item.status == "open" and getattr(item, "bounty_status", "frozen") == "frozen"),
    }


def _build_upload_payload(item: NetdiskUpload) -> dict:
    return {
        "id": str(item.id),
        "request_id": str(item.request_id) if getattr(item, "request_id", None) else None,
        "title": item.title,
        "category": item.category,
        "pan": item.pan,
        "status": item.status,
        "accepted_at": getattr(item, "accepted_at", None),
        "reward_points": int(item.reward_points),
        "reward_released_points": int(getattr(item, "reward_released_points", 0) or 0),
        "valid_days_rewarded": int(getattr(item, "valid_days_rewarded", 0) or 0),
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


def _build_feedback_payload(item: NetdiskFeedback, user_id=None) -> dict:
    return {
        "id": str(item.id),
        "feedback_type": item.feedback_type,
        "content": item.content,
        "contact": item.contact,
        "status": item.status,
        "auto_reply": item.auto_reply,
        "admin_reply": item.admin_reply,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "mine": bool(user_id and item.user_id == user_id),
    }


def _build_admin_list_payload(key: str, items: list[dict], total: int, page: int, page_size: int) -> dict:
    return {
        key: items,
        "total": int(total),
        "page": int(page),
        "page_size": int(page_size),
        "has_more": (int(page) - 1) * int(page_size) + len(items) < int(total),
    }


def _build_risk_payload(item: NetdiskRiskRecord) -> dict:
    return {
        "id": str(item.id),
        "user_id": str(item.user_id),
        "related_type": item.related_type,
        "related_id": item.related_id,
        "reason": item.reason,
        "points_due": int(item.points_due),
        "points_collected": int(item.points_collected),
        "status": item.status,
        "note": item.note,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
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
    creator_reward: dict | None = None,
    platform_recovered_points: int = 0,
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
        "creator_reward": creator_reward,
        "platform_recovered_points": int(platform_recovered_points),
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
