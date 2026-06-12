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
    total: int
    page: int
    page_size: int
    has_more: bool


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


class NetdiskRequestCreate(BaseModel):
    title: str
    pans: list[str]
    category: str
    bounty_points: int
    note: str = ""


class NetdiskRequestItem(BaseModel):
    id: str
    title: str
    pans: str
    category: str
    bounty_points: int
    note: str = ""
    status: str
    submissions_count: int
    deadline_text: str
    created_at: datetime
    mine: bool = False


class NetdiskRequestListResponse(BaseModel):
    requests: list[NetdiskRequestItem]


class NetdiskRequestResponse(BaseModel):
    request: NetdiskRequestItem


class NetdiskUploadCreate(BaseModel):
    title: str
    category: str
    pan: str
    link: str
    extract_code: str = ""
    unzip_code: str = ""
    description: str


class NetdiskUploadItem(BaseModel):
    id: str
    title: str
    category: str
    pan: str
    status: str
    reward_points: int
    audit_note: str
    created_at: datetime


class NetdiskUploadListResponse(BaseModel):
    uploads: list[NetdiskUploadItem]


class NetdiskUploadResponse(BaseModel):
    upload: NetdiskUploadItem


class NetdiskRepairCreate(BaseModel):
    resource_id: str
    mode: str
    pan: str
    link: str = ""
    extract_code: str = ""
    unzip_code: str = ""
    note: str


class NetdiskRepairItem(BaseModel):
    id: str
    resource_id: str
    resource_title: str
    mode: str
    pan: str
    status: str
    reward_points: int
    audit_note: str
    note: str
    created_at: datetime
    mine: bool = False


class NetdiskRepairListResponse(BaseModel):
    repairs: list[NetdiskRepairItem]


class NetdiskRepairResponse(BaseModel):
    repair: NetdiskRepairItem


class NetdiskAdminAuditRequest(BaseModel):
    note: str = ""
