"""Netdisk resource routes."""

from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.response import response
from jwt_create import get_current_user
from models.base import get_session
from models.user import User
from schemas.netdisk import NetdiskResourceAccessResponse, NetdiskResourceUnlockResponse
from services.netdisk_resource_service import NetdiskResourceService

router = APIRouter(prefix="/netdisk", tags=["netdisk"])


@router.get("/resources/{resource_id}/access", summary="get netdisk resource access")
async def get_netdisk_resource_access(
    resource_id: str,
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).where(User.openid == openid))
    user = result.scalar_one_or_none()
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
    result = await session.execute(select(User).where(User.openid == openid))
    user = result.scalar_one_or_none()
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
