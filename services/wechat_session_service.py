"""Server-side WeChat session_key cache."""

import logging
import os
from typing import Any

import redis.asyncio as redis

logger = logging.getLogger(__name__)

SESSION_KEY_PREFIX = "wechat:session_key:"
SESSION_KEY_TTL = int(os.getenv("WECHAT_SESSION_KEY_TTL", "7200"))


async def save_session_key(request: Any, openid: str, session_key: str) -> None:
    if not openid or not session_key:
        return
    pool = getattr(getattr(request, "app", None), "state", None)
    redis_pool = getattr(pool, "redis_pool", None)
    if not redis_pool:
        logger.warning("[WeChatSession] Redis pool missing, session_key not cached")
        return
    client = redis.Redis(connection_pool=redis_pool, decode_responses=True)
    try:
        await client.setex(f"{SESSION_KEY_PREFIX}{openid}", SESSION_KEY_TTL, session_key)
    except Exception as exc:
        logger.warning("[WeChatSession] cache session_key failed: %s", exc)
    finally:
        await client.aclose()


async def get_session_key(request: Any, openid: str) -> str:
    if not openid:
        return ""
    pool = getattr(getattr(request, "app", None), "state", None)
    redis_pool = getattr(pool, "redis_pool", None)
    if not redis_pool:
        return ""
    client = redis.Redis(connection_pool=redis_pool, decode_responses=True)
    try:
        return str(await client.get(f"{SESSION_KEY_PREFIX}{openid}") or "")
    except Exception as exc:
        logger.warning("[WeChatSession] read session_key failed: %s", exc)
        return ""
    finally:
        await client.aclose()
