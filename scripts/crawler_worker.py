"""Standalone crawler worker for browser-based netdisk collection."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from models.base import close_db

logger = logging.getLogger("crawler_worker")


async def run_crawler(crawler_key: str) -> dict:
    if crawler_key == "kdocs_anime":
        from services.sync_service import sync_anime_from_kdocs

        return await sync_anime_from_kdocs(["anime"])
    if crawler_key == "kdocs_movie":
        from services.sync_service import sync_anime_from_kdocs

        return await sync_anime_from_kdocs(["movie"])
    if crawler_key == "kdocs_4k":
        from services.sync_service import sync_anime_from_kdocs

        return await sync_anime_from_kdocs(["4k"])
    if crawler_key == "linuxdo":
        from services.linuxdo_resource_service import LINUXDO_SYNC_LIMIT, sync_linuxdo_resources

        return await sync_linuxdo_resources(limit=LINUXDO_SYNC_LIMIT)
    raise HTTPException(status_code=404, detail="未知采集任务")


@asynccontextmanager
async def lifespan(app: FastAPI):
    schedulers = []
    try:
        from services.sync_service import create_scheduler

        scheduler = create_scheduler()
        if scheduler:
            scheduler.start()
            schedulers.append(scheduler)
            logger.info("[crawler-worker] KDocs scheduler started")
    except Exception as exc:
        logger.error("[crawler-worker] KDocs scheduler failed: %s", exc, exc_info=True)

    try:
        from services.linuxdo_resource_service import create_linuxdo_scheduler

        scheduler = create_linuxdo_scheduler()
        if scheduler:
            scheduler.start()
            schedulers.append(scheduler)
            logger.info("[crawler-worker] LinuxDo scheduler started")
    except Exception as exc:
        logger.error("[crawler-worker] LinuxDo scheduler failed: %s", exc, exc_info=True)

    app.state.schedulers = schedulers
    yield

    for scheduler in getattr(app.state, "schedulers", []):
        scheduler.shutdown(wait=False)
    await close_db()


app = FastAPI(title="yuexiang-crawler-worker", lifespan=lifespan)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "crawler-worker",
        "chromium": os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH", ""),
    }


@app.post("/run/{crawler_key}")
async def run_one_crawler(crawler_key: str):
    try:
        result = await run_crawler(crawler_key)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("[crawler-worker] manual run failed: %s", exc, exc_info=True)
        return {"code": 500, "msg": f"采集失败：{exc}", "data": {"error": str(exc)}}
    return {"code": 200, "msg": "采集任务已完成", "data": result}
