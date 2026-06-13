"""Verify KDocs parser supports xunlei and netdisk sync row mapping."""

from __future__ import annotations

import sys
import types
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

services_pkg = types.ModuleType("services")
services_pkg.__path__ = [str(PROJECT_ROOT / "services")]
sys.modules.setdefault("services", services_pkg)

from core.kdocs_service import _filter_latest_section_entries, _parse_section_date, parse_doc  # noqa: E402
from services.resource_classification_service import media_level_and_cost  # noqa: E402
from services.sync_service import _dedupe_source_links, _iter_netdisk_links, _netdisk_resource_id, _netdisk_source_key  # noqa: E402


def main() -> None:
    assert _parse_section_date("6月13日 更新", 2026).isoformat() == "2026-06-13"
    assert _parse_section_date("今日更新", 2026) is not None
    assert _parse_section_date("某电影 2026.06.13 修复版", 2026) is None

    doc = {
        "content": {
            "content": [
                {"type": "text", "text": "2026.06.12"},
                {"type": "text", "text": "旧资源 S01"},
                {"type": "text", "text": "夸克"},
                {"type": "text", "text": "https://pan.quark.cn/s/old"},
                {"type": "text", "text": "2026.06.13"},
                {"type": "text", "text": "测试影视剧 S01 4K"},
                {"type": "text", "text": "百度链接"},
                {"type": "text", "text": "链接:"},
                {"type": "text", "text": "https://pan.baidu.com/s/test"},
                {"type": "text", "text": "提取码：abcd"},
                {"type": "text", "text": "夸克"},
                {"type": "text", "text": "https://pan.quark.cn/s/test"},
                {"type": "text", "text": "迅雷资源"},
                {"type": "text", "text": "magnet:?xt=urn:btih:TEST"},
                {"type": "text", "text": "4K链接"},
                {"type": "text", "text": "https://www.aliyundrive.com/s/test"},
            ]
        }
    }
    parsed = parse_doc(doc, "06月13日 04:30")
    assert len(parsed) == 2, parsed
    latest = _filter_latest_section_entries(parsed, limit=20)
    assert len(latest) == 1, latest
    assert latest[0]["name"] == "测试影视剧 S01 4K", latest
    parsed = latest
    item = {
        "anime_id": "movie_test",
        "title": parsed[0]["name"],
        "category": "movie",
        "baidu_url": parsed[0]["baidu_link"],
        "baidu_password": parsed[0]["baidu_code"],
        "quark_url": parsed[0]["quark_link"],
        "xunlei_url": parsed[0]["xunlei_link"],
        "4k_url": parsed[0]["4k_link"],
    }
    links = _iter_netdisk_links(item)
    assert [pan for pan, _, _ in links] == ["百度", "夸克", "阿里", "迅雷"], links
    assert links[0][2] == "abcd", links
    assert _netdisk_resource_id(item, links[0][0], links[0][1]).startswith("kdocs-")
    assert _netdisk_source_key(item).startswith("kdocs:movie:")
    deduped = _dedupe_source_links([item, {**item, "anime_id": "movie_test_2"}])
    assert deduped[0]["xunlei_url"]
    assert deduped[1]["xunlei_url"] == ""
    assert media_level_and_cost("测试影视剧 完结合集")[1] == 20
    assert media_level_and_cost("测试影视剧 更新至08")[1] == 5
    print("OK kdocs netdisk sync mapping passed")


if __name__ == "__main__":
    main()
