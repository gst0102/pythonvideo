"""Resource update subscription push helpers."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from uuid import UUID

import httpx
from sqlalchemy import and_
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.databaseApi import get_access_token
from models.netdisk_resource import NetdiskResource
from models.netdisk_resource_subscription import NetdiskResourceSubscription
from models.netdisk_resource_subscription_push_log import NetdiskResourceSubscriptionPushLog
from models.user import User

logger = logging.getLogger(__name__)


async def notify_resource_updated(
    session: AsyncSession,
    resource: NetdiskResource,
    *,
    old_title: str = "",
) -> dict[str, int]:
    """Send one-time WeChat subscription messages to users who accepted updates."""
    if not resource or not resource.id:
        return {"sent": 0, "skipped": 0, "failed": 0}
    if old_title and old_title.strip() == str(resource.title or "").strip():
        return {"sent": 0, "skipped": 0, "failed": 0}

    result = await session.execute(
        select(NetdiskResourceSubscription, User)
        .join(User, User.id == NetdiskResourceSubscription.user_id)
        .where(
            and_(
                NetdiskResourceSubscription.resource_id == resource.id,
                NetdiskResourceSubscription.is_active == True,  # noqa: E712
                NetdiskResourceSubscription.status == "active",
                NetdiskResourceSubscription.wx_subscribe_status == "accept",
            )
        )
    )
    rows = result.all()
    if not rows:
        return {"sent": 0, "skipped": 0, "failed": 0}

    token_result = await get_access_token(redis_client=None)
    access_token = token_result.get("token")
    if not access_token:
        for subscription, user in rows:
            _record_push_log(
                session,
                subscription=subscription,
                user=user,
                resource=resource,
                status="skipped",
                errmsg="微信 access_token 不可用",
            )
        await session.flush()
        return {"sent": 0, "skipped": len(rows), "failed": 0}

    now = datetime.utcnow()
    sent = 0
    skipped = 0
    failed = 0
    async with httpx.AsyncClient(timeout=10) as client:
        for subscription, user in rows:
            template_id = (subscription.template_id or os.getenv("WX_RESOURCE_UPDATE_TEMPLATE_ID", "")).strip()
            if not template_id or not user.openid:
                _record_push_log(
                    session,
                    subscription=subscription,
                    user=user,
                    resource=resource,
                    status="skipped",
                    template_id=template_id,
                    errmsg="缺少订阅模板 ID 或用户 openid",
                )
                skipped += 1
                continue
            payload = _build_subscribe_message_payload(user.openid, template_id, resource)
            try:
                response = await client.post(
                    f"https://api.weixin.qq.com/cgi-bin/message/subscribe/send?access_token={access_token}",
                    json=payload,
                )
                data = response.json()
            except Exception as exc:
                logger.warning("[netdisk subscription] send failed resource=%s user=%s error=%s", resource.id, user.id, exc)
                _record_push_log(
                    session,
                    subscription=subscription,
                    user=user,
                    resource=resource,
                    status="failed",
                    template_id=template_id,
                    errmsg=str(exc),
                )
                failed += 1
                continue
            if int(data.get("errcode") or 0) == 0:
                subscription.last_pushed_at = now
                subscription.wx_subscribe_status = "sent"
                subscription.updated_at = now
                _record_push_log(
                    session,
                    subscription=subscription,
                    user=user,
                    resource=resource,
                    status="sent",
                    template_id=template_id,
                    response_body=data,
                )
                sent += 1
            else:
                logger.warning("[netdisk subscription] send rejected resource=%s user=%s response=%s", resource.id, user.id, data)
                _record_push_log(
                    session,
                    subscription=subscription,
                    user=user,
                    resource=resource,
                    status="failed",
                    template_id=template_id,
                    errcode=int(data.get("errcode") or 0),
                    errmsg=str(data.get("errmsg") or "微信订阅消息发送失败"),
                    response_body=data,
                )
                failed += 1

    await session.flush()
    return {"sent": sent, "skipped": skipped, "failed": failed}


def _build_subscribe_message_payload(openid: str, template_id: str, resource: NetdiskResource) -> dict:
    title_field = os.getenv("WX_RESOURCE_UPDATE_TITLE_FIELD", "thing1")
    status_field = os.getenv("WX_RESOURCE_UPDATE_STATUS_FIELD", "thing2")
    time_field = os.getenv("WX_RESOURCE_UPDATE_TIME_FIELD", "time3")
    return {
        "touser": openid,
        "template_id": template_id,
        "page": f"pages/netdisk/detail?id={resource.id}",
        "miniprogram_state": os.getenv("WX_SUBSCRIBE_MINIPROGRAM_STATE", "formal"),
        "lang": "zh_CN",
        "data": {
            title_field: {"value": _wechat_thing_value(str(resource.title or "资源已更新"))},
            status_field: {"value": _wechat_thing_value("资源已更新")},
            time_field: {"value": _bj_time_text()},
        },
    }


def _wechat_thing_value(value: str) -> str:
    clean = " ".join(str(value or "").split())
    return clean[:20] or "资源更新"


def _bj_time_text() -> str:
    return (datetime.utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")


def _record_push_log(
    session: AsyncSession,
    *,
    subscription: NetdiskResourceSubscription,
    user: User,
    resource: NetdiskResource,
    status: str,
    template_id: str = "",
    errcode: int = 0,
    errmsg: str = "",
    response_body: dict | str | None = None,
) -> None:
    session.add(
        NetdiskResourceSubscriptionPushLog(
            subscription_id=_uuid_or_none(subscription.id),
            user_id=_uuid_or_none(user.id),
            resource_id=str(resource.id),
            template_id=(template_id or subscription.template_id or "")[:128],
            status=(status or "skipped")[:32],
            errcode=int(errcode or 0),
            errmsg=str(errmsg or "")[:300],
            response_body=_response_text(response_body),
            title_snapshot=str(resource.title or "")[:180],
        )
    )


def _uuid_or_none(value) -> UUID | None:
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _response_text(value: dict | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value[:2000]
    try:
        import json

        return json.dumps(value, ensure_ascii=False)[:2000]
    except Exception:
        return str(value)[:2000]
