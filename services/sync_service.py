"""
影视资源定时同步服务。

数据来源：金山文档(kdocs) 逆向爬取
功能：
1. 定时从金山文档爬取 anime/movie/4k 资源
2. 按夸克网盘 URL 做去重：匹配到旧记录则删除后重新插入
3. 将外部已删除的数据标记为 is_active=False
"""

import asyncio
import logging
import os
from datetime import datetime

from sqlalchemy import or_, select, update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession

from models.anime_resource import AnimeResource
from models.base import get_session_ctx

logger = logging.getLogger("sync_anime")

SYNC_INTERVAL_MINUTES = int(os.getenv("ANIME_SYNC_INTERVAL", "15"))
SYNC_ENABLED = os.getenv("ANIME_SYNC_ENABLED", "true").lower() == "true"


async def _upsert_anime(session: AsyncSession, item: dict) -> None:
    baidu_url = (item.get("baidu_url") or "").strip()
    quark_url = (item.get("quark_url") or "").strip()
    k4_url = (item.get("4k_url") or "").strip()
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
            source_update_time=source_time,
            is_active=True,
        )
        session.add(resource)


async def sync_anime_from_kdocs(types: list[str] | None = None) -> dict:
    if types is None:
        types = ["anime", "movie", "4k"]

    logger.info("[sync] ====== start kdocs sync (types=%s) ======", types)
    result = {"synced": 0, "inactive": 0, "error": None}

    try:
        from core.kdocs_service import KDocsService

        loop = asyncio.get_event_loop()
        all_items = await loop.run_in_executor(None, KDocsService.crawl_all, types)

        logger.info("[sync] kdocs fetched %s items", len(all_items))

        if not all_items:
            logger.info("[sync] kdocs data is empty, skip sync")
            return result

        async with get_session_ctx() as session:
            external_ids = {
                item.get("anime_id", "")
                for item in all_items
                if item.get("anime_id")
            }

            for item in all_items:
                await _upsert_anime(session, item)
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

            await session.commit()
            logger.info(
                "[sync] completed: upsert=%s inactive=%s",
                result["synced"],
                result["inactive"],
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
        name="番剧数据定时同步(金山文档)",
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
