"""Hide active KDocs duplicate rows that share the exact same link.

Default mode is dry-run. Use --execute to update rows.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from models.base import get_session_ctx  # noqa: E402


KDOCS_WHERE = "(source_type = 'kdocs' OR source_upload_id LIKE 'kdocs:%')"

PROTECTED_WHERE = """
    downloads > 0
    OR favorites > 0
    OR report_count > 0
    OR invalid_count > 0
    OR EXISTS (
        SELECT 1 FROM netdisk_favorites f
        WHERE f.resource_id = ranked.id
    )
    OR EXISTS (
        SELECT 1 FROM points_ledger l
        WHERE l.related_type = 'netdisk_resource'
          AND l.related_id = ranked.id
    )
    OR EXISTS (
        SELECT 1 FROM netdisk_repairs r
        WHERE r.resource_id = ranked.id
    )
"""

RANKED_CTE = f"""
WITH ranked AS (
    SELECT
        r.id,
        r.title,
        r.pan,
        r.link,
        r.source_ref,
        r.source_upload_id,
        r.downloads,
        r.favorites,
        r.report_count,
        r.invalid_count,
        r.quality_score,
        r.created_at,
        r.verified_at,
        r.updated_at,
        lower(trim(r.link)) AS link_key,
        row_number() OVER (
            PARTITION BY lower(trim(r.link))
            ORDER BY
                (nullif(trim(r.source_ref), '') IS NOT NULL) DESC,
                greatest(coalesce(r.verified_at, r.created_at), coalesce(r.updated_at, r.created_at), r.created_at) DESC,
                r.created_at DESC,
                r.quality_score DESC,
                r.id ASC
        ) AS rn,
        count(*) OVER (PARTITION BY lower(trim(r.link))) AS active_duplicate_count
    FROM netdisk_resources r
    WHERE {KDOCS_WHERE}
      AND r.is_active
      AND nullif(trim(r.link), '') IS NOT NULL
)
"""


def _json_default(value: Any) -> str:
    return str(value)


async def _one(session, sql: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    result = await session.execute(text(sql), params or {})
    return dict(result.mappings().one())


async def _all(session, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    result = await session.execute(text(sql), params or {})
    return [dict(row) for row in result.mappings().all()]


async def build_cleanup_plan(limit: int) -> dict[str, Any]:
    async with get_session_ctx() as session:
        overview = await _one(
            session,
            f"""
            {RANKED_CTE}
            SELECT
                count(*) FILTER (WHERE active_duplicate_count > 1) AS duplicate_active_rows,
                count(*) FILTER (WHERE active_duplicate_count > 1 AND rn = 1) AS keep_rows,
                count(*) FILTER (WHERE active_duplicate_count > 1 AND rn > 1 AND NOT ({PROTECTED_WHERE})) AS hide_candidates,
                count(*) FILTER (WHERE active_duplicate_count > 1 AND rn > 1 AND ({PROTECTED_WHERE})) AS protected_review_rows,
                count(DISTINCT link_key) FILTER (WHERE active_duplicate_count > 1) AS duplicate_link_groups
            FROM ranked
            """,
        )

        samples = await _all(
            session,
            f"""
            {RANKED_CTE}
            SELECT
                id,
                title,
                pan,
                link,
                source_ref,
                source_upload_id,
                downloads,
                favorites,
                report_count,
                invalid_count,
                quality_score,
                created_at,
                verified_at,
                updated_at,
                rn,
                active_duplicate_count,
                CASE
                    WHEN rn = 1 THEN 'keep'
                    WHEN {PROTECTED_WHERE} THEN 'manual_review_protected'
                    ELSE 'hide_on_execute'
                END AS planned_action
            FROM ranked
            WHERE active_duplicate_count > 1
            ORDER BY link_key ASC, rn ASC
            LIMIT :limit
            """,
            {"limit": limit},
        )

    return {
        "mode": "dry_run_preview_only",
        "policy": "仅处理 KDocs 活跃资源中同链接重复项；保留有 source_ref 且最新的一条；有下载、收藏、投诉、积分流水、补链关联的重复项不自动隐藏。",
        "overview": overview,
        "samples": samples,
    }


async def execute_cleanup(limit: int) -> dict[str, Any]:
    async with get_session_ctx() as session:
        before = await build_cleanup_plan(limit)
        result = await session.execute(
            text(
                f"""
                {RANKED_CTE},
                candidates AS (
                    SELECT id
                    FROM ranked
                    WHERE active_duplicate_count > 1
                      AND rn > 1
                      AND NOT ({PROTECTED_WHERE})
                ),
                updated AS (
                    UPDATE netdisk_resources r
                    SET is_active = false, updated_at = now()
                    FROM candidates c
                    WHERE r.id = c.id
                    RETURNING r.id
                )
                SELECT count(*) AS hidden_count FROM updated
                """
            )
        )
        hidden_count = int(result.scalar_one() or 0)
        await session.commit()

    return {
        "mode": "execute_hide_duplicates",
        "hidden_count": hidden_count,
        "before": before["overview"],
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Preview or hide KDocs same-link duplicate active resources.")
    parser.add_argument("--execute", action="store_true", help="Actually hide safe duplicate rows.")
    parser.add_argument("--limit", type=int, default=80, help="Sample row limit for dry-run output.")
    args = parser.parse_args()

    if args.execute:
        payload = await execute_cleanup(args.limit)
    else:
        payload = await build_cleanup_plan(args.limit)
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default))


if __name__ == "__main__":
    asyncio.run(main())
