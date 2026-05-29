"""
影视资源定时同步服务

功能：
  1. 每 15 分钟从外部 API 拉取番剧数据
  2. 按 baidu_url / quark_url 做唯一去重 upsert
  3. 标记外部已删除的记录为 is_active=False

架构：
  - 使用 APScheduler AsyncIOScheduler 在 FastAPI lifespan 中注册
  - httpx 异步请求外部 API
  - 事务包裹整个同步批次，保证一致性
"""

import os
import logging
from datetime import datetime

import httpx
import urllib3
from dotenv import load_dotenv

# 同步任务调自己的服务器，关闭 SSL 校验和警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from sqlalchemy import select, or_, update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from models.base import get_session_ctx
from models.anime_resource import AnimeResource

load_dotenv()
logger = logging.getLogger("sync_anime")

# ── 配置 ──
ANIME_SOURCE_URL = os.getenv(
    "ANIME_SOURCE_URL",
    "https://api.lifelove.top/api/anime",
)

SYNC_TYPES = ["anime"]  # 番剧每15分钟同步
SYNC_TYPES_DAILY = ["movie", "4k"]  # 电影/4K 每天早上8点同步
SYNC_PAGE_SIZE = 100

# 同步间隔（分钟）
SYNC_INTERVAL_MINUTES = int(os.getenv("ANIME_SYNC_INTERVAL", "15"))
# 同步开关（本地开发可关闭）
SYNC_ENABLED = os.getenv("ANIME_SYNC_ENABLED", "true").lower() == "true"


async def _fetch_page(
    client: httpx.AsyncClient,
    type_name: str,
    page: int,
) -> dict:
    """拉取单页数据。外部 API 不可用时返回空数据，不抛异常"""
    url = f"{ANIME_SOURCE_URL}/library"
    params = {
        "type": type_name,
        "page": page,
        "page_size": SYNC_PAGE_SIZE,
    }
    logger.info(f"[sync] 请求 {url} page={page}")
    try:
        resp = await client.get(url, params=params, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            logger.warning(f"[sync] 外部 API 返回错误: {data}")
            return {}
        return data.get("data", {})
    except Exception as e:
        logger.warning(f"[sync] 外部 API 不可用（{type_name} page={page}）: {e}")
        return {}


async def _fetch_all_anime(client: httpx.AsyncClient, type_name: str) -> list[dict]:
    """拉取指定类型的全部数据（自动分页）"""
    all_items: list[dict] = []
    page = 1

    while True:
        data = await _fetch_page(client, type_name, page)
        items = data.get("list", [])
        total = data.get("total", 0)

        all_items.extend(items)
        logger.info(
            f"[sync] {type_name} page={page}: 获取 {len(items)} 条, "
            f"累计 {len(all_items)}/{total}"
        )

        # 数据拿完了就停
        if len(all_items) >= total or len(items) == 0:
            break

        page += 1

    return all_items


async def _upsert_anime(session: AsyncSession, item: dict) -> None:
    """
    按 baidu_url / quark_url 查找已有记录，执行 upsert。

    策略：
      - baidu_url 或 quark_url 匹配 → 更新现有记录
      - 都不匹配 → 插入新记录
      - 如果 URL 匹配但 anime_id 不同 → 用新数据覆盖（数据源可能重新生成了 ID）
    """
    baidu_url = (item.get("baidu_url") or "").strip()
    quark_url = (item.get("quark_url") or "").strip()

    # 构建 URL 匹配条件
    conditions = []
    if baidu_url:
        conditions.append(AnimeResource.baidu_url == baidu_url)
    if quark_url:
        conditions.append(AnimeResource.quark_url == quark_url)

    existing = None
    if conditions:
        result = await session.execute(
            select(AnimeResource).where(or_(*conditions))
        )
        existing = result.scalars().first()

    now = datetime.utcnow()

    if existing:
        # URL 匹配 → 更新
        existing.anime_id = item.get("anime_id", existing.anime_id)
        existing.title = item.get("title", existing.title)
        existing.quality = item.get("quality")
        existing.episode = item.get("episode")
        existing.status = item.get("status")
        existing.baidu_url = baidu_url or None
        existing.baidu_password = item.get("baidu_password")
        existing.quark_url = quark_url or None
        existing.is_active = True
        existing.updated_at = now

        raw_time = item.get("update_time") or item.get("updated_at")
        if raw_time:
            try:
                existing.source_update_time = datetime.fromisoformat(
                    raw_time.replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                pass

        session.add(existing)
    else:
        # 全新记录 → 插入
        raw_time = item.get("update_time") or item.get("updated_at")
        source_time = None
        if raw_time:
            try:
                source_time = datetime.fromisoformat(
                    raw_time.replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                pass

        resource = AnimeResource(
            anime_id=item.get("anime_id", ""),
            title=item.get("title", ""),
            category=item.get("category", "anime"),
            quality=item.get("quality"),
            episode=item.get("episode"),
            status=item.get("status"),
            baidu_url=baidu_url or None,
            baidu_password=item.get("baidu_password"),
            quark_url=quark_url or None,
            source_update_time=source_time,
            is_active=True,
        )
        session.add(resource)


async def sync_anime_from_external(types: list[str] | None = None) -> dict:
    """
    执行一次完整的同步任务。

    Args:
        types: 要同步的资源类型列表，默认 ["anime"]

    Returns:
        dict: {"synced": int, "inactive": int, "error": str|None}
    """
    if types is None:
        types = SYNC_TYPES

    logger.info(f"[sync] ====== 开始同步数据 (types={types}) ======")
    result = {"synced": 0, "inactive": 0, "error": None}

    try:
        async with httpx.AsyncClient(verify=False) as client:
            # 1. 拉取所有指定类型数据
            all_items: list[dict] = []
            for type_name in types:
                items = await _fetch_all_anime(client, type_name)
                all_items.extend(items)

            logger.info(f"[sync] 拉取完成，共 {len(all_items)} 条")

            if not all_items:
                logger.info("[sync] 外部数据为空，跳过同步")
                return result

            # 2. 事务内 upsert
            async with get_session_ctx() as session:
                # 收集所有外部 anime_id
                external_ids = {item.get("anime_id", "") for item in all_items if item.get("anime_id")}

                # 逐条 upsert
                for item in all_items:
                    await _upsert_anime(session, item)
                    result["synced"] += 1

                # 3. 标记外部已删除的记录
                if external_ids:
                    stmt = (
                        sql_update(AnimeResource)
                        .where(
                            AnimeResource.category.in_(SYNC_TYPES),
                            AnimeResource.is_active == True,
                            AnimeResource.anime_id.not_in(external_ids),
                        )
                        .values(is_active=False)
                    )
                    exec_result = await session.execute(stmt)
                    result["inactive"] = exec_result.rowcount or 0

                await session.commit()
                logger.info(
                    f"[sync] 同步完成 — upsert {result['synced']} 条, "
                    f"标记失效 {result['inactive']} 条"
                )

    except Exception as e:
        logger.error(f"[sync] 同步失败: {e}", exc_info=True)
        result["error"] = str(e)

    return result


def create_scheduler():
    """创建并配置 APScheduler 实例（未启用时返回 None）"""
    if not SYNC_ENABLED:
        logger.info("[sync] 同步功能已关闭（ANIME_SYNC_ENABLED=false）")
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

    # 番剧：每 N 分钟执行
    scheduler.add_job(
        sync_anime_from_external,
        "interval",
        minutes=SYNC_INTERVAL_MINUTES,
        kwargs={"types": ["anime"]},
        id="sync_anime_job",
        name="番剧数据定时同步",
        replace_existing=True,
    )

    # 电影 + 4K：每天早上 8:00 执行
    scheduler.add_job(
        sync_anime_from_external,
        "cron",
        hour=8,
        minute=0,
        kwargs={"types": ["movie", "4k"]},
        id="sync_movie_4k_job",
        name="电影/4K数据每日同步",
        replace_existing=True,
    )

    return scheduler
