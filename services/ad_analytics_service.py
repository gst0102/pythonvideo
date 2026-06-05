"""Ad analytics aggregation and export helpers."""

from __future__ import annotations

import html
import io
import zipfile
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import case, func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from models.ad_event import AdEventRecord
from models.user import User
from services.config_service import ConfigService

DEFAULT_REVENUE_CONFIG = {"default_ecpm": 30.0, "items": []}
DEFAULT_REWARD_CONFIG = {"points_per_reward": 5.0, "cash_per_reward": 0.05}


def now_keys(now: datetime | None = None) -> tuple[str, str, str]:
    current = now or datetime.utcnow()
    iso = current.isocalendar()
    return current.strftime("%Y-%m-%d"), f"{iso.year}-{iso.week:02d}", current.strftime("%Y-%m")


def scene_location(scene: str) -> tuple[str, str]:
    mapping = {
        "video_download": ("视频", "视频提取"),
        "game_jump": ("游戏", "休闲小游戏"),
        "anime_library": ("影视", "番剧库"),
        "movie": ("影视", "最新电影"),
        "k4": ("影视", "4K影视"),
    }
    return mapping.get(scene, ("其他", scene or "未知版块"))


async def get_revenue_config(session: AsyncSession) -> dict[str, Any]:
    config = await ConfigService.get(session, "ad_revenue_settings")
    if not config:
        return DEFAULT_REVENUE_CONFIG.copy()
    return {
        "default_ecpm": float(config.get("default_ecpm", DEFAULT_REVENUE_CONFIG["default_ecpm"])),
        "items": list(config.get("items") or []),
    }


async def get_reward_config(session: AsyncSession) -> dict[str, float]:
    config = await ConfigService.get(session, "ad_reward_settings")
    return {
        "points_per_reward": float(config.get("points_per_reward", DEFAULT_REWARD_CONFIG["points_per_reward"])),
        "cash_per_reward": float(config.get("cash_per_reward", DEFAULT_REWARD_CONFIG["cash_per_reward"])),
    }


def resolve_ecpm(config: dict[str, Any], module: str, section: str, ad_unit_id: str) -> float:
    for item in config.get("items", []):
        if (
            str(item.get("module", "")) == module
            and str(item.get("section", "")) == section
            and str(item.get("ad_unit_id", "")) == ad_unit_id
        ):
            return float(item.get("ecpm", config.get("default_ecpm", 30.0)) or 0)
    return float(config.get("default_ecpm", 30.0) or 0)


def enrich_metrics(row: dict[str, Any], revenue_config: dict[str, Any], reward_config: dict[str, float]) -> dict[str, Any]:
    completed = int(row.get("complete_count", 0) or 0)
    ecpm = resolve_ecpm(revenue_config, row.get("module", ""), row.get("section", ""), row.get("ad_unit_id", ""))
    estimated_revenue = completed / 1000 * ecpm
    actual_reward_points = float(row.get("actual_reward_points", 0) or 0)
    actual_reward_amount = float(row.get("actual_reward_amount", 0) or 0)
    reward_points = actual_reward_points if actual_reward_points > 0 else completed * reward_config["points_per_reward"]
    reward_amount = actual_reward_amount if actual_reward_amount > 0 else completed * reward_config["cash_per_reward"]
    return {
        **row,
        "ecpm": round(ecpm, 3),
        "estimated_revenue": round(estimated_revenue, 3),
        "reward_points": round(reward_points, 3),
        "reward_amount": round(reward_amount, 3),
        "net_revenue": round(estimated_revenue - reward_amount, 3),
    }


def date_range(period: str, start_date: str | None = None, end_date: str | None = None) -> tuple[datetime, datetime]:
    if start_date and end_date:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        return start, end

    today = date.today()
    if period == "week":
        start_day = today - timedelta(days=today.weekday())
    elif period == "month":
        start_day = today.replace(day=1)
    else:
        start_day = today
    return datetime.combine(start_day, datetime.min.time()), datetime.combine(today + timedelta(days=1), datetime.min.time())


def period_bounds() -> dict[str, tuple[datetime, datetime]]:
    return {
        "today": date_range("day"),
        "week": date_range("week"),
        "month": date_range("month"),
    }


def event_filters(
    query,
    start: datetime,
    end: datetime,
    module: str | None = None,
    section: str | None = None,
    ad_unit_id: str | None = None,
):
    query = query.where(AdEventRecord.created_at >= start, AdEventRecord.created_at < end)
    if module:
        query = query.where(AdEventRecord.module == module)
    if section:
        query = query.where(AdEventRecord.section == section)
    if ad_unit_id:
        query = query.where(AdEventRecord.ad_unit_id == ad_unit_id)
    return query


async def aggregate_rows(
    session: AsyncSession,
    start: datetime,
    end: datetime,
    group_fields: list[Any],
    module: str | None = None,
    section: str | None = None,
    ad_unit_id: str | None = None,
) -> list[dict[str, Any]]:
    query = select(
        *group_fields,
        func.count(case((AdEventRecord.event_type == "request", 1))).label("request_count"),
        func.count(case((AdEventRecord.event_type == "show", 1))).label("show_count"),
        func.count(case((AdEventRecord.event_type == "close", 1))).label("close_count"),
        func.count(case((AdEventRecord.event_type == "complete", 1))).label("complete_count"),
        func.count(case((AdEventRecord.event_type == "reward", 1))).label("reward_count"),
        func.coalesce(
            func.sum(case((AdEventRecord.event_type == "reward", AdEventRecord.reward_points), else_=0)),
            0,
        ).label("actual_reward_points"),
        func.coalesce(
            func.sum(case((AdEventRecord.event_type == "reward", AdEventRecord.reward_amount), else_=0)),
            0,
        ).label("actual_reward_amount"),
    )
    query = event_filters(query, start, end, module, section, ad_unit_id).group_by(*group_fields)
    rows = (await session.execute(query)).all()
    keys = [field.key for field in group_fields]
    return [
        {
            **{keys[i]: row[i] for i in range(len(keys))},
            "request_count": int(row[-7] or 0),
            "show_count": int(row[-6] or 0),
            "close_count": int(row[-5] or 0),
            "complete_count": int(row[-4] or 0),
            "reward_count": int(row[-3] or 0),
            "actual_reward_points": float(row[-2] or 0),
            "actual_reward_amount": float(row[-1] or 0),
        }
        for row in rows
    ]


async def user_rows(
    session: AsyncSession,
    start: datetime,
    end: datetime,
    revenue_config: dict[str, Any],
    reward_config: dict[str, float],
    keyword: str | None = None,
    module: str | None = None,
    section: str | None = None,
    ad_unit_id: str | None = None,
) -> list[dict[str, Any]]:
    completed = (
        select(
            AdEventRecord.user_id,
            User.nickname,
            User.openid,
            func.coalesce(
                func.sum(case((AdEventRecord.event_type == "complete", 1), else_=0)),
                0,
            ).label("complete_count"),
            func.string_agg(func.distinct(AdEventRecord.module), ", ").label("modules"),
            func.string_agg(func.distinct(AdEventRecord.section), ", ").label("sections"),
            func.string_agg(func.distinct(AdEventRecord.ad_unit_id), ", ").label("ad_unit_ids"),
            func.coalesce(
                func.sum(case((AdEventRecord.event_type == "reward", AdEventRecord.reward_points), else_=0)),
                0,
            ).label("reward_points"),
            func.coalesce(
                func.sum(case((AdEventRecord.event_type == "reward", AdEventRecord.reward_amount), else_=0)),
                0,
            ).label("reward_amount"),
        )
        .join(User, User.id == AdEventRecord.user_id)
        .where(AdEventRecord.event_type.in_(["complete", "reward"]))
    )
    completed = event_filters(completed, start, end, module, section, ad_unit_id)
    if keyword:
        kw = f"%{keyword.strip()}%"
        completed = completed.where((User.nickname.ilike(kw)) | (User.openid.ilike(kw)))
    completed = completed.group_by(AdEventRecord.user_id, User.nickname, User.openid)
    rows = (await session.execute(completed)).all()

    result: list[dict[str, Any]] = []
    for user_id, nickname, openid, complete_count, modules, sections, ad_unit_ids, actual_points, actual_amount in rows:
        detail_query = select(
            AdEventRecord.module,
            AdEventRecord.section,
            AdEventRecord.ad_unit_id,
            func.count().label("complete_count"),
        ).where(
            AdEventRecord.user_id == user_id,
            AdEventRecord.event_type == "complete",
        )
        detail_query = event_filters(detail_query, start, end, module, section, ad_unit_id)
        details = (await session.execute(detail_query.group_by(AdEventRecord.module, AdEventRecord.section, AdEventRecord.ad_unit_id))).all()
        estimated = 0.0
        for d_module, d_section, d_ad_unit_id, d_count in details:
            estimated += int(d_count or 0) / 1000 * resolve_ecpm(revenue_config, d_module or "", d_section or "", d_ad_unit_id or "")
        count = int(complete_count or 0)
        reward_points = float(actual_points or 0)
        reward_amount = float(actual_amount or 0)
        if reward_points <= 0 and count > 0:
            reward_points = count * reward_config["points_per_reward"]
        if reward_amount <= 0 and count > 0:
            reward_amount = count * reward_config["cash_per_reward"]
        result.append(
            {
                "user_id": str(user_id),
                "nickname": nickname or "",
                "openid": openid or "",
                "complete_count": count,
                "modules": modules or "",
                "sections": sections or "",
                "ad_unit_ids": ad_unit_ids or "",
                "estimated_revenue": round(estimated, 3),
                "reward_points": round(reward_points, 3),
                "reward_amount": round(reward_amount, 3),
                "net_revenue": round(estimated - reward_amount, 3),
            }
        )
    return sorted(result, key=lambda item: item["complete_count"], reverse=True)


def build_xlsx(sheets: list[tuple[str, list[str], list[list[Any]]]]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _content_types(len(sheets)))
        zf.writestr("_rels/.rels", _root_rels())
        zf.writestr("xl/workbook.xml", _workbook(sheets))
        zf.writestr("xl/_rels/workbook.xml.rels", _workbook_rels(len(sheets)))
        for idx, (_, headers, rows) in enumerate(sheets, start=1):
            zf.writestr(f"xl/worksheets/sheet{idx}.xml", _sheet_xml(headers, rows))
    return output.getvalue()


def _xml(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _cell(value: Any) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"<c><v>{value}</v></c>"
    return f'<c t="inlineStr"><is><t>{_xml(value)}</t></is></c>'


def _sheet_xml(headers: list[str], rows: list[list[Any]]) -> str:
    all_rows = [headers, *rows]
    row_xml = []
    for idx, row in enumerate(all_rows, start=1):
        row_xml.append(f'<row r="{idx}">{"".join(_cell(value) for value in row)}</row>')
    return f'<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>{"".join(row_xml)}</sheetData></worksheet>'


def _content_types(count: int) -> str:
    overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for i in range(1, count + 1)
    )
    return f'<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>{overrides}</Types>'


def _root_rels() -> str:
    return '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'


def _workbook(sheets: list[tuple[str, list[str], list[list[Any]]]]) -> str:
    sheet_xml = "".join(f'<sheet name="{_xml(name[:31])}" sheetId="{i}" r:id="rId{i}"/>' for i, (name, _, _) in enumerate(sheets, start=1))
    return f'<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>{sheet_xml}</sheets></workbook>'


def _workbook_rels(count: int) -> str:
    rels = "".join(
        f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
        for i in range(1, count + 1)
    )
    return f'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{rels}</Relationships>'
