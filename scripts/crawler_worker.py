"""Standalone crawler worker for browser-based netdisk collection."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, Query
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlmodel import select

from core.browser_guard import browser_process_count, cleanup_all_browser_processes
from models.base import close_db, get_session_ctx
from models.netdisk_crawler_run import NetdiskCrawlerRun

logger = logging.getLogger("crawler_worker")

CRAWLER_KEYS = {"kdocs_anime", "kdocs_movie", "kdocs_4k", "linuxdo"}
TASK_TIMEOUT_SECONDS = int(os.getenv("CRAWLER_TASK_TIMEOUT_SECONDS", "900"))
FAILURE_BREAKER_THRESHOLD = int(os.getenv("CRAWLER_FAILURE_BREAKER_THRESHOLD", "3"))
FAILURE_BREAKER_COOLDOWN_SECONDS = int(os.getenv("CRAWLER_FAILURE_BREAKER_COOLDOWN_SECONDS", "1800"))
BROWSER_PROCESS_LIMIT = int(os.getenv("CRAWLER_BROWSER_PROCESS_LIMIT", "2"))
BROWSER_STALE_SECONDS = int(os.getenv("CRAWLER_BROWSER_STALE_SECONDS", "300"))
WORKER_TIMEZONE = os.getenv("TZ", "Asia/Shanghai")
RECENT_RUN_HISTORY_LIMIT = int(os.getenv("CRAWLER_RECENT_RUN_HISTORY_LIMIT", "8"))

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


def _serialize_result_payload(result: dict | None) -> str:
    if not result:
        return "{}"
    try:
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception:
        logger.warning("[crawler-worker] failed to serialize result payload", exc_info=True)
        return "{}"


def _deserialize_result_payload(payload: str) -> dict:
    if not payload:
        return {}
    try:
        data = json.loads(payload)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _summarize_recent_run(row: NetdiskCrawlerRun) -> dict:
    payload = _deserialize_result_payload(row.result_payload)
    return {
        "id": str(row.id),
        "crawler_key": row.crawler_key,
        "trigger_source": row.trigger_source,
        "status": row.status,
        "started_at": _iso(row.started_at),
        "finished_at": _iso(row.finished_at),
        "duration_seconds": int(row.duration_seconds or 0),
        "synced_count": int(row.synced_count or 0),
        "inactive_count": int(row.inactive_count or 0),
        "auto_published_count": int(row.auto_published_count or 0),
        "review_required_count": int(row.review_required_count or 0),
        "skipped_count": int(row.skipped_count or 0),
        "failed_count": int(row.failed_count or 0),
        "netdisk_inactive_count": int(row.netdisk_inactive_count or 0),
        "consecutive_failures": int(row.consecutive_failures or 0),
        "error_text": row.error_text or "",
        "result_payload": payload,
    }


async def _persist_run_history(
    crawler_keys: list[str],
    *,
    trigger_source: str,
    status: str,
    started_at: datetime,
    finished_at: datetime,
    result: dict | None = None,
    error_text: str = "",
    consecutive_failures: int = 0,
) -> None:
    payload = result or {}
    duration_seconds = max(int((finished_at - started_at).total_seconds()), 0)
    try:
        async with get_session_ctx() as session:
            for crawler_key in crawler_keys:
                session.add(
                    NetdiskCrawlerRun(
                        crawler_key=crawler_key,
                        trigger_source=trigger_source,
                        status=status,
                        started_at=started_at,
                        finished_at=finished_at,
                        duration_seconds=duration_seconds,
                        synced_count=int(payload.get("synced") or 0),
                        inactive_count=int(payload.get("inactive") or 0),
                        auto_published_count=int(payload.get("auto_published") or 0),
                        review_required_count=int(payload.get("review_required") or 0),
                        skipped_count=int(payload.get("skipped") or 0),
                        failed_count=int(payload.get("failed") or 0),
                        netdisk_inactive_count=int(payload.get("netdisk_inactive") or 0),
                        consecutive_failures=consecutive_failures,
                        result_payload=_serialize_result_payload(payload),
                        error_text=error_text,
                    )
                )
    except Exception:
        logger.error("[crawler-worker] failed to persist run history", exc_info=True)


async def _load_recent_runs(limit: int = RECENT_RUN_HISTORY_LIMIT) -> list[dict]:
    try:
        async with get_session_ctx() as session:
            rows = (
                await session.execute(
                    select(NetdiskCrawlerRun)
                    .order_by(NetdiskCrawlerRun.started_at.desc(), NetdiskCrawlerRun.created_at.desc())
                    .limit(limit)
                )
            ).scalars().all()
        return [_summarize_recent_run(row) for row in rows]
    except Exception:
        logger.error("[crawler-worker] failed to load recent run history", exc_info=True)
        return []


async def _restore_task_state_from_history() -> None:
    try:
        async with get_session_ctx() as session:
            for crawler_key in CRAWLER_KEYS:
                latest_row = (
                    await session.execute(
                        select(NetdiskCrawlerRun)
                        .where(NetdiskCrawlerRun.crawler_key == crawler_key)
                        .order_by(NetdiskCrawlerRun.started_at.desc(), NetdiskCrawlerRun.created_at.desc())
                        .limit(1)
                    )
                ).scalars().first()
                latest_success_row = (
                    await session.execute(
                        select(NetdiskCrawlerRun)
                        .where(NetdiskCrawlerRun.crawler_key == crawler_key, NetdiskCrawlerRun.status == "success")
                        .order_by(NetdiskCrawlerRun.finished_at.desc(), NetdiskCrawlerRun.created_at.desc())
                        .limit(1)
                    )
                ).scalars().first()
                if not latest_row and not latest_success_row:
                    continue
                payload = _deserialize_result_payload(latest_row.result_payload) if latest_row else {}
                async with _state_lock:
                    task = _task_state[crawler_key]
                    task["running"] = False
                    task["last_started_at"] = _iso(latest_row.started_at) if latest_row else ""
                    task["last_finished_at"] = _iso(latest_row.finished_at) if latest_row else ""
                    task["last_result"] = payload
                    task["consecutive_failures"] = int(latest_row.consecutive_failures or 0) if latest_row else 0
                    task["breaker_until"] = ""
                    task["last_success_at"] = _iso(latest_success_row.finished_at) if latest_success_row else ""
                    if latest_row and latest_row.status == "success":
                        task["last_error"] = ""
                    else:
                        task["last_error"] = latest_row.error_text or latest_row.status if latest_row else ""
        logger.info("[crawler-worker] restored persisted task state from run history")
    except Exception:
        logger.error("[crawler-worker] failed to restore persisted task state", exc_info=True)


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


def _browser_status(*, auto_cleanup: bool = False) -> dict:
    count = browser_process_count()
    cleaned = 0
    if auto_cleanup and BROWSER_PROCESS_LIMIT > 0 and count > BROWSER_PROCESS_LIMIT:
        cleaned = cleanup_all_browser_processes(
            "crawler-worker browser process limit",
            min_age_seconds=BROWSER_STALE_SECONDS,
        )
        count = browser_process_count()
    return {
        "browser_processes": count,
        "browser_process_limit": BROWSER_PROCESS_LIMIT,
        "browser_stale_seconds": BROWSER_STALE_SECONDS,
        "auto_cleaned": cleaned,
    }


def _result_error(result: dict | None) -> str:
    if not isinstance(result, dict):
        return "采集结果格式异常"
    return str(result.get("error") or "").strip()


async def _attach_featured_preview(result: dict | None) -> dict:
    payload = dict(result or {})
    try:
        from services.netdisk_resource_service import NetdiskResourceService

        async with get_session_ctx() as session:
            preview_payload = await NetdiskResourceService.list_today_featured_resources(session, limit=3)
        payload["featured_preview"] = [
            {
                "id": item.get("id", ""),
                "title": item.get("title", ""),
                "pan": item.get("pan", ""),
                "published_at": item.get("published_at", ""),
                "verified_at": item.get("verified_at", ""),
                "source_type": item.get("source_type", ""),
            }
            for item in preview_payload.get("resources", [])[:3]
        ]
        payload["featured_preview_total"] = int(preview_payload.get("today_total") or 0)
        payload["featured_preview_generated_at"] = _iso(_now())
    except Exception:
        logger.warning("[crawler-worker] failed to attach featured preview", exc_info=True)
        payload.setdefault("featured_preview", [])
    return payload


async def _snapshot_state() -> dict:
    async with _state_lock:
        tasks = [dict(value) for value in _task_state.values()]
    browser = _browser_status()
    running = [item["key"] for item in tasks if item.get("running")]
    blocked = [item["key"] for item in tasks if _parse_iso(str(item.get("breaker_until") or "")) and _parse_iso(str(item.get("breaker_until"))) > _now()]
    recent_runs = await _load_recent_runs()
    scheduler_jobs = []
    scheduler = getattr(app.state, "worker_scheduler", None)
    if scheduler:
        for job in scheduler.get_jobs():
            scheduler_jobs.append(
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": _iso(job.next_run_time) if getattr(job, "next_run_time", None) else "",
                }
            )
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
        "recent_runs": recent_runs,
        "scheduler_jobs": scheduler_jobs,
        **browser,
    }


async def _run_with_state(crawler_key: str, *, force: bool = False, trigger_source: str = "manual") -> dict:
    if crawler_key not in CRAWLER_KEYS:
        raise HTTPException(status_code=404, detail="未知采集任务")

    started_at = _now()
    async with _state_lock:
        task = _task_state[crawler_key]
        if task["running"]:
            raise HTTPException(status_code=409, detail="采集任务正在运行")
        breaker_until = _parse_iso(str(task.get("breaker_until") or ""))
        if breaker_until and breaker_until > _now() and not force:
            raise HTTPException(status_code=429, detail=f"连续失败熔断中，{_iso(breaker_until)} 后可重试")
        task["running"] = True
        task["last_started_at"] = _iso(started_at)
        task["last_error"] = ""

    try:
        _browser_status(auto_cleanup=True)
        result = await asyncio.wait_for(run_crawler(crawler_key), timeout=TASK_TIMEOUT_SECONDS)
        if error_text := _result_error(result):
            raise RuntimeError(error_text)
        result = await _attach_featured_preview(result)
    except asyncio.TimeoutError:
        finished_at = _now()
        async with _state_lock:
            task = _task_state[crawler_key]
            failures = int(task.get("consecutive_failures") or 0) + 1
            task["consecutive_failures"] = failures
            task["last_error"] = "timeout"
            task["last_finished_at"] = _iso(finished_at)
            task["running"] = False
            if failures >= FAILURE_BREAKER_THRESHOLD:
                task["breaker_until"] = _iso(_now() + timedelta(seconds=FAILURE_BREAKER_COOLDOWN_SECONDS))
        await _persist_run_history(
            [crawler_key],
            trigger_source=trigger_source,
            status="timeout",
            started_at=started_at,
            finished_at=finished_at,
            error_text="timeout",
            consecutive_failures=failures,
        )
        raise
    except Exception as exc:
        finished_at = _now()
        async with _state_lock:
            task = _task_state[crawler_key]
            failures = int(task.get("consecutive_failures") or 0) + 1
            task["consecutive_failures"] = failures
            task["last_error"] = str(exc)
            task["last_finished_at"] = _iso(finished_at)
            task["running"] = False
            if failures >= FAILURE_BREAKER_THRESHOLD:
                task["breaker_until"] = _iso(_now() + timedelta(seconds=FAILURE_BREAKER_COOLDOWN_SECONDS))
        await _persist_run_history(
            [crawler_key],
            trigger_source=trigger_source,
            status="failed",
            started_at=started_at,
            finished_at=finished_at,
            error_text=str(exc),
            consecutive_failures=failures,
        )
        raise
    else:
        finished_at = _now()
        async with _state_lock:
            task = _task_state[crawler_key]
            task["consecutive_failures"] = 0
            task["breaker_until"] = ""
            task["last_error"] = ""
            task["last_result"] = result
            task["last_success_at"] = _iso(finished_at)
            task["last_finished_at"] = _iso(finished_at)
            task["running"] = False
        await _persist_run_history(
            [crawler_key],
            trigger_source=trigger_source,
            status="success",
            started_at=started_at,
            finished_at=finished_at,
            result=result,
            consecutive_failures=0,
        )
        return result
    finally:
        cleanup_all_browser_processes(f"crawler-worker run {crawler_key}")


async def _run_movie_4k_sync() -> dict:
    from services.sync_service import sync_anime_from_kdocs

    return await sync_anime_from_kdocs(["movie", "4k"])


async def _run_multi_key_job(crawler_keys: list[str], runner, *, force: bool = False, trigger_source: str = "manual") -> dict:
    started_at = _now()
    async with _state_lock:
        now_iso = _iso(started_at)
        for crawler_key in crawler_keys:
            task = _task_state[crawler_key]
            if task["running"]:
                raise HTTPException(status_code=409, detail=f"采集任务正在运行: {crawler_key}")
            breaker_until = _parse_iso(str(task.get("breaker_until") or ""))
            if breaker_until and breaker_until > _now() and not force:
                raise HTTPException(status_code=429, detail=f"连续失败熔断中，{crawler_key} 需等待到 {_iso(breaker_until)}")
        for crawler_key in crawler_keys:
            task = _task_state[crawler_key]
            task["running"] = True
            task["last_started_at"] = now_iso
            task["last_error"] = ""

    try:
        _browser_status(auto_cleanup=True)
        result = await asyncio.wait_for(runner(), timeout=TASK_TIMEOUT_SECONDS)
        if error_text := _result_error(result):
            raise RuntimeError(error_text)
        result = await _attach_featured_preview(result)
    except asyncio.TimeoutError:
        finished_at = _now()
        async with _state_lock:
            for crawler_key in crawler_keys:
                task = _task_state[crawler_key]
                failures = int(task.get("consecutive_failures") or 0) + 1
                task["consecutive_failures"] = failures
                task["last_error"] = "timeout"
                task["last_finished_at"] = _iso(finished_at)
                task["running"] = False
                if failures >= FAILURE_BREAKER_THRESHOLD:
                    task["breaker_until"] = _iso(_now() + timedelta(seconds=FAILURE_BREAKER_COOLDOWN_SECONDS))
        await _persist_run_history(
            crawler_keys,
            trigger_source=trigger_source,
            status="timeout",
            started_at=started_at,
            finished_at=finished_at,
            error_text="timeout",
            consecutive_failures=max(int(_task_state[key]["consecutive_failures"] or 0) for key in crawler_keys),
        )
        raise
    except Exception as exc:
        finished_at = _now()
        async with _state_lock:
            finished_at_iso = _iso(finished_at)
            for crawler_key in crawler_keys:
                task = _task_state[crawler_key]
                failures = int(task.get("consecutive_failures") or 0) + 1
                task["consecutive_failures"] = failures
                task["last_error"] = str(exc)
                task["last_finished_at"] = finished_at_iso
                task["running"] = False
                if failures >= FAILURE_BREAKER_THRESHOLD:
                    task["breaker_until"] = _iso(_now() + timedelta(seconds=FAILURE_BREAKER_COOLDOWN_SECONDS))
        await _persist_run_history(
            crawler_keys,
            trigger_source=trigger_source,
            status="failed",
            started_at=started_at,
            finished_at=finished_at,
            error_text=str(exc),
            consecutive_failures=max(int(_task_state[key]["consecutive_failures"] or 0) for key in crawler_keys),
        )
        raise
    else:
        finished_at = _now()
        async with _state_lock:
            finished_at_iso = _iso(finished_at)
            for crawler_key in crawler_keys:
                task = _task_state[crawler_key]
                task["consecutive_failures"] = 0
                task["breaker_until"] = ""
                task["last_error"] = ""
                task["last_result"] = result
                task["last_success_at"] = finished_at_iso
                task["last_finished_at"] = finished_at_iso
                task["running"] = False
        await _persist_run_history(
            crawler_keys,
            trigger_source=trigger_source,
            status="success",
            started_at=started_at,
            finished_at=finished_at,
            result=result,
            consecutive_failures=0,
        )
        return result
    finally:
        cleanup_all_browser_processes(f"crawler-worker run {'+'.join(crawler_keys)}")


async def _run_scheduled_crawler(crawler_key: str) -> dict:
    try:
        result = await _run_with_state(crawler_key, trigger_source="schedule")
        logger.info("[crawler-worker] scheduled run %s succeeded: %s", crawler_key, result)
        return result
    except Exception as exc:
        logger.error("[crawler-worker] scheduled run %s failed: %s", crawler_key, exc, exc_info=True)
        raise


async def _run_scheduled_movie_4k() -> dict:
    try:
        result = await _run_multi_key_job(["kdocs_movie", "kdocs_4k"], _run_movie_4k_sync, trigger_source="schedule")
        logger.info("[crawler-worker] scheduled run kdocs_movie+kdocs_4k succeeded: %s", result)
        return result
    except Exception as exc:
        logger.error("[crawler-worker] scheduled run kdocs_movie+kdocs_4k failed: %s", exc, exc_info=True)
        raise


def _build_worker_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(
        timezone=WORKER_TIMEZONE,
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 120,
        },
    )
    if os.getenv("ANIME_SYNC_ENABLED", "true").lower() == "true":
        anime_interval_minutes = int(os.getenv("ANIME_SYNC_INTERVAL", "60"))
        if anime_interval_minutes == 60:
            scheduler.add_job(
                _run_scheduled_crawler,
                "cron",
                minute=30,
                kwargs={"crawler_key": "kdocs_anime"},
                id="sync_anime_job",
                name="影视剧数据每小时30分同步(金山文档)",
                replace_existing=True,
            )
        else:
            scheduler.add_job(
                _run_scheduled_crawler,
                "interval",
                minutes=anime_interval_minutes,
                kwargs={"crawler_key": "kdocs_anime"},
                id="sync_anime_job",
                name="影视剧数据定时间隔同步(金山文档)",
                replace_existing=True,
            )
    scheduler.add_job(
        _run_scheduled_movie_4k,
        "cron",
        hour=0,
        minute=0,
        id="sync_movie_4k_job",
        name="电影/4K数据每日凌晨同步(金山文档)",
        replace_existing=True,
    )
    if os.getenv("LINUXDO_SYNC_ENABLED", "true").lower() == "true":
        scheduler.add_job(
            _run_scheduled_crawler,
            "interval",
            hours=int(os.getenv("LINUXDO_SYNC_INTERVAL_HOURS", "12")),
            kwargs={"crawler_key": "linuxdo"},
            id="linuxdo_netdisk_12h_sync",
            name="LinuxDo云资产每12小时同步",
            replace_existing=True,
        )
    return scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    cleaned = cleanup_all_browser_processes("crawler-worker startup")
    if cleaned:
        logger.warning("[crawler-worker] cleaned %s stale browser processes on startup", cleaned)
    await _restore_task_state_from_history()
    try:
        scheduler = _build_worker_scheduler()
        scheduler.start()
        app.state.worker_scheduler = scheduler
        for job in scheduler.get_jobs():
            logger.info(
                "[crawler-worker] scheduler job registered id=%s next_run=%s",
                job.id,
                _iso(job.next_run_time) if getattr(job, "next_run_time", None) else "",
            )
        logger.info("[crawler-worker] worker scheduler started")
    except Exception as exc:
        app.state.worker_scheduler = None
        logger.error("[crawler-worker] worker scheduler failed: %s", exc, exc_info=True)

    yield

    scheduler = getattr(app.state, "worker_scheduler", None)
    if scheduler:
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
    async with _state_lock:
        running = [key for key, task in _task_state.items() if task.get("running")]
    if running:
        return {
            "code": 409,
            "msg": f"采集任务运行中，暂不清理浏览器进程：{', '.join(running)}",
            "data": {"running_tasks": running},
        }
    before = browser_process_count()
    cleaned = cleanup_all_browser_processes(
        "crawler-worker manual cleanup",
        min_age_seconds=BROWSER_STALE_SECONDS,
    )
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
