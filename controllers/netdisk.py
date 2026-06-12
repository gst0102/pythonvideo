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
    NetdiskResourceAccessResponse,
    NetdiskResourceDetailResponse,
    NetdiskResourceListResponse,
    NetdiskResourceUnlockResponse,
    NetdiskUnfavoriteResponse,
)
from services.netdisk_resource_service import NetdiskResourceService

router = APIRouter(prefix="/netdisk", tags=["netdisk"])


async def _get_user_by_openid(session: AsyncSession, openid: str) -> User | None:
    result = await session.execute(select(User).where(User.openid == openid))
    return result.scalar_one_or_none()


@router.get("/resources", summary="list netdisk resources")
async def list_netdisk_resources(pan: str | None = None):
    payload = {"resources": NetdiskResourceService.list_resources(pan=pan)}
    return response(data=NetdiskResourceListResponse(**payload).model_dump(mode="json"))


@router.get("/resources/{resource_id}", summary="get netdisk resource detail")
async def get_netdisk_resource_detail(resource_id: str):
    try:
        payload = {"resource": NetdiskResourceService.get_resource_detail(resource_id)}
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
