"""Schemas for netdisk resource unlock endpoints."""

from datetime import datetime

from pydantic import BaseModel

from schemas.checkin import CheckinAccountSummary


class NetdiskResourceSummary(BaseModel):
    id: str
    title: str
    category: str
    pan: str
    level: str
    cost_points: int
    verified_at: str
    downloads: int
    favorites: int
    description: str


class NetdiskResourceListResponse(BaseModel):
    resources: list[NetdiskResourceSummary]


class NetdiskResourceDetailResponse(BaseModel):
    resource: NetdiskResourceSummary


class NetdiskUnlockData(BaseModel):
    unlocked: bool = True
    ledger_id: str
    points_delta: int
    link: str
    extract_code: str = ""
    unzip_code: str = ""


class NetdiskAccessData(BaseModel):
    unlocked: bool = False
    ledger_id: str = ""
    points_delta: int = 0
    link: str = ""
    extract_code: str = ""
    unzip_code: str = ""


class NetdiskInviteRewardSummary(BaseModel):
    created: bool = False
    ledger_id: str
    points_delta: int
    inviter_consumable_points: int


class NetdiskResourceUnlockResponse(BaseModel):
    resource: NetdiskResourceSummary
    unlock: NetdiskUnlockData
    account: CheckinAccountSummary
    invite_reward: NetdiskInviteRewardSummary | None = None


class NetdiskResourceAccessResponse(BaseModel):
    resource: NetdiskResourceSummary
    access: NetdiskAccessData
    account: CheckinAccountSummary


class NetdiskFavoriteItem(BaseModel):
    resource: NetdiskResourceSummary
    favorite_at: datetime
    favorited: bool = True


class NetdiskFavoriteListResponse(BaseModel):
    favorites: list[NetdiskFavoriteItem]


class NetdiskFavoriteResponse(BaseModel):
    resource: NetdiskResourceSummary
    favorite_at: datetime
    favorited: bool = True


class NetdiskUnfavoriteResponse(BaseModel):
    resource: NetdiskResourceSummary
    favorited: bool = False
