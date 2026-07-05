"""Netdisk resource routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, Header
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.response import response
from jwt_create import create_access_token, get_current_user
from models.base import get_session
from models.netdisk_user_notification import NetdiskUserNotification
from models.user import User
from schemas.netdisk import (
    NetdiskFavoriteListResponse,
    NetdiskFavoriteResponse,
    NetdiskFeedbackCreate,
    NetdiskFeedbackListResponse,
    NetdiskFeedbackResponse,
    NetdiskH5ConfigResponse,
    NetdiskH5RequestDetailResponse,
    NetdiskH5ResourceDetailResponse,
    NetdiskH5SessionResponse,
    NetdiskH5WechatCallbackCreate,
    NetdiskNotificationItem,
    NetdiskNotificationListResponse,
    NetdiskRepairCreate,
    NetdiskRepairListResponse,
    NetdiskRepairResponse,
    NetdiskRequestCreate,
    NetdiskRequestExpireResponse,
    NetdiskRequestListResponse,
    NetdiskRequestResponse,
    NetdiskRequestSubmissionsResponse,
    NetdiskResourceAccessResponse,
    NetdiskResourceDetailResponse,
    NetdiskResourceListResponse,
    NetdiskResourceSubscribeCreate,
    NetdiskResourceSubscriptionResponse,
    NetdiskResourceUnlockResponse,
    NetdiskUnlockHistoryHideResponse,
    NetdiskUnlockHistoryListResponse,
    NetdiskUnfavoriteResponse,
    NetdiskUploadCreate,
    NetdiskUploadListResponse,
    NetdiskUploadResponse,
)
from services.config_service import ConfigService
from services.netdisk_resource_service import NetdiskResourceService

router = APIRouter(prefix="/netdisk", tags=["netdisk"])


async def _get_user_by_openid(session: AsyncSession, openid: str) -> User | None:
    result = await session.execute(select(User).where(User.openid == openid))
    return result.scalar_one_or_none()


@router.get("/co-build/config", summary="get netdisk co-build config")
async def get_netdisk_co_build_config(session: AsyncSession = Depends(get_session)):
    config = await ConfigService.get(session, "co_build_config")
    return response(data=config)


def _normalize_category_names(categories: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for item in categories:
        value = str(item or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value[:32])
    return normalized


@router.get("/frontend-categories", summary="get netdisk frontend categories")
async def get_netdisk_frontend_categories(session: AsyncSession = Depends(get_session)):
    config = await ConfigService.get(session, "netdisk_frontend_categories_config")
    configured = _normalize_category_names(config.get("categories") or [])
    return response(data={"categories": configured})


@router.get("/h5/config", summary="get interactbao h5 config")
async def get_netdisk_h5_config(session: AsyncSession = Depends(get_session)):
    payload = await NetdiskResourceService.get_h5_config(session)
    return response(data=NetdiskH5ConfigResponse(**payload).model_dump(mode="json"))


@router.get("/h5/resources/{resource_id}", summary="get h5 safe resource detail")
async def get_netdisk_h5_resource_detail(
    resource_id: str,
    authorization: str | None = Header(None),
    session: AsyncSession = Depends(get_session),
):
    try:
        payload = await NetdiskResourceService.get_h5_resource_detail(
            session,
            resource_id,
            logged_in=bool(authorization),
        )
    except ValueError as exc:
        return response([], 404, str(exc))
    return response(data=NetdiskH5ResourceDetailResponse(**payload).model_dump(mode="json"))


@router.get("/h5/requests/{request_id}", summary="get h5 public request detail")
async def get_netdisk_h5_request_detail(
    request_id: str,
    authorization: str | None = Header(None),
    session: AsyncSession = Depends(get_session),
):
    try:
        payload = await NetdiskResourceService.get_h5_request_detail(
            session,
            request_id,
            logged_in=bool(authorization),
        )
    except ValueError as exc:
        return response([], 404, str(exc))
    return response(data=NetdiskH5RequestDetailResponse(**payload).model_dump(mode="json"))


@router.post("/h5/auth/wechat/callback", summary="h5 wechat oauth callback")
async def create_netdisk_h5_wechat_session(payload: NetdiskH5WechatCallbackCreate):
    clean_code = (payload.code or "").strip()
    if not clean_code:
        return response(
            data=NetdiskH5SessionResponse(
                logged_in=False,
                message="微信网页授权未配置或授权码为空，H5 已降级为只读详情。",
            ).model_dump(mode="json")
        )
    # First edition keeps the OAuth handoff explicit. Once official account
    # appid/secret are configured, replace this deterministic placeholder with
    # real sns/oauth2 access_token + userinfo exchange and unionid binding.
    token = create_access_token({"openid": f"h5:{clean_code[:32]}", "login_source": "h5_wechat"})
    return response(
        data=NetdiskH5SessionResponse(
            token=token,
            logged_in=True,
            nickname="互动宝用户",
            unionid_bound=False,
            message="H5 会话已创建；当前未完成公众号 unionid 绑定。",
        ).model_dump(mode="json")
    )


@router.get("/resources", summary="list netdisk resources")
async def list_netdisk_resources(
    keyword: str | None = None,
    pan: str | None = None,
    category: str | None = None,
    level: str | None = None,
    time: str | None = None,
    sort: str | None = None,
    page: int = 1,
    page_size: int = 20,
    session: AsyncSession = Depends(get_session),
):
    payload = await NetdiskResourceService.list_resources(
        session=session,
        keyword=keyword,
        pan=pan,
        category=category,
        level=level,
        time=time,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    return response(data=NetdiskResourceListResponse(**payload).model_dump(mode="json"))


@router.get("/resources/featured-today", summary="list today's featured netdisk resources")
async def list_today_featured_netdisk_resources(
    limit: int = 3,
    session: AsyncSession = Depends(get_session),
):
    payload = await NetdiskResourceService.list_today_featured_resources(session=session, limit=limit)
    return response(data=NetdiskResourceListResponse(**payload).model_dump(mode="json"))


@router.get("/requests", summary="list netdisk resource requests")
async def list_netdisk_requests(session: AsyncSession = Depends(get_session)):
    payload = await NetdiskResourceService.list_requests(session)
    return response(data=NetdiskRequestListResponse(**payload).model_dump(mode="json"))


@router.get("/requests/mine", summary="list current user's netdisk resource requests")
async def list_my_netdisk_requests(
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user = await _get_user_by_openid(session, openid)
    if not user:
        return response([], 404, "user not found")

    payload = await NetdiskResourceService.list_my_requests(session, user)
    return response(data=NetdiskRequestListResponse(**payload).model_dump(mode="json"))


@router.post("/requests", summary="create netdisk resource request")
async def create_netdisk_request(
    payload: NetdiskRequestCreate,
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user = await _get_user_by_openid(session, openid)
    if not user:
        return response([], 404, "user not found")

    try:
        result = await NetdiskResourceService.create_request(
            session=session,
            user=user,
            title=payload.title,
            pans=payload.pans,
            category=payload.category,
            bounty_points=payload.bounty_points,
            note=payload.note,
        )
    except ValueError as exc:
        return response([], 400, str(exc))

    return response(data=NetdiskRequestResponse(**result).model_dump(mode="json"), msg="request created")


@router.get("/requests/{request_id}/submissions", summary="list netdisk request submissions")
async def list_netdisk_request_submissions(
    request_id: str,
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user = await _get_user_by_openid(session, openid)
    if not user:
        return response([], 404, "user not found")

    try:
        result = await NetdiskResourceService.list_request_submissions(session, user, request_id)
    except ValueError as exc:
        return response([], 400, str(exc))

    return response(data=NetdiskRequestSubmissionsResponse(**result).model_dump(mode="json"))


@router.post("/requests/{request_id}/submissions", summary="submit resource to netdisk request")
async def submit_netdisk_request_resource(
    request_id: str,
    payload: NetdiskUploadCreate,
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user = await _get_user_by_openid(session, openid)
    if not user:
        return response([], 404, "user not found")

    try:
        result = await NetdiskResourceService.create_upload(
            session=session,
            user=user,
            title=payload.title,
            category=payload.category,
            pan=payload.pan,
            link=payload.link,
            extract_code=payload.extract_code,
            unzip_code=payload.unzip_code,
            description=payload.description,
            request_id=request_id,
        )
    except ValueError as exc:
        return response([], 400, str(exc))

    return response(data=NetdiskUploadResponse(**result).model_dump(mode="json"), msg="submission created")


@router.post("/requests/{request_id}/submissions/{upload_id}/accept", summary="accept netdisk request submission")
async def accept_netdisk_request_submission(
    request_id: str,
    upload_id: str,
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user = await _get_user_by_openid(session, openid)
    if not user:
        return response([], 404, "user not found")

    try:
        result = await NetdiskResourceService.accept_request_submission(session, user, request_id, upload_id)
    except ValueError as exc:
        return response([], 400, str(exc))

    return response(data=NetdiskRequestResponse(**result).model_dump(mode="json"), msg="submission accepted")


@router.post("/requests/{request_id}/cancel", summary="cancel netdisk request and return bounty")
async def cancel_netdisk_request(
    request_id: str,
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user = await _get_user_by_openid(session, openid)
    if not user:
        return response([], 404, "user not found")

    try:
        result = await NetdiskResourceService.cancel_request(session, user, request_id)
    except ValueError as exc:
        return response([], 400, str(exc))

    return response(data=NetdiskRequestResponse(**result).model_dump(mode="json"), msg="request canceled")


@router.post("/requests/expire", summary="expire netdisk requests and return bounty")
async def expire_netdisk_requests(session: AsyncSession = Depends(get_session)):
    result = await NetdiskResourceService.expire_requests(session)
    return response(data=NetdiskRequestExpireResponse(**result).model_dump(mode="json"))


@router.get("/uploads/mine", summary="list current user's netdisk uploads")
async def list_my_netdisk_uploads(
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user = await _get_user_by_openid(session, openid)
    if not user:
        return response([], 404, "user not found")

    payload = await NetdiskResourceService.list_my_uploads(session, user)
    return response(data=NetdiskUploadListResponse(**payload).model_dump(mode="json"))


@router.post("/uploads", summary="create netdisk upload submission")
async def create_netdisk_upload(
    payload: NetdiskUploadCreate,
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user = await _get_user_by_openid(session, openid)
    if not user:
        return response([], 404, "user not found")

    try:
        result = await NetdiskResourceService.create_upload(
            session=session,
            user=user,
            title=payload.title,
            category=payload.category,
            pan=payload.pan,
            link=payload.link,
            extract_code=payload.extract_code,
            unzip_code=payload.unzip_code,
            description=payload.description,
            request_id=payload.request_id,
        )
    except ValueError as exc:
        return response([], 400, str(exc))

    return response(data=NetdiskUploadResponse(**result).model_dump(mode="json"), msg="upload created")


@router.get("/repairs", summary="list netdisk repair/report submissions")
async def list_netdisk_repairs(session: AsyncSession = Depends(get_session)):
    payload = await NetdiskResourceService.list_repairs(session)
    return response(data=NetdiskRepairListResponse(**payload).model_dump(mode="json"))


@router.get("/repairs/mine", summary="list current user's netdisk repair/report submissions")
async def list_my_netdisk_repairs(
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user = await _get_user_by_openid(session, openid)
    if not user:
        return response([], 404, "user not found")

    payload = await NetdiskResourceService.list_my_repairs(session, user)
    return response(data=NetdiskRepairListResponse(**payload).model_dump(mode="json"))


@router.post("/repairs", summary="create netdisk repair/report submission")
async def create_netdisk_repair(
    payload: NetdiskRepairCreate,
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user = await _get_user_by_openid(session, openid)
    if not user:
        return response([], 404, "user not found")

    try:
        result = await NetdiskResourceService.create_repair(
            session=session,
            user=user,
            resource_id=payload.resource_id,
            mode=payload.mode,
            pan=payload.pan,
            link=payload.link,
            extract_code=payload.extract_code,
            unzip_code=payload.unzip_code,
            note=payload.note,
        )
    except ValueError as exc:
        return response([], 400, str(exc))

    return response(data=NetdiskRepairResponse(**result).model_dump(mode="json"), msg="repair created")


@router.get("/feedbacks/mine", summary="list current user's netdisk feedback tickets")
async def list_my_netdisk_feedbacks(
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user = await _get_user_by_openid(session, openid)
    if not user:
        return response([], 404, "user not found")

    payload = await NetdiskResourceService.list_my_feedbacks(session, user)
    return response(data=NetdiskFeedbackListResponse(**payload).model_dump(mode="json"))


@router.post("/feedbacks", summary="create netdisk feedback ticket")
async def create_netdisk_feedback(
    payload: NetdiskFeedbackCreate,
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user = await _get_user_by_openid(session, openid)
    if not user:
        return response([], 404, "user not found")

    try:
        result = await NetdiskResourceService.create_feedback(
            session=session,
            user=user,
            feedback_type=payload.feedback_type,
            content=payload.content,
            contact=payload.contact,
        )
    except ValueError as exc:
        return response([], 400, str(exc))

    return response(data=NetdiskFeedbackResponse(**result).model_dump(mode="json"), msg="feedback created")


@router.get("/resources/{resource_id}", summary="get netdisk resource detail")
async def get_netdisk_resource_detail(resource_id: str, session: AsyncSession = Depends(get_session)):
    try:
        payload = {"resource": await NetdiskResourceService.get_resource_detail(session, resource_id)}
    except ValueError as exc:
        return response([], 400, str(exc))

    return response(data=NetdiskResourceDetailResponse(**payload).model_dump(mode="json"))


@router.get("/resources/{resource_id}/access", summary="get netdisk resource access")
async def get_netdisk_resource_access(
    resource_id: str,
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user = await _get_user_by_openid(session, openid)
    if not user:
        return response([], 404, "user not found")

    try:
        payload = await NetdiskResourceService.get_resource_access(session, user, resource_id)
    except ValueError as exc:
        return response([], 400, str(exc))

    return response(data=NetdiskResourceAccessResponse(**payload).model_dump(mode="json"))


@router.get("/resources/{resource_id}/subscription", summary="get netdisk resource subscription")
async def get_netdisk_resource_subscription(
    resource_id: str,
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user = await _get_user_by_openid(session, openid)
    if not user:
        return response([], 404, "user not found")

    try:
        payload = await NetdiskResourceService.get_resource_subscription(session, user, resource_id)
    except ValueError as exc:
        return response([], 400, str(exc))

    return response(data=NetdiskResourceSubscriptionResponse(**payload).model_dump(mode="json"))


@router.post("/resources/{resource_id}/subscribe", summary="subscribe netdisk resource updates")
async def subscribe_netdisk_resource(
    resource_id: str,
    payload: NetdiskResourceSubscribeCreate,
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user = await _get_user_by_openid(session, openid)
    if not user:
        return response([], 404, "user not found")

    try:
        result = await NetdiskResourceService.subscribe_resource(
            session=session,
            user=user,
            resource_id=resource_id,
            wx_subscribe_status=payload.wx_subscribe_status,
            template_id=payload.template_id,
        )
    except ValueError as exc:
        return response([], 400, str(exc))

    return response(data=NetdiskResourceSubscriptionResponse(**result).model_dump(mode="json"), msg="resource subscribed")


@router.post("/resources/{resource_id}/unlock", summary="unlock netdisk resource")
async def unlock_netdisk_resource(
    resource_id: str,
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user = await _get_user_by_openid(session, openid)
    if not user:
        return response([], 404, "user not found")

    try:
        payload, unlocked_now = await NetdiskResourceService.unlock_resource(session, user, resource_id)
    except ValueError as exc:
        return response([], 400, str(exc))

    return response(
        data=NetdiskResourceUnlockResponse(**payload).model_dump(mode="json"),
        msg="resource unlocked" if unlocked_now else "resource already unlocked",
    )


@router.get("/favorites", summary="list current user's netdisk favorites")
async def list_netdisk_favorites(
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user = await _get_user_by_openid(session, openid)
    if not user:
        return response([], 404, "user not found")

    payload = await NetdiskResourceService.list_favorites(session, user)
    return response(data=NetdiskFavoriteListResponse(**payload).model_dump(mode="json"))


@router.get("/unlocks/mine", summary="list current user's netdisk unlock history")
async def list_my_netdisk_unlock_history(
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user = await _get_user_by_openid(session, openid)
    if not user:
        return response([], 404, "user not found")

    payload = await NetdiskResourceService.list_unlock_history(session, user)
    return response(data=NetdiskUnlockHistoryListResponse(**payload).model_dump(mode="json"))


@router.delete("/unlocks/{ledger_id}", summary="hide current user's netdisk unlock history")
async def hide_my_netdisk_unlock_history(
    ledger_id: str,
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user = await _get_user_by_openid(session, openid)
    if not user:
        return response([], 404, "user not found")

    try:
        payload = await NetdiskResourceService.hide_unlock_history(session, user, ledger_id)
    except ValueError as exc:
        return response([], 404, str(exc))

    return response(data=NetdiskUnlockHistoryHideResponse(**payload).model_dump(mode="json"), msg="unlock history hidden")


@router.get("/notifications", summary="list current user's netdisk notifications")
async def list_netdisk_notifications(
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user = await _get_user_by_openid(session, openid)
    if not user:
        return response([], 404, "user not found")

    rows = (
        await session.execute(
            select(NetdiskUserNotification)
            .where(NetdiskUserNotification.user_id == user.id)
            .order_by(NetdiskUserNotification.created_at.desc())
            .limit(100)
        )
    ).scalars().all()
    unread_count = (
        await session.execute(
            select(func.count())
            .select_from(NetdiskUserNotification)
            .where(
                NetdiskUserNotification.user_id == user.id,
                NetdiskUserNotification.status == "unread",
            )
        )
    ).scalar() or 0
    payload = {
        "notifications": [_build_notification_payload(item) for item in rows],
        "unread_count": int(unread_count),
    }
    return response(data=NetdiskNotificationListResponse(**payload).model_dump(mode="json"))


@router.post("/notifications/{notification_id}/read", summary="mark netdisk notification read")
async def mark_netdisk_notification_read(
    notification_id: str,
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _mark_netdisk_notification_read(notification_id, openid, session)


@router.get("/notifications/{notification_id}/read", summary="mark netdisk notification read fallback")
async def mark_netdisk_notification_read_fallback(
    notification_id: str,
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _mark_netdisk_notification_read(notification_id, openid, session)


async def _mark_netdisk_notification_read(notification_id: str, openid: str, session: AsyncSession):
    user = await _get_user_by_openid(session, openid)
    if not user:
        return response([], 404, "user not found")
    try:
        item_id = UUID(notification_id)
    except ValueError:
        return response([], 400, "invalid notification id")
    item = await session.get(NetdiskUserNotification, item_id)
    if not item or item.user_id != user.id:
        return response([], 404, "notification not found")
    item.status = "read"
    await session.flush()
    payload = NetdiskNotificationItem(**_build_notification_payload(item)).model_dump(mode="json")
    return response(data=payload, msg="notification marked read")


@router.post("/resources/{resource_id}/favorite", summary="favorite netdisk resource")
async def favorite_netdisk_resource(
    resource_id: str,
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user = await _get_user_by_openid(session, openid)
    if not user:
        return response([], 404, "user not found")

    try:
        payload, created = await NetdiskResourceService.favorite_resource(session, user, resource_id)
    except ValueError as exc:
        return response([], 400, str(exc))

    return response(
        data=NetdiskFavoriteResponse(**payload).model_dump(mode="json"),
        msg="resource favorited" if created else "resource already favorited",
    )


@router.delete("/resources/{resource_id}/favorite", summary="unfavorite netdisk resource")
async def unfavorite_netdisk_resource(
    resource_id: str,
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user = await _get_user_by_openid(session, openid)
    if not user:
        return response([], 404, "user not found")

    try:
        payload = await NetdiskResourceService.unfavorite_resource(session, user, resource_id)
    except ValueError as exc:
        return response([], 400, str(exc))

    return response(data=NetdiskUnfavoriteResponse(**payload).model_dump(mode="json"), msg="resource unfavorited")


def _build_notification_payload(item: NetdiskUserNotification) -> dict:
    return {
        "id": str(item.id),
        "notice_type": item.notice_type,
        "title": item.title,
        "content": item.content,
        "related_type": item.related_type,
        "related_id": item.related_id,
        "status": item.status,
        "created_at": item.created_at,
    }
