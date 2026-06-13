"""Verify collected resource review pool actions with an isolated database."""

from __future__ import annotations

import asyncio
import os
import sys
import types
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("DEEPSEEK_CLASSIFIER_ENABLED", "false")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

services_pkg = types.ModuleType("services")
services_pkg.__path__ = [str(PROJECT_ROOT / "services")]
sys.modules.setdefault("services", services_pkg)

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from models.netdisk_collected_resource import NetdiskCollectedResource
from models.netdisk_resource import NetdiskResource
from services.netdisk_resource_service import NetdiskResourceService


def candidate(
    title: str,
    link: str,
    duplicate_status: str,
    confidence: int,
    pan: str = "夸克",
) -> NetdiskCollectedResource:
    return NetdiskCollectedResource(
        title=title,
        category="影视剧",
        pan=pan,
        link=link,
        extract_code="abcd",
        tags='["影视"]',
        normalized_title="测试采集剧",
        source_type="linuxdo",
        source_ref=f"linuxdo:test:{abs(hash(link))}",
        source_url="https://linux.do/t/test/1",
        confidence=confidence,
        duplicate_status=duplicate_status,
        ingest_action="review_required",
        status="pending",
    )


async def main() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(NetdiskResource.__table__.create)
        await conn.run_sync(NetdiskCollectedResource.__table__.create)

    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        existing = NetdiskResource(
            id="existing-same-link",
            title="测试采集剧 全集",
            category="影视剧",
            pan="夸克",
            level="official",
            cost_points=20,
            description="existing",
            link="https://pan.quark.cn/s/existing",
            extract_code="",
            tags='["影视", "完结", "夸克"]',
            source_type="kdocs",
            source_ref="kdocs:test:existing",
            normalized_title="测试采集剧",
            is_active=True,
        )
        low_confidence = candidate(
            "低置信测试资源 更新至08",
            "https://pan.quark.cn/s/low-confidence",
            "none",
            55,
        )
        same_link = candidate(
            "测试采集剧 全集 4K",
            "https://pan.quark.cn/s/existing",
            "same_link",
            88,
        )
        supplement_pan = candidate(
            "测试采集剧 全集 迅雷资源",
            "https://pan.xunlei.com/s/supplement",
            "supplement_pan",
            86,
            pan="迅雷",
        )
        session.add(existing)
        session.add(low_confidence)
        session.add(same_link)
        session.add(supplement_pan)
        await session.commit()

        low_result = await NetdiskResourceService.handle_admin_collected_resource(
            session,
            str(low_confidence.id),
            "approve",
            note="低置信人工通过",
        )
        same_result = await NetdiskResourceService.handle_admin_collected_resource(
            session,
            str(same_link.id),
            "merge",
            note="同链接合并",
        )
        supplement_result = await NetdiskResourceService.handle_admin_collected_resource(
            session,
            str(supplement_pan.id),
            "merge",
            note="新增网盘合并",
        )
        await session.commit()

        resources = (await session.exec(select(NetdiskResource))).all()
        by_link = {item.link: item for item in resources}

        assert low_result["candidate"]["status"] == "published", low_result
        assert by_link["https://pan.quark.cn/s/low-confidence"].cost_points == 5
        assert same_result["candidate"]["status"] == "merged", same_result
        assert len([item for item in resources if item.link == "https://pan.quark.cn/s/existing"]) == 1
        assert supplement_result["candidate"]["status"] == "merged", supplement_result
        assert by_link["https://pan.xunlei.com/s/supplement"].pan == "迅雷"
        assert by_link["https://pan.xunlei.com/s/supplement"].cost_points == 20
        assert len(resources) == 3, [item.link for item in resources]

        repeated = await NetdiskResourceService.handle_admin_collected_resource(
            session,
            str(supplement_pan.id),
            "merge",
            note="重复点击",
        )
        await session.commit()
        after_repeat = (await session.exec(select(NetdiskResource))).all()
        assert repeated["message"] == "该候选已处理", repeated
        assert len(after_repeat) == 3

    print("OK collected resource review pool integration passed")


if __name__ == "__main__":
    asyncio.run(main())
