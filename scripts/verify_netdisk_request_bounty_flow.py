"""Verify netdisk request bounty P0 flow.

This script expects DATABASE_URL to point to a disposable test database.
It calls FastAPI routes through ASGI transport, then checks account and
ledger state directly.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import sys

import httpx
from sqlmodel import select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main import app  # noqa: E402
from models.base import get_session_ctx  # noqa: E402
from models.netdisk_request import NetdiskRequest  # noqa: E402
from models.points_ledger import PointsLedger  # noqa: E402
from models.user import User  # noqa: E402
from models.user_account import UserAccount  # noqa: E402


def _assert_equal(name: str, actual, expected) -> None:
    if actual != expected:
        raise AssertionError(f"{name}: expected {expected}, got {actual}")


async def _post(client: httpx.AsyncClient, url: str, json: dict | None = None, token: str | None = None) -> dict:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    response = await client.post(url, json=json or {}, headers=headers)
    try:
        payload = response.json()
    except Exception as exc:
        raise AssertionError(f"{url} did not return JSON: {response.text}") from exc
    if response.status_code >= 400:
        raise AssertionError(f"{url} failed: HTTP {response.status_code}, {payload}")
    return payload


async def _get(client: httpx.AsyncClient, url: str, token: str | None = None) -> dict:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    response = await client.get(url, headers=headers)
    payload = response.json()
    if response.status_code >= 400:
        raise AssertionError(f"{url} failed: HTTP {response.status_code}, {payload}")
    return payload


async def _post_expect_status(
    client: httpx.AsyncClient,
    url: str,
    status_code: int,
    json: dict | None = None,
    token: str | None = None,
) -> dict:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    response = await client.post(url, json=json or {}, headers=headers)
    payload = response.json()
    _assert_equal(f"{url} status", response.status_code, status_code)
    return payload


async def _login(client: httpx.AsyncClient, openid: str, nickname: str, seed_points: int) -> tuple[str, str]:
    payload = await _post(
        client,
        "/user/dev-login",
        {"openid": openid, "nickname": nickname, "seed_points": seed_points},
    )
    return payload["data"]["token"], payload["data"]["user"]["id"]


async def _account(user_id: str) -> UserAccount:
    async with get_session_ctx() as session:
        result = await session.execute(select(UserAccount).where(UserAccount.user_id == user_id))
        account = result.scalar_one()
        return account


async def _ledger_count(change_type: str, related_id: str) -> int:
    async with get_session_ctx() as session:
        result = await session.execute(
            select(PointsLedger).where(
                PointsLedger.change_type == change_type,
                PointsLedger.related_id == related_id,
            )
        )
        return len(result.scalars().all())


async def _set_request_expired(request_id: str) -> None:
    async with get_session_ctx() as session:
        result = await session.execute(select(NetdiskRequest).where(NetdiskRequest.id == request_id))
        item = result.scalar_one()
        item.expires_at = datetime.utcnow() - timedelta(minutes=1)
        item.updated_at = datetime.utcnow()


async def main() -> None:
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        client = httpx.AsyncClient(transport=transport, base_url="http://testserver")
        publisher_token, publisher_id = await _login(client, "bounty-publisher", "悬赏发布者", 100)
        submitter_token, submitter_id = await _login(client, "bounty-submitter", "投稿者", 20)
        low_token, _ = await _login(client, "bounty-low", "低积分用户", 5)

        insufficient = await _post_expect_status(
            client,
            "/netdisk/requests",
            400,
            {
                "title": "求高赏资源",
                "pans": ["夸克"],
                "category": "学习办公",
                "bounty_points": 50,
                "note": "积分不足应失败",
            },
            low_token,
        )
        if "可用积分不足" not in insufficient.get("msg", ""):
            raise AssertionError(f"insufficient message mismatch: {insufficient}")

        created = await _post(
            client,
            "/netdisk/requests",
            {
                "title": "求 Excel 悬赏模板",
                "pans": ["夸克"],
                "category": "学习办公",
                "bounty_points": 20,
                "note": "P0 联调",
            },
            publisher_token,
        )
        request_id = created["data"]["request"]["id"]
        account = await _account(publisher_id)
        _assert_equal("publisher consumable after freeze", int(account.consumable_points), 80)
        _assert_equal("publisher frozen after freeze", int(account.frozen_points), 20)
        _assert_equal("freeze ledger count", await _ledger_count("request_bounty_freeze", request_id), 1)

        await _post_expect_status(
            client,
            f"/netdisk/requests/{request_id}/submissions",
            400,
            {
                "title": "自己的投稿",
                "category": "学习办公",
                "pan": "夸克",
                "link": "https://pan.quark.cn/s/self",
                "description": "应失败",
            },
            publisher_token,
        )

        submission = await _post(
            client,
            f"/netdisk/requests/{request_id}/submissions",
            {
                "title": "Excel 悬赏模板投稿",
                "category": "学习办公",
                "pan": "夸克",
                "link": "https://pan.quark.cn/s/bounty-ok",
                "description": "符合需求的资源",
            },
            submitter_token,
        )
        upload_id = submission["data"]["upload"]["id"]
        await _post_expect_status(
            client,
            f"/netdisk/requests/{request_id}/submissions",
            400,
            {
                "title": "重复投稿",
                "category": "学习办公",
                "pan": "夸克",
                "link": "https://pan.quark.cn/s/bounty-repeat",
                "description": "应失败",
            },
            submitter_token,
        )
        submissions = await _get(client, f"/netdisk/requests/{request_id}/submissions", publisher_token)
        _assert_equal("submission count visible to publisher", len(submissions["data"]["submissions"]), 1)

        accepted = await _post(
            client,
            f"/netdisk/requests/{request_id}/submissions/{upload_id}/accept",
            token=publisher_token,
        )
        _assert_equal("accepted status", accepted["data"]["request"]["status"], "accepted")
        publisher_account = await _account(publisher_id)
        submitter_account = await _account(submitter_id)
        _assert_equal("publisher consumable after accept", int(publisher_account.consumable_points), 80)
        _assert_equal("publisher frozen after accept", int(publisher_account.frozen_points), 0)
        _assert_equal("submitter consumable after accept", int(submitter_account.consumable_points), 40)
        _assert_equal("award ledger count", await _ledger_count("request_bounty_award", request_id), 2)

        await _post_expect_status(
            client,
            f"/netdisk/requests/{request_id}/submissions/{upload_id}/accept",
            400,
            token=publisher_token,
        )
        submitter_after_repeat = await _account(submitter_id)
        _assert_equal("submitter no duplicate award", int(submitter_after_repeat.consumable_points), 40)

        cancel_created = await _post(
            client,
            "/netdisk/requests",
            {
                "title": "求可取消资源",
                "pans": ["百度"],
                "category": "学习办公",
                "bounty_points": 15,
                "note": "用于取消退回",
            },
            publisher_token,
        )
        cancel_id = cancel_created["data"]["request"]["id"]
        canceled = await _post(client, f"/netdisk/requests/{cancel_id}/cancel", token=publisher_token)
        _assert_equal("canceled status", canceled["data"]["request"]["status"], "canceled")
        publisher_after_cancel = await _account(publisher_id)
        _assert_equal("publisher consumable after cancel", int(publisher_after_cancel.consumable_points), 80)
        _assert_equal("publisher frozen after cancel", int(publisher_after_cancel.frozen_points), 0)
        _assert_equal("return ledger count", await _ledger_count("request_bounty_return", cancel_id), 1)
        await _post_expect_status(client, f"/netdisk/requests/{cancel_id}/cancel", 400, token=publisher_token)

        expire_created = await _post(
            client,
            "/netdisk/requests",
            {
                "title": "求过期资源",
                "pans": ["阿里"],
                "category": "学习办公",
                "bounty_points": 10,
                "note": "用于过期退回",
            },
            publisher_token,
        )
        expire_id = expire_created["data"]["request"]["id"]
        await _set_request_expired(expire_id)
        expired = await _post(client, "/netdisk/requests/expire")
        if expired["data"]["expired_count"] < 1:
            raise AssertionError(f"expire did not process request: {expired}")
        publisher_after_expire = await _account(publisher_id)
        _assert_equal("publisher consumable after expire", int(publisher_after_expire.consumable_points), 80)
        _assert_equal("publisher frozen after expire", int(publisher_after_expire.frozen_points), 0)
        _assert_equal("expire return ledger count", await _ledger_count("request_bounty_return", expire_id), 1)
        await client.aclose()

    print("OK netdisk request bounty P0 flow passed")


if __name__ == "__main__":
    asyncio.run(main())
