"""单条资源分类调试工具。

生产入库优先使用规则库；只有低置信标题才会调用 DeepSeek。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.resource_classification_service import classify_resource  # noqa: E402


async def main() -> None:
    parser = argparse.ArgumentParser(description="DeepSeek/规则库资源分类调试")
    parser.add_argument("title", help="资源标题")
    parser.add_argument("--text", default="", help="正文或摘要")
    parser.add_argument("--pan", default="", help="网盘类型")
    args = parser.parse_args()

    result = await classify_resource(args.title, args.text, args.pan)
    print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
