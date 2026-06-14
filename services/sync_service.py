"""
影视资源定时同步服务。

数据来源：金山文档(kdocs) 逆向爬取
功能：
1. 定时从金山文档爬取 anime/movie/4k 资源
2. 按夸克网盘 URL 做去重：匹配到旧记录则删除后重新插入
3. 将外部已删除的数据标记为 is_active=False
"""

import asyncio
import hashlib
import json
import logging
import os
from datetime import datetime

from sqlalchemy import or_, select, update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession

from models.anime_resource import AnimeResource
from models.base import get_session_ctx
from models.netdisk_resource import NetdiskResource as NetdiskResourceModel
from services.netdisk_resource_service import _calculate_resource_quality_score
from services.resource_classification_service import media_level_and_cost, normalize_resource_title

logger = logging.getLogger("sync_anime")

SYNC_INTERVAL_MINUTES = int(os.getenv("ANIME_SYNC_INTERVAL", "60"))
SYNC_ENABLED = os.getenv("ANIME_SYNC_ENABLED", "true").lower() == "true"
KDOCS_SYNC_LIMIT_PER_TYPE = int(os.getenv("KDOCS_SYNC_LIMIT_PER_TYPE", "20"))


async def _upsert_anime(session: AsyncSession, item: dict) -> None:
    baidu_url = (item.get("baidu_url") or "").strip()
    quark_url = (item.get("quark_url") or "").strip()
    k4_url = (item.get("4k_url") or "").strip()
    xunlei_url = (item.get("xunlei_url") or "").strip()
    category = item.get("category", "anime")
    anime_id = item.get("anime_id", "")

    raw_time = item.get("update_time") or item.get("updated_at")
    source_time = None
    if raw_time:
        try:
            source_time = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass

    conditions = [
        (AnimeResource.category == category) & (AnimeResource.anime_id == anime_id)
    ]
    if quark_url:
        conditions.append(AnimeResource.quark_url == quark_url)
    if baidu_url:
        conditions.append(AnimeResource.baidu_url == baidu_url)
    if xunlei_url:
        conditions.append(AnimeResource.xunlei_url == xunlei_url)

    existing = None
    if conditions:
        result = await session.execute(select(AnimeResource).where(or_(*conditions)).limit(1))
        existing = result.scalar_one_or_none()

    if existing:
        existing.anime_id = anime_id
        existing.title = item.get("title", "") or existing.title
        existing.category = category
        existing.quality = item.get("quality")
        existing.episode = item.get("episode")
        existing.status = item.get("status")
        existing.baidu_url = baidu_url or None
        existing.baidu_password = item.get("baidu_password")
        existing.quark_url = quark_url or None
        existing.four_k_url = k4_url or None
        existing.xunlei_url = xunlei_url or None
        existing.source_update_time = source_time
        existing.is_active = True
        existing.updated_at = datetime.utcnow()
        session.add(existing)
    else:
        resource = AnimeResource(
            anime_id=anime_id,
            title=item.get("title", ""),
            category=category,
            quality=item.get("quality"),
            episode=item.get("episode"),
            status=item.get("status"),
            baidu_url=baidu_url or None,
            baidu_password=item.get("baidu_password"),
            quark_url=quark_url or None,
            four_k_url=k4_url or None,
            xunlei_url=xunlei_url or None,
            source_update_time=source_time,
            is_active=True,
        )
        session.add(resource)


def _netdisk_resource_id(item: dict, pan: str, link: str) -> str:
    anime_id = (item.get("anime_id") or item.get("title") or "").strip()
    digest = hashlib.sha1(f"{anime_id}:{pan}:{link}".encode("utf-8")).hexdigest()[:20]
    return f"kdocs-{digest}"


def _netdisk_source_key(item: dict) -> str:
    category = (item.get("category") or "anime").strip()
    anime_id = (item.get("anime_id") or "").strip()
    digest = hashlib.sha1(f"{category}:{anime_id}".encode("utf-8")).hexdigest()[:16]
    return f"kdocs:{category}:{digest}"


def _netdisk_source_ref(item: dict, pan: str, link: str) -> str:
    category = (item.get("category") or "anime").strip()
    anime_id = (item.get("anime_id") or "").strip()
    digest = hashlib.sha1(link.encode("utf-8")).hexdigest()[:16]
    return f"kdocs:{category}:{anime_id}:{pan}:{digest}"[:180]


def _detect_pan(link: str, fallback: str) -> str:
    value = (link or "").lower()
    if "pan.quark.cn" in value:
        return "夸克"
    if "pan.baidu.com" in value:
        return "百度"
    if value.startswith(("thunder://", "magnet:", "ed2k://")) or "xunlei" in value:
        return "迅雷"
    if "aliyundrive" in value or "alipan" in value:
        return "阿里"
    return fallback


def _iter_netdisk_links(item: dict) -> list[tuple[str, str, str]]:
    candidates = [
        ("百度", (item.get("baidu_url") or "").strip(), item.get("baidu_password") or ""),
        ("夸克", (item.get("quark_url") or "").strip(), ""),
        ("阿里", (item.get("4k_url") or "").strip(), ""),
        ("迅雷", (item.get("xunlei_url") or "").strip(), ""),
    ]
    links: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for fallback_pan, link, code in candidates:
        if not link or link in seen:
            continue
        seen.add(link)
        links.append((_detect_pan(link, fallback_pan), link, code))
    return links


def _dedupe_source_links(items: list[dict]) -> list[dict]:
    """Clear duplicate links in the same crawl batch to respect URL unique indexes."""
    seen: set[str] = set()
    result: list[dict] = []
    link_fields = ("baidu_url", "quark_url", "4k_url", "xunlei_url")
    for item in items:
        clean_item = dict(item)
        for field in link_fields:
            link = (clean_item.get(field) or "").strip()
            if not link:
                continue
            key = link.lower()
            if key in seen:
                clean_item[field] = ""
                if field == "baidu_url":
                    clean_item["baidu_password"] = ""
                continue
            seen.add(key)
        result.append(clean_item)
    return result


def _netdisk_description(item: dict, pan: str) -> str:
    category_label = {"anime": "番剧", "movie": "电影", "4k": "4K影视"}.get(item.get("category"), "影视剧")
    update_time = item.get("update_time") or "最近同步"
    return f"系统每日从金山文档同步的{category_label}资源，当前网盘：{pan}，同步时间：{update_time}。"


async def _upsert_netdisk_resources(session: AsyncSession, item: dict) -> list[str]:
    active_ids: list[str] = []
    title = (item.get("title") or "").strip()
    if not title:
        return active_ids
    level, cost_points, media_tags = media_level_and_cost(title)
    normalized_title = normalize_resource_title(title)

    for pan, link, extract_code in _iter_netdisk_links(item):
        resource_id = _netdisk_resource_id(item, pan, link)
        source_key = _netdisk_source_key(item)
        source_ref = _netdisk_source_ref(item, pan, link)
        tags = sorted(set([*media_tags, pan]))
        resource = await session.get(NetdiskResourceModel, resource_id)
        if not resource:
            link_result = await session.execute(
                select(NetdiskResourceModel)
                .where(NetdiskResourceModel.link == link)
                .order_by(NetdiskResourceModel.is_active.desc(), NetdiskResourceModel.updated_at.desc())
                .limit(1)
            )
            resource = link_result.scalar_one_or_none()
        if resource:
            active_ids.append(resource.id)
            resource.title = title
            resource.category = "影视剧"
            resource.pan = pan
            resource.level = level
            resource.cost_points = cost_points
            resource.description = _netdisk_description(item, pan)
            resource.link = link
            resource.extract_code = extract_code or ""
            resource.tags = json.dumps(tags, ensure_ascii=False)
            resource.source_type = "kdocs"
            resource.source_ref = source_ref
            resource.normalized_title = normalized_title
            resource.source_upload_id = source_key
            resource.uploader_user_id = None
            resource.is_active = True
            resource.verified_at = datetime.utcnow()
            resource.updated_at = datetime.utcnow()
            resource.quality_score = _calculate_resource_quality_score(resource)
            session.add(resource)
            continue

        active_ids.append(resource_id)
        resource = NetdiskResourceModel(
            id=resource_id,
            title=title,
            category="影视剧",
            pan=pan,
            level=level,
            cost_points=cost_points,
            downloads=0,
            favorites=0,
            description=_netdisk_description(item, pan),
            link=link,
            extract_code=extract_code or "",
            unzip_code="",
            tags=json.dumps(tags, ensure_ascii=False),
            source_type="kdocs",
            source_ref=source_ref,
            normalized_title=normalized_title,
            source_upload_id=source_key,
            uploader_user_id=None,
            is_active=True,
            verified_at=datetime.utcnow(),
        )
        resource.quality_score = _calculate_resource_quality_score(resource)
        session.add(resource)
    return active_ids


async def sync_anime_from_kdocs(types: list[str] | None = None) -> dict:
    if types is None:
        types = ["anime", "movie", "4k"]

    logger.info("[sync] ====== start kdocs sync (types=%s) ======", types)
    result = {"synced": 0, "inactive": 0, "error": None}

    try:
        from core.kdocs_service import KDocsService

        loop = asyncio.get_event_loop()
        all_items = await loop.run_in_executor(None, KDocsService.crawl_all, types, KDOCS_SYNC_LIMIT_PER_TYPE)

        logger.info("[sync] kdocs fetched %s items", len(all_items))
        all_items = _dedupe_source_links(all_items)

        if not all_items:
            logger.info("[sync] kdocs data is empty, skip sync")
            return result

        async with get_session_ctx() as session:
            external_ids = {
                item.get("anime_id", "")
                for item in all_items
                if item.get("anime_id")
            }

            active_netdisk_ids: set[str] = set()
            for item in all_items:
                await _upsert_anime(session, item)
                active_netdisk_ids.update(await _upsert_netdisk_resources(session, item))
                result["synced"] += 1

            if external_ids:
                stmt = (
                    sql_update(AnimeResource)
                    .where(
                        AnimeResource.category.in_(types),
                        AnimeResource.is_active == True,
                        AnimeResource.anime_id.not_in(external_ids),
                    )
                    .values(is_active=False)
                )
                exec_result = await session.execute(stmt)
                result["inactive"] = exec_result.rowcount or 0

            # KDocs sync only fetches the latest rows from each source. Missing
            # rows are historical resources, not deletions, so never hide old
            # netdisk resources during routine sync.
            result["netdisk_inactive"] = 0


            await session.commit()
            logger.info(
                "[sync] completed: upsert=%s inactive=%s netdisk_inactive=%s",
                result["synced"],
                result["inactive"],
                result.get("netdisk_inactive", 0),
            )

    except Exception as exc:
        logger.error("[sync] failed: %s", exc, exc_info=True)
        result["error"] = str(exc)

    return result


def create_scheduler():
    if not SYNC_ENABLED:
        logger.info("[sync] sync disabled by ANIME_SYNC_ENABLED=false")
        return None

    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    scheduler = AsyncIOScheduler(
        timezone="Asia/Shanghai",
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 60,
        },
    )

    scheduler.add_job(
        sync_anime_from_kdocs,
        "interval",
        minutes=SYNC_INTERVAL_MINUTES,
        kwargs={"types": ["anime"]},
        id="sync_anime_job",
        name="影视剧数据每小时同步(金山文档)",
        replace_existing=True,
    )

    scheduler.add_job(
        sync_anime_from_kdocs,
        "cron",
        hour=0,
        minute=0,
        kwargs={"types": ["movie", "4k"]},
        id="sync_movie_4k_job",
        name="电影/4K数据每日凌晨同步(金山文档)",
        replace_existing=True,
    )

    return scheduler
