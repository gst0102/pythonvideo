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
    is_active: bool = True
    quality_score: int = 0
    uploader_credit_level: str = "normal"
    uploader_credit_score: int = 100
    uploader_nickname: str = "官方整理"
    uploader_avatar: str = ""
    valid_days: int = 0
    report_count: int = 0
    invalid_count: int = 0


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


class NetdiskCreatorRewardSummary(BaseModel):
    created: bool = False
    ledger_id: str = ""
    points_delta: int = 0
    creator_consumable_points: int = 0


class NetdiskResourceUnlockResponse(BaseModel):
    resource: NetdiskResourceSummary
    unlock: NetdiskUnlockData
    account: CheckinAccountSummary
    invite_reward: NetdiskInviteRewardSummary | None = None
    creator_reward: NetdiskCreatorRewardSummary | None = None
    platform_recovered_points: int = 0


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
    bounty_status: str = "frozen"
    accepted_upload_id: str | None = None
    submissions_count: int
    deadline_text: str
    expires_at: datetime | None = None
    accepted_at: datetime | None = None
    closed_at: datetime | None = None
    created_at: datetime
    mine: bool = False
    can_submit: bool = True


class NetdiskRequestListResponse(BaseModel):
    requests: list[NetdiskRequestItem]


class NetdiskRequestResponse(BaseModel):
    request: NetdiskRequestItem


class NetdiskUploadCreate(BaseModel):
    request_id: str | None = None
    title: str
    category: str
    pan: str
    link: str
    extract_code: str = ""
    unzip_code: str = ""
    description: str


class NetdiskUploadItem(BaseModel):
    id: str
    request_id: str | None = None
    title: str
    category: str
    pan: str
    status: str
    accepted_at: datetime | None = None
    reward_points: int
    reward_released_points: int = 0
    valid_days_rewarded: int = 0
    audit_note: str
    created_at: datetime


class NetdiskUploadListResponse(BaseModel):
    uploads: list[NetdiskUploadItem]


class NetdiskUploadResponse(BaseModel):
    upload: NetdiskUploadItem


class NetdiskRequestSubmissionsResponse(BaseModel):
    submissions: list[NetdiskUploadItem]


class NetdiskRequestExpireResponse(BaseModel):
    expired_count: int
    returned_points: int


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


class NetdiskNotificationItem(BaseModel):
    id: str
    notice_type: str
    title: str
    content: str
    related_type: str
    related_id: str
    status: str
    created_at: datetime


class NetdiskNotificationListResponse(BaseModel):
    notifications: list[NetdiskNotificationItem]
    unread_count: int


class NetdiskAdminAuditRequest(BaseModel):
    note: str = ""
    result_action: str | None = None
    resource_level: str | None = None
    cost_points: int | None = None
