"""Ad event collection and admin analytics routes."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response as FastAPIResponse
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.response import response
from jwt_create import get_current_user
from models.ad_event import AdEventRecord
from models.base import get_session
from models.user import User
from schemas.user import AdEventCreateRequest, ConfigUpdateRequest
from services.ad_analytics_service import (
    aggregate_rows,
    build_xlsx,
    date_range,
    enrich_metrics,
    get_revenue_config,
    get_reward_config,
    now_keys,
    period_bounds,
    scene_location,
    user_rows,
)
from services.config_service import ConfigService

router = APIRouter(prefix="/ad", tags=["ad"])
admin_router = APIRouter(prefix="/admin/ad", tags=["admin-ad"])

VALID_EVENT_TYPES = {"request", "show", "close", "complete", "reward", "error"}


@router.post("/events", summary="record ad event")
async def record_ad_event(
    req: AdEventCreateRequest,
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    event_type = (req.event_type or "").strip()
    if event_type not in VALID_EVENT_TYPES:
        return response([], 400, "invalid ad event type")

    result = await session.execute(select(User).where(User.openid == openid))
    user = result.scalar_one_or_none()
    if not user:
        return response([], 404, "user not found")

    module = (req.module or "").strip()
    section = (req.section or "").strip()
    if not module or not section:
        module, section = scene_location(req.scene)

    date_key, week_key, month_key = now_keys()
    record = AdEventRecord(
        event_id=(req.event_id or "").strip()[:80],
        user_id=user.id,
        openid=openid,
        module=module,
        section=section,
        scene=(req.scene or "").strip(),
        ad_unit_id=(req.ad_unit_id or "").strip(),
        event_type=event_type,
        is_completed=bool(req.is_completed or event_type == "complete"),
        reward_points=float(req.reward_points or 0),
        reward_amount=float(req.reward_amount or 0),
        date_key=date_key,
        week_key=week_key,
        month_key=month_key,
    )
    session.add(record)
    await session.flush()
    return response(data={"id": str(record.id)}, msg="ad event recorded")


@router.get("/reward-config", summary="get public ad reward config")
async def get_public_ad_reward_config(session: AsyncSession = Depends(get_session)):
    return response(data=await get_reward_config(session))


@admin_router.get("/events/summary", summary="ad summary")
async def ad_summary(session: AsyncSession = Depends(get_session)):
    revenue_config = await get_revenue_config(session)
    reward_config = await get_reward_config(session)
    result = {}
    for key, (start, end) in period_bounds().items():
        rows = await aggregate_rows(
            session,
            start,
            end,
            [AdEventRecord.module, AdEventRecord.section, AdEventRecord.ad_unit_id],
        )
        enriched = [enrich_metrics(row, revenue_config, reward_config) for row in rows]
        result[key] = {
            "complete_count": sum(item["complete_count"] for item in enriched),
            "estimated_revenue": round(sum(item["estimated_revenue"] for item in enriched), 3),
            "reward_amount": round(sum(item["reward_amount"] for item in enriched), 3),
            "net_revenue": round(sum(item["net_revenue"] for item in enriched), 3),
        }
    return response(data=result)


@admin_router.get("/events/rankings", summary="ad rankings")
async def ad_rankings(
    period: str = Query("day"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    module: Optional[str] = Query(None),
    section: Optional[str] = Query(None),
    ad_unit_id: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    start, end = date_range(period, start_date, end_date)
    revenue_config = await get_revenue_config(session)
    reward_config = await get_reward_config(session)
    rows = await aggregate_rows(
        session,
        start,
        end,
        [AdEventRecord.module, AdEventRecord.section, AdEventRecord.ad_unit_id],
        module,
        section,
        ad_unit_id,
    )
    items = [enrich_metrics(row, revenue_config, reward_config) for row in rows]
    return response(data={"list": sorted(items, key=lambda item: item["estimated_revenue"], reverse=True)})


@admin_router.get("/events/by-user", summary="ad stats by user")
async def ad_by_user(
    period: str = Query("day"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    module: Optional[str] = Query(None),
    section: Optional[str] = Query(None),
    ad_unit_id: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    start, end = date_range(period, start_date, end_date)
    revenue_config = await get_revenue_config(session)
    reward_config = await get_reward_config(session)
    rows = await user_rows(session, start, end, revenue_config, reward_config, keyword, module, section, ad_unit_id)
    return response(data={"list": rows})


@admin_router.get("/revenue-configs", summary="get ad revenue configs")
async def get_ad_revenue_configs(session: AsyncSession = Depends(get_session)):
    return response(data=await get_revenue_config(session))


@admin_router.put("/revenue-configs", summary="update ad revenue configs")
async def update_ad_revenue_configs(req: ConfigUpdateRequest, session: AsyncSession = Depends(get_session)):
    config = await ConfigService.set(session, "ad_revenue_settings", req.config_data)
    return response(data=config.config_data, msg="ad revenue config updated")


@admin_router.get("/reward-config", summary="get ad reward config")
async def get_ad_reward_config(session: AsyncSession = Depends(get_session)):
    return response(data=await get_reward_config(session))


@admin_router.put("/reward-config", summary="update ad reward config")
async def update_ad_reward_config(req: ConfigUpdateRequest, session: AsyncSession = Depends(get_session)):
    config = await ConfigService.set(session, "ad_reward_settings", req.config_data)
    return response(data=config.config_data, msg="ad reward config updated")


@admin_router.get("/events/export.xlsx", summary="export ad analytics")
async def export_ad_events(
    period: str = Query("day"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    module: Optional[str] = Query(None),
    section: Optional[str] = Query(None),
    ad_unit_id: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    start, end = date_range(period, start_date, end_date)
    revenue_config = await get_revenue_config(session)
    reward_config = await get_reward_config(session)
    ranking_rows = [
        enrich_metrics(row, revenue_config, reward_config)
        for row in await aggregate_rows(
            session,
            start,
            end,
            [AdEventRecord.module, AdEventRecord.section, AdEventRecord.ad_unit_id],
            module,
            section,
            ad_unit_id,
        )
    ]
    users = await user_rows(session, start, end, revenue_config, reward_config, None, module, section, ad_unit_id)

    summary_rows = [
        ["完整观看次数", sum(item["complete_count"] for item in ranking_rows)],
        ["广告预估收益", round(sum(item["estimated_revenue"] for item in ranking_rows), 3)],
        ["用户奖励金额", round(sum(item["reward_amount"] for item in ranking_rows), 3)],
        ["净预估收益", round(sum(item["net_revenue"] for item in ranking_rows), 3)],
        ["导出时间", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")],
    ]
    ranking_export = [
        [
            item["module"],
            item["section"],
            item["ad_unit_id"],
            item["request_count"],
            item["show_count"],
            item["close_count"],
            item["complete_count"],
            item["reward_count"],
            item["ecpm"],
            item["estimated_revenue"],
            item["reward_amount"],
            item["net_revenue"],
        ]
        for item in ranking_rows
    ]
    user_export = [
        [
            item["user_id"],
            item["nickname"],
            item["openid"],
            item["complete_count"],
            item["modules"],
            item["sections"],
            item["ad_unit_ids"],
            item["estimated_revenue"],
            item["reward_points"],
            item["reward_amount"],
            item["net_revenue"],
        ]
        for item in users
    ]
    workbook = build_xlsx(
        [
            ("广告汇总", ["指标", "值"], summary_rows),
            (
                "功能区广告ID",
                ["功能区", "子栏目", "广告ID", "请求", "打开", "关闭", "完整观看", "奖励", "千次收益", "预估收益", "奖励金额", "净收益"],
                ranking_export,
            ),
            (
                "用户明细",
                ["用户ID", "昵称", "OpenID", "完整观看", "功能区", "子栏目", "广告ID", "预估收益", "奖励积分", "奖励金额", "净贡献"],
                user_export,
            ),
        ]
    )
    return FastAPIResponse(
        content=workbook,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="ad-events.xlsx"'},
    )
