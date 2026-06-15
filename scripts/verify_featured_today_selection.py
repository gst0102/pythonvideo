"""Verify homepage featured-resource ordering stays aligned with latest KDocs batch."""

from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import services.netdisk_resource_service as netdisk_resource_service  # noqa: E402
from services.netdisk_resource_service import _dedupe_featured_resources, _featured_kdocs_sort_key  # noqa: E402
from services.netdisk_resource_service import _build_resource_payload  # noqa: E402
from services.resource_classification_service import normalize_resource_title  # noqa: E402


def resource(title: str, source_index: int, pan: str = "百度"):
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
        verified_at=datetime(2026, 6, 15, 10, 30, tzinfo=timezone.utc),
        created_at=datetime(2026, 6, 13, 10, 30, tzinfo=timezone.utc),
        description="fixture",
        tags="[]",
        source_type="kdocs",
        is_active=True,
    )


def main() -> None:
    netdisk_resource_service.today_bj = lambda: date(2026, 6, 15)

    rows = [
        resource("飞常日志 第二季.1080P更 01", 8),
        resource("飞常日志 第二季.1080P更 01", 8, "夸克"),
        resource("医到孤岛爱上你.1080P更 05", 9),
        resource("菜鸟炊事兵.1080P更 11", 10),
        resource("天赐的声音 第7季.1080P更 6.15期", 12),
        resource("无限超越班 第四季.1080P更6.15期", 13),
        resource("讲给孩子的中华上下5000年故事", 99),
    ]

    ordered = sorted(rows, key=_featured_kdocs_sort_key)
    selected = _dedupe_featured_resources(ordered, 3)
    titles = [item.title for item in selected]

    assert titles == [
        "飞常日志 第二季.1080P更 01",
        "医到孤岛爱上你.1080P更 05",
        "菜鸟炊事兵.1080P更 11",
    ], titles
    assert selected[0].pan == "百度", selected[0]
    first_payload = _build_resource_payload(selected[0])
    assert first_payload["created_at"].startswith("2026-06-13"), first_payload
    assert first_payload["published_at"] == "今天", first_payload
    assert all("讲给孩子" not in title for title in titles), titles
    print("OK featured today selection prioritizes latest KDocs source order and dedupes pans")


if __name__ == "__main__":
    main()
