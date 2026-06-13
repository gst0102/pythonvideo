"""Shared guardrails for browser automation tasks."""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import threading
import time
from contextlib import contextmanager
from typing import Iterator

logger = logging.getLogger(__name__)


def _read_positive_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
        return value if value > 0 else default
    except ValueError:
        return default


_CONCURRENCY = _read_positive_int("BROWSER_AUTOMATION_CONCURRENCY", 1)
_QUEUE_TIMEOUT = _read_positive_int("BROWSER_AUTOMATION_QUEUE_TIMEOUT", 120)
_FORCE_CLEANUP = os.getenv("BROWSER_FORCE_CLEANUP", "true").lower() != "false"
_BROWSER_SEMAPHORE = threading.BoundedSemaphore(_CONCURRENCY)


@contextmanager
def browser_slot(label: str) -> Iterator[None]:
    acquired = _BROWSER_SEMAPHORE.acquire(timeout=_QUEUE_TIMEOUT)
    if not acquired:
        raise TimeoutError(f"browser automation is busy: {label}")

    before_pids = _browser_pids()
    logger.info("[BrowserGuard] acquired slot: %s", label)
    try:
        yield
    finally:
        if _FORCE_CLEANUP:
            _cleanup_new_browser_processes(before_pids, label)
        _BROWSER_SEMAPHORE.release()
        logger.info("[BrowserGuard] released slot: %s", label)


def chromium_launch_args(*extra_args: str) -> list[str]:
    args = [
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--disable-extensions",
        "--disable-background-networking",
        "--disable-background-timer-throttling",
        "--disable-default-apps",
        "--disable-renderer-backgrounding",
        "--disable-sync",
        "--metrics-recording-only",
        "--mute-audio",
        "--no-first-run",
    ]
    args.extend(arg for arg in extra_args if arg)
    return list(dict.fromkeys(args))


def chromium_launch_options(*extra_args: str) -> dict:
    options = {"args": chromium_launch_args(*extra_args)}
    executable_path = os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH", "").strip()
    if not executable_path and os.path.exists("/usr/bin/chromium"):
        executable_path = "/usr/bin/chromium"
    if executable_path:
        options["executable_path"] = executable_path
    return options


def _browser_pids() -> set[int]:
    try:
        result = subprocess.run(
            ["pgrep", "-f", "chromium|chrome|ms-playwright"],
            text=True,
            capture_output=True,
            timeout=3,
            check=False,
        )
    except Exception:
        return set()

    pids: set[int] = set()
    for line in result.stdout.splitlines():
        try:
            pid = int(line.strip())
        except ValueError:
            continue
        if pid != os.getpid():
            pids.add(pid)
    return pids


def _cleanup_new_browser_processes(before_pids: set[int], label: str) -> None:
    leftovers = sorted(_browser_pids() - before_pids)
    if not leftovers:
        return

    logger.warning("[BrowserGuard] cleaning browser leftovers after %s: %s", label, leftovers)
    for sig in (signal.SIGTERM, signal.SIGKILL):
        for pid in leftovers:
            try:
                os.kill(pid, sig)
            except ProcessLookupError:
                pass
            except PermissionError:
                logger.warning("[BrowserGuard] no permission to kill pid=%s", pid)
        if sig == signal.SIGTERM:
            time.sleep(1)
            leftovers = sorted(pid for pid in leftovers if pid in _browser_pids())
            if not leftovers:
                return
