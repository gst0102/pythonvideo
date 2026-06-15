"""Verify LinuxDo classification, media pricing, dedupe and idempotent ingest."""

from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

services_pkg = types.ModuleType("services")
services_pkg.__path__ = [str(PROJECT_ROOT / "services")]
sys.modules.setdefault("services", services_pkg)

from models.netdisk_collected_resource import NetdiskCollectedResource  # noqa: E402
from models.netdisk_resource import NetdiskResource  # noqa: E402
from services.linuxdo_resource_service import LinuxDoAssetRow, _collect_topics, _parse_boundary_date, ingest_linuxdo_rows  # noqa: E402
from services.resource_classification_service import media_level_and_cost  # noqa: E402


def row(topic_id: int, title: str, pan: str, link: str) -> LinuxDoAssetRow:
    return LinuxDoAssetRow(
        topic_id=topic_id,
        title=title,
        posted_at="2026-06-13T00:00:00Z",
        crawled_at="2026-06-13T01:00:00Z",
        crawl_status="ok",
        error="",
        topic_url=f"https://linux.do/t/topic/{topic_id}",
        netdisk=pan,
        link=link,
        code="abcd",
    )


async def main() -> None:
    class FakePage:
        async def evaluate(self, _script, url):
            page_num = 0 if "page=0" in url else 1
            topics = [
                {"id": 1, "title": "最新资源", "created_at": "2026-06-13T00:00:00Z", "slug": "new"},
                {"id": 2, "title": "一月资源", "created_at": "2026-01-03T00:00:00Z", "slug": "jan"},
            ] if page_num == 0 else [
                {"id": 3, "title": "旧资源", "created_at": "2025-12-31T00:00:00Z", "slug": "old"},
            ]
            return {"topic_list": {"topics": topics}}

    limited_topics = await _collect_topics(FakePage(), 2, limit=1)
    assert [item.topic_id for item in limited_topics] == [1], limited_topics
    ranged_topics = await _collect_topics(
        FakePage(),
        2,
        limit=0,
        since_dt=_parse_boundary_date("2026-01-01", is_end=False),
        until_dt=_parse_boundary_date("2026-06-13", is_end=True),
    )
    assert [item.topic_id for item in ranged_topics] == [1, 2], ranged_topics

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(NetdiskResource.__table__.create)
        await conn.run_sync(NetdiskCollectedResource.__table__.create)

    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        session.add(
            NetdiskResource(
                id="kdocs-movie-1",
                title="测试剧 全集 1080P",
                category="影视剧",
                pan="夸克",
                level="official",
                cost_points=20,
                link="https://pan.quark.cn/s/same",
                extract_code="",
                source_type="kdocs",
                source_ref="kdocs:test",
                normalized_title="测试剧",
                is_active=True,
            )
        )
        await session.commit()

        result = await ingest_linuxdo_rows(
            session,
            [
                row(1, "测试剧 全集 4K", "夸克", "https://pan.quark.cn/s/same"),
                row(2, "测试剧 全集 迅雷资源", "迅雷", "https://pan.xunlei.com/s/new-pan"),
                row(3, "更新至08集 示例剧", "夸克", "https://pan.quark.cn/s/updating"),
                row(4, "求资源：测试剧夸克链接", "夸克", "https://pan.quark.cn/s/request"),
            ],
        )
        await session.commit()

        assert result["skipped"] == 2, result
        assert result["auto_published"] == 2, result

        resources = (await session.exec(select(NetdiskResource))).all()
        by_link = {item.link: item for item in resources}
        assert by_link["https://pan.xunlei.com/s/new-pan"].cost_points == 20
        assert by_link["https://pan.xunlei.com/s/new-pan"].source_type == "linuxdo"
        assert by_link["https://pan.quark.cn/s/updating"].cost_points == 5
        dirty_candidate = (
            await session.exec(
                select(NetdiskCollectedResource).where(NetdiskCollectedResource.link == "https://pan.quark.cn/s/request")
            )
        ).one()
        assert dirty_candidate.status == "skipped"
        assert dirty_candidate.ingest_action == "skip_dirty"
        assert "求助" in dirty_candidate.error or "求资源" in dirty_candidate.error

        second = await ingest_linuxdo_rows(
            session,
            [
                row(2, "测试剧 全集 迅雷资源", "迅雷", "https://pan.xunlei.com/s/new-pan"),
                row(3, "更新至08集 示例剧", "夸克", "https://pan.quark.cn/s/updating"),
            ],
        )
        await session.commit()
        assert second["skipped"] == 2, second
        assert second["auto_published"] == 0, second
        count = len((await session.exec(select(NetdiskResource))).all())
        assert count == 3, count

    assert media_level_and_cost("某剧 完结合集")[1] == 20
    assert media_level_and_cost("某剧 更新至08")[1] == 5
    print("OK linuxdo hybrid classification passed")


if __name__ == "__main__":
    asyncio.run(main())
