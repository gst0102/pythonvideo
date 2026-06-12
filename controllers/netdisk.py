"""Netdisk resource routes."""

from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.response import response
from jwt_create import get_current_user
from models.base import get_session
from models.user import User
from schemas.netdisk import (
    NetdiskFavoriteListResponse,
    NetdiskFavoriteResponse,
    NetdiskRequestCreate,
    NetdiskRequestListResponse,
    NetdiskRequestResponse,
    NetdiskResourceAccessResponse,
    NetdiskResourceDetailResponse,
    NetdiskResourceListResponse,
    NetdiskResourceUnlockResponse,
    NetdiskUnfavoriteResponse,
    NetdiskUploadCreate,
    NetdiskUploadListResponse,
    NetdiskUploadResponse,
)
from services.netdisk_resource_service import NetdiskResourceService

router = APIRouter(prefix="/netdisk", tags=["netdisk"])


async def _get_user_by_openid(session: AsyncSession, openid: str) -> User | None:
    result = await session.execute(select(User).where(User.openid == openid))
    return result.scalar_one_or_none()


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
        )
    except ValueError as exc:
        return response([], 400, str(exc))

    return response(data=NetdiskUploadResponse(**result).model_dump(mode="json"), msg="upload created")


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
