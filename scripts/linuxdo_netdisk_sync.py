"""LinuxDo 云资产采集/入库命令。"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.linuxdo_resource_service import (  # noqa: E402
    LINUXDO_OUTPUT_DIR,
    LINUXDO_STATE_FILE,
    crawl_linuxdo_assets,
    ingest_linuxdo_rows,
    sync_linuxdo_resources,
    write_outputs,
)
from models.base import get_session_ctx  # noqa: E402


async def main() -> None:
    parser = argparse.ArgumentParser(description="LinuxDo 网盘资源采集与入库")
    parser.add_argument(
        "action",
        choices=["crawl", "sync", "backfill", "import-json"],
        help="crawl 只采集导出；sync 采集并入库；backfill 回补2026年至今；import-json 从本地采集文件入库",
    )
    parser.add_argument("--pages", type=int, default=1, help="采集页数，默认 1")
    parser.add_argument("--limit", type=int, default=20, help="最多采集帖子数，0 表示不限制；日常默认 20")
    parser.add_argument("--since-date", default="", help="只采集该日期之后的帖子，例如 2026-01-01")
    parser.add_argument("--until-date", default="", help="只采集该日期之前的帖子，例如 2026-06-13")
    parser.add_argument("--state-file", default=str(LINUXDO_STATE_FILE), help="LinuxDo 登录态文件")
    parser.add_argument("--input", default="", help="import-json 使用的 JSON 文件路径")
    parser.add_argument("--browser-fallback", action="store_true", help="帖子 JSON 没抓到链接时再打开页面兜底")
    args = parser.parse_args()

    if args.action == "backfill":
        args.since_date = args.since_date or "2026-01-01"
        args.until_date = args.until_date or date.today().isoformat()
        args.limit = 0 if args.limit == 20 else args.limit
        args.pages = max(args.pages, 80)

    state_file = Path(args.state_file)
    if args.action == "crawl":
        rows = await crawl_linuxdo_assets(
            args.pages,
            state_file,
            browser_fallback=args.browser_fallback,
            limit=args.limit,
            since_date=args.since_date or None,
            until_date=args.until_date or None,
        )
        csv_path = LINUXDO_OUTPUT_DIR / "linuxdo_netdisk_latest.csv"
        json_path = LINUXDO_OUTPUT_DIR / "linuxdo_netdisk_latest.json"
        write_outputs(rows, csv_path, json_path)
        print(json.dumps({"rows": len(rows), "csv": str(csv_path), "json": str(json_path)}, ensure_ascii=False))
        return

    if args.action == "import-json":
        input_path = Path(args.input)
        if not input_path.exists():
            raise FileNotFoundError(f"采集文件不存在: {input_path}")
        with input_path.open("r", encoding="utf-8") as file:
            rows = json.load(file)
        async with get_session_ctx() as session:
            result = await ingest_linuxdo_rows(session, rows)
            await session.commit()
        print(json.dumps({"input": str(input_path), **result}, ensure_ascii=False))
        return

    result = await sync_linuxdo_resources(
        pages=args.pages,
        browser_fallback=args.browser_fallback,
        limit=args.limit,
        since_date=args.since_date or None,
        until_date=args.until_date or None,
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
