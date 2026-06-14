"""Standalone crawler worker for browser-based netdisk collection."""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, Query

from core.browser_guard import browser_process_count, cleanup_all_browser_processes
from models.base import close_db

logger = logging.getLogger("crawler_worker")

CRAWLER_KEYS = {"kdocs_anime", "kdocs_movie", "kdocs_4k", "linuxdo"}
TASK_TIMEOUT_SECONDS = int(os.getenv("CRAWLER_TASK_TIMEOUT_SECONDS", "900"))
FAILURE_BREAKER_THRESHOLD = int(os.getenv("CRAWLER_FAILURE_BREAKER_THRESHOLD", "3"))
FAILURE_BREAKER_COOLDOWN_SECONDS = int(os.getenv("CRAWLER_FAILURE_BREAKER_COOLDOWN_SECONDS", "1800"))
BROWSER_PROCESS_LIMIT = int(os.getenv("CRAWLER_BROWSER_PROCESS_LIMIT", "2"))

_state_lock = asyncio.Lock()
_task_state = {
    key: {
        "key": key,
        "running": False,
        "last_started_at": "",
        "last_finished_at": "",
        "last_success_at": "",
        "last_error": "",
        "last_result": {},
        "consecutive_failures": 0,
        "breaker_until": "",
    }
    for key in CRAWLER_KEYS
}


def _now() -> datetime:
    return datetime.utcnow()


def _iso(value: datetime | None) -> str:
    return value.isoformat() if value else ""


def _parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


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


def _browser_status() -> dict:
    count = browser_process_count()
    cleaned = 0
    if BROWSER_PROCESS_LIMIT > 0 and count > BROWSER_PROCESS_LIMIT:
        cleaned = cleanup_all_browser_processes("crawler-worker browser process limit")
        count = browser_process_count()
    return {
        "browser_processes": count,
        "browser_process_limit": BROWSER_PROCESS_LIMIT,
        "auto_cleaned": cleaned,
    }


async def _snapshot_state() -> dict:
    async with _state_lock:
        tasks = [dict(value) for value in _task_state.values()]
    browser = _browser_status()
    running = [item["key"] for item in tasks if item.get("running")]
    blocked = [item["key"] for item in tasks if _parse_iso(str(item.get("breaker_until") or "")) and _parse_iso(str(item.get("breaker_until"))) > _now()]
    return {
        "status": "degraded" if blocked else "ok",
        "service": "crawler-worker",
        "chromium": os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH", ""),
        "task_timeout_seconds": TASK_TIMEOUT_SECONDS,
        "failure_breaker_threshold": FAILURE_BREAKER_THRESHOLD,
        "failure_breaker_cooldown_seconds": FAILURE_BREAKER_COOLDOWN_SECONDS,
        "running_tasks": running,
        "blocked_tasks": blocked,
        "tasks": tasks,
        **browser,
    }


async def _run_with_state(crawler_key: str, *, force: bool = False) -> dict:
    if crawler_key not in CRAWLER_KEYS:
        raise HTTPException(status_code=404, detail="未知采集任务")

    async with _state_lock:
        task = _task_state[crawler_key]
        if task["running"]:
            raise HTTPException(status_code=409, detail="采集任务正在运行")
        breaker_until = _parse_iso(str(task.get("breaker_until") or ""))
        if breaker_until and breaker_until > _now() and not force:
            raise HTTPException(status_code=429, detail=f"连续失败熔断中，{_iso(breaker_until)} 后可重试")
        task["running"] = True
        task["last_started_at"] = _iso(_now())
        task["last_error"] = ""

    try:
        _browser_status()
        result = await asyncio.wait_for(run_crawler(crawler_key), timeout=TASK_TIMEOUT_SECONDS)
    except Exception as exc:
        async with _state_lock:
            task = _task_state[crawler_key]
            failures = int(task.get("consecutive_failures") or 0) + 1
            task["consecutive_failures"] = failures
            task["last_error"] = str(exc)
            task["last_finished_at"] = _iso(_now())
            task["running"] = False
            if failures >= FAILURE_BREAKER_THRESHOLD:
                task["breaker_until"] = _iso(_now() + timedelta(seconds=FAILURE_BREAKER_COOLDOWN_SECONDS))
        raise
    else:
        async with _state_lock:
            task = _task_state[crawler_key]
            task["consecutive_failures"] = 0
            task["breaker_until"] = ""
            task["last_error"] = ""
            task["last_result"] = result
            task["last_success_at"] = _iso(_now())
            task["last_finished_at"] = _iso(_now())
            task["running"] = False
        return result
    finally:
        cleanup_all_browser_processes(f"crawler-worker run {crawler_key}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    schedulers = []
    cleaned = cleanup_all_browser_processes("crawler-worker startup")
    if cleaned:
        logger.warning("[crawler-worker] cleaned %s stale browser processes on startup", cleaned)
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
    cleanup_all_browser_processes("crawler-worker shutdown")
    await close_db()


app = FastAPI(title="yuexiang-crawler-worker", lifespan=lifespan)


@app.get("/health")
async def health_check():
    return await _snapshot_state()


@app.get("/status")
async def worker_status():
    return await _snapshot_state()


@app.post("/maintenance/cleanup-browsers")
async def cleanup_browsers():
    before = browser_process_count()
    cleaned = cleanup_all_browser_processes("crawler-worker manual cleanup")
    after = browser_process_count()
    return {"code": 200, "msg": "浏览器进程清理完成", "data": {"before": before, "cleaned": cleaned, "after": after}}


@app.post("/run/{crawler_key}")
async def run_one_crawler(crawler_key: str, force: bool = Query(False)):
    try:
        result = await _run_with_state(crawler_key, force=force)
    except HTTPException:
        raise
    except asyncio.TimeoutError:
        logger.error("[crawler-worker] manual run timeout: %s", crawler_key, exc_info=True)
        return {"code": 504, "msg": f"采集超时，已关闭浏览器进程：{crawler_key}", "data": {"error": "timeout"}}
    except Exception as exc:
        logger.error("[crawler-worker] manual run failed: %s", exc, exc_info=True)
        return {"code": 500, "msg": f"采集失败：{exc}", "data": {"error": str(exc)}}
    return {"code": 200, "msg": "采集任务已完成", "data": result}
