"""Verify featured resources keep published time aligned with created_at."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from types import SimpleNamespace
from urllib.request import urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import services.netdisk_resource_service as netdisk_resource_service  # noqa: E402
from services.netdisk_resource_service import _dedupe_featured_resources  # noqa: E402
from services.netdisk_resource_service import _build_resource_payload  # noqa: E402
from services.resource_classification_service import normalize_resource_title  # noqa: E402


BUSINESS_TZ = timezone(timedelta(hours=8))


def resource(
    title: str,
    source_index: int,
    pan: str = "百度",
    created_at: datetime | None = None,
    verified_at: datetime | None = None,
):
    return SimpleNamespace(
        id=f"{source_index}-{pan}",
        title=title,
        pan=pan,
        source_ref=f"kdocs:anime:anime_{source_index}_fixture:{pan}:fixture",
        source_upload_id=f"kdocs:anime:fixture_{source_index}",
        normalized_title=normalize_resource_title(title),
        quality_score=0,
        downloads=0,
        favorites=0,
        category="影视剧",
        level="normal",
        cost_points=5,
        verified_at=verified_at or datetime(2026, 6, 15, 10, 30, tzinfo=timezone.utc),
        created_at=created_at or datetime(2026, 6, 13, 10, 30, tzinfo=timezone.utc),
        description="fixture",
        tags="[]",
        source_type="kdocs",
        is_active=True,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default="",
        help="Optional API base URL. When provided, verify live /netdisk resource responses too.",
    )
    parser.add_argument("--limit", type=int, default=20, help="Live response sample size.")
    return parser.parse_args()


def _created_at_bj_date(value: str) -> date | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        created = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if created.tzinfo:
        created = created.astimezone(BUSINESS_TZ)
    return created.date()


def _created_at_bj_datetime(value: str) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        created = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if created.tzinfo:
        created = created.astimezone(BUSINESS_TZ)
    return created.replace(tzinfo=None)


def _assert_payload_uses_created_at(payload: dict) -> None:
    assert payload.get("created_at"), payload
    assert payload.get("published_at_precise"), payload

    created_date = _created_at_bj_date(str(payload["created_at"]))
    assert created_date is not None, payload

    if payload.get("published_at") == "今天":
        assert created_date == datetime.now(BUSINESS_TZ).date(), payload


def _verify_live_endpoint(base_url: str, path: str, limit: int, require_unique_titles: bool = False) -> None:
    separator = "&" if "?" in path else "?"
    url = f"{base_url.rstrip('/')}{path}{separator}limit={limit}" if "limit=" not in path else f"{base_url.rstrip('/')}{path}"
    with urlopen(url, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    resources = data.get("data", {}).get("resources", [])
    assert resources, data
    for item in resources:
        _assert_payload_uses_created_at(item)
    _assert_latest_created_at_order(resources)
    if require_unique_titles:
        _assert_unique_titles(resources)


def _assert_latest_created_at_order(resources: list[dict]) -> None:
    created_values = [_created_at_bj_datetime(str(item.get("created_at", ""))) for item in resources]
    assert all(value is not None for value in created_values), resources
    assert created_values == sorted(created_values, reverse=True), resources


def _assert_unique_titles(resources: list[dict]) -> None:
    seen: set[str] = set()
    for item in resources:
        key = normalize_resource_title(str(item.get("title") or ""))
        assert key not in seen, resources
        seen.add(key)


def main() -> None:
    args = _parse_args()
    netdisk_resource_service.today_bj = lambda: date(2026, 6, 16)

    latest_created = datetime(2026, 6, 15, 16, 0, 36, tzinfo=timezone.utc)
    older_created = datetime(2026, 6, 13, 10, 30, tzinfo=timezone.utc)
    rows = [
        resource("哈哈哈哈哈 第六季.HD4K更 6.15期", 14, "夸克", latest_created),
        resource("喜欢你我也是 第六季.HD4K更 6.15期", 10, "夸克", latest_created - timedelta(seconds=1)),
        resource("无限超越班 第四季.HD4K更6.15期", 8, "夸克", latest_created - timedelta(seconds=2)),
        resource("无限超越班 第四季.HD4K更6.15期", 8, "百度", latest_created - timedelta(seconds=3)),
        resource("飞常日志 第二季.1080P更 01", 8, "百度", older_created),
        resource("飞常日志 第二季.1080P更 01", 8, "夸克", older_created - timedelta(seconds=1)),
        resource("医到孤岛爱上你.1080P更 05", 9, "百度", older_created - timedelta(seconds=2)),
        resource("讲给孩子的中华上下5000年故事", 99, "百度", latest_created - timedelta(seconds=4)),
    ]

    ordered = sorted(
        rows,
        key=lambda item: (
            item.created_at,
            int(getattr(item, "quality_score", 0) or 0),
            int(getattr(item, "downloads", 0) or 0),
            int(getattr(item, "favorites", 0) or 0),
            item.verified_at,
        ),
        reverse=True,
    )
    selected = _dedupe_featured_resources(ordered, 3)
    titles = [item.title for item in selected]

    assert titles == [
        "哈哈哈哈哈 第六季.HD4K更 6.15期",
        "喜欢你我也是 第六季.HD4K更 6.15期",
        "无限超越班 第四季.HD4K更6.15期",
    ], titles
    assert selected[0].pan == "夸克", selected[0]
    first_payload = _build_resource_payload(selected[0])
    assert first_payload["created_at"].startswith("2026-06-15"), first_payload
    assert first_payload["published_at"] == "今天", first_payload
    assert first_payload["published_at_precise"] == "6月16日 00:00", first_payload
    _assert_payload_uses_created_at(first_payload)
    assert all("讲给孩子" not in title for title in titles), titles
    if args.base_url:
        _verify_live_endpoint(
            args.base_url,
            "/netdisk/resources/featured-today?limit=20",
            args.limit,
            require_unique_titles=True,
        )
        _verify_live_endpoint(args.base_url, "/netdisk/resources?sort=latest&page=1&page_size=20", args.limit)
    print("OK featured resources use created_at for published time and include published_at_precise")


if __name__ == "__main__":
    main()
