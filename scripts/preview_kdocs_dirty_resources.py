"""Preview KDocs duplicate/dirty resources without changing data."""

from __future__ import annotations

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


def _json_default(value: Any) -> str:
    return str(value)


async def _fetch_mappings(session, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    result = await session.execute(text(sql), params or {})
    return [dict(row) for row in result.mappings().all()]


async def _fetch_one(session, sql: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    result = await session.execute(text(sql), params or {})
    return dict(result.mappings().one())


async def build_preview(limit: int = 20) -> dict[str, Any]:
    async with get_session_ctx() as session:
        overview = await _fetch_one(
            session,
            f"""
            SELECT
                count(*) AS total_kdocs,
                count(*) FILTER (WHERE is_active) AS active_kdocs,
                count(*) FILTER (WHERE NOT is_active) AS hidden_kdocs,
                count(*) FILTER (WHERE is_active AND nullif(trim(link), '') IS NULL) AS active_empty_link,
                count(*) FILTER (WHERE is_active AND nullif(trim(source_ref), '') IS NULL) AS active_missing_source_ref,
                count(DISTINCT lower(trim(link))) FILTER (WHERE nullif(trim(link), '') IS NOT NULL) AS unique_link_count
            FROM netdisk_resources
            WHERE {KDOCS_WHERE}
            """,
        )
        issue_counts = {
            "same_link_active_duplicates": await _fetch_one(
                session,
                f"""
                SELECT
                    count(*) AS group_count,
                    coalesce(sum(active_count - 1), 0) AS preview_hide_rows
                FROM (
                    SELECT count(*) FILTER (WHERE is_active) AS active_count
                    FROM netdisk_resources
                    WHERE {KDOCS_WHERE}
                      AND nullif(trim(link), '') IS NOT NULL
                    GROUP BY lower(trim(link))
                    HAVING count(*) FILTER (WHERE is_active) > 1
                ) grouped
                """,
            ),
            "same_source_ref_duplicates": await _fetch_one(
                session,
                f"""
                SELECT
                    count(*) AS group_count,
                    coalesce(sum(row_count - 1), 0) AS duplicate_rows
                FROM (
                    SELECT count(*) AS row_count
                    FROM netdisk_resources
                    WHERE {KDOCS_WHERE}
                      AND nullif(trim(source_ref), '') IS NOT NULL
                    GROUP BY trim(source_ref)
                    HAVING count(*) > 1
                ) grouped
                """,
            ),
            "same_title_pan_active_duplicates": await _fetch_one(
                session,
                f"""
                SELECT
                    count(*) AS group_count,
                    coalesce(sum(active_count - 1), 0) AS manual_review_rows
                FROM (
                    SELECT count(*) AS active_count
                    FROM netdisk_resources
                    WHERE {KDOCS_WHERE}
                      AND is_active
                      AND nullif(trim(pan), '') IS NOT NULL
                      AND nullif(trim(coalesce(nullif(normalized_title, ''), title)), '') IS NOT NULL
                    GROUP BY lower(trim(coalesce(nullif(normalized_title, ''), title))), lower(trim(pan))
                    HAVING count(*) > 1
                ) grouped
                """,
            ),
        }

        same_link_groups = await _fetch_mappings(
            session,
            f"""
            WITH grouped AS (
                SELECT
                    lower(trim(link)) AS dirty_key,
                    count(*) AS row_count,
                    count(*) FILTER (WHERE is_active) AS active_count,
                    max(greatest(coalesce(verified_at, created_at), coalesce(updated_at, created_at), created_at)) AS newest_at
                FROM netdisk_resources
                WHERE {KDOCS_WHERE}
                  AND nullif(trim(link), '') IS NOT NULL
                GROUP BY lower(trim(link))
                HAVING count(*) FILTER (WHERE is_active) > 1
            )
            SELECT
                'same_link_active_duplicates' AS issue_type,
                g.dirty_key,
                g.row_count,
                g.active_count,
                g.newest_at,
                (
                    SELECT json_agg(row_to_json(sample_rows))
                    FROM (
                        SELECT
                            r.id,
                            r.title,
                            r.pan,
                            r.link,
                            r.is_active,
                            r.downloads,
                            r.favorites,
                            r.source_ref,
                            r.source_upload_id,
                            r.quality_score,
                            r.created_at,
                            r.verified_at,
                            r.updated_at,
                            CASE
                                WHEN row_number() OVER (
                                    ORDER BY r.is_active DESC,
                                             (nullif(trim(r.source_ref), '') IS NOT NULL) DESC,
                                             greatest(coalesce(r.verified_at, r.created_at), coalesce(r.updated_at, r.created_at), r.created_at) DESC,
                                             r.created_at DESC,
                                             r.quality_score DESC,
                                             r.id ASC
                                ) = 1 THEN 'keep_preview'
                                ELSE 'hide_preview'
                            END AS preview_action
                        FROM netdisk_resources r
                        WHERE {KDOCS_WHERE}
                          AND lower(trim(r.link)) = g.dirty_key
                        ORDER BY r.is_active DESC,
                                 (nullif(trim(r.source_ref), '') IS NOT NULL) DESC,
                                 greatest(coalesce(r.verified_at, r.created_at), coalesce(r.updated_at, r.created_at), r.created_at) DESC,
                                 r.created_at DESC,
                                 r.quality_score DESC,
                                 r.id ASC
                        LIMIT 8
                    ) sample_rows
                ) AS samples
            FROM grouped g
            ORDER BY g.active_count DESC, g.row_count DESC, g.newest_at DESC NULLS LAST
            LIMIT :limit
            """,
            {"limit": limit},
        )

        same_source_ref_groups = await _fetch_mappings(
            session,
            f"""
            WITH grouped AS (
                SELECT
                    trim(source_ref) AS dirty_key,
                    count(*) AS row_count,
                    count(*) FILTER (WHERE is_active) AS active_count,
                    max(greatest(coalesce(verified_at, created_at), coalesce(updated_at, created_at), created_at)) AS newest_at
                FROM netdisk_resources
                WHERE {KDOCS_WHERE}
                  AND nullif(trim(source_ref), '') IS NOT NULL
                GROUP BY trim(source_ref)
                HAVING count(*) > 1
            )
            SELECT
                'same_source_ref_duplicates' AS issue_type,
                g.dirty_key,
                g.row_count,
                g.active_count,
                g.newest_at,
                (
                    SELECT json_agg(row_to_json(sample_rows))
                    FROM (
                        SELECT
                            r.id,
                            r.title,
                            r.pan,
                            r.link,
                            r.is_active,
                            r.downloads,
                            r.favorites,
                            r.source_ref,
                            r.source_upload_id,
                            r.quality_score,
                            r.created_at,
                            r.verified_at,
                            r.updated_at,
                            CASE
                                WHEN row_number() OVER (
                                    ORDER BY r.is_active DESC,
                                             (nullif(trim(r.source_ref), '') IS NOT NULL) DESC,
                                             greatest(coalesce(r.verified_at, r.created_at), coalesce(r.updated_at, r.created_at), r.created_at) DESC,
                                             r.created_at DESC,
                                             r.quality_score DESC,
                                             r.id ASC
                                ) = 1 THEN 'keep_preview'
                                ELSE 'hide_preview'
                            END AS preview_action
                        FROM netdisk_resources r
                        WHERE {KDOCS_WHERE}
                          AND trim(r.source_ref) = g.dirty_key
                        ORDER BY r.is_active DESC,
                                 (nullif(trim(r.source_ref), '') IS NOT NULL) DESC,
                                 greatest(coalesce(r.verified_at, r.created_at), coalesce(r.updated_at, r.created_at), r.created_at) DESC,
                                 r.created_at DESC,
                                 r.quality_score DESC,
                                 r.id ASC
                        LIMIT 8
                    ) sample_rows
                ) AS samples
            FROM grouped g
            ORDER BY g.active_count DESC, g.row_count DESC, g.newest_at DESC NULLS LAST
            LIMIT :limit
            """,
            {"limit": limit},
        )

        same_title_pan_groups = await _fetch_mappings(
            session,
            f"""
            WITH grouped AS (
                SELECT
                    concat_ws(' | ', lower(trim(coalesce(nullif(normalized_title, ''), title))), lower(trim(pan))) AS dirty_key,
                    count(*) AS active_count,
                    max(greatest(coalesce(verified_at, created_at), coalesce(updated_at, created_at), created_at)) AS newest_at
                FROM netdisk_resources
                WHERE {KDOCS_WHERE}
                  AND is_active
                  AND nullif(trim(pan), '') IS NOT NULL
                  AND nullif(trim(coalesce(nullif(normalized_title, ''), title)), '') IS NOT NULL
                GROUP BY lower(trim(coalesce(nullif(normalized_title, ''), title))), lower(trim(pan))
                HAVING count(*) > 1
            )
            SELECT
                'same_title_pan_active_duplicates' AS issue_type,
                g.dirty_key,
                g.active_count AS row_count,
                g.active_count,
                g.newest_at,
                (
                    SELECT json_agg(row_to_json(sample_rows))
                    FROM (
                        SELECT
                            r.id,
                            r.title,
                            r.pan,
                            r.link,
                            r.is_active,
                            r.downloads,
                            r.favorites,
                            r.source_ref,
                            r.source_upload_id,
                            r.quality_score,
                            r.created_at,
                            r.verified_at,
                            r.updated_at,
                            CASE
                                WHEN row_number() OVER (
                                    ORDER BY (nullif(trim(r.source_ref), '') IS NOT NULL) DESC,
                                             greatest(coalesce(r.verified_at, r.created_at), coalesce(r.updated_at, r.created_at), r.created_at) DESC,
                                             r.created_at DESC,
                                             r.quality_score DESC,
                                             r.id ASC
                                ) = 1 THEN 'keep_preview'
                                ELSE 'manual_review_preview'
                            END AS preview_action
                        FROM netdisk_resources r
                        WHERE {KDOCS_WHERE}
                          AND r.is_active
                          AND concat_ws(' | ', lower(trim(coalesce(nullif(r.normalized_title, ''), r.title))), lower(trim(r.pan))) = g.dirty_key
                        ORDER BY (nullif(trim(r.source_ref), '') IS NOT NULL) DESC,
                                 greatest(coalesce(r.verified_at, r.created_at), coalesce(r.updated_at, r.created_at), r.created_at) DESC,
                                 r.created_at DESC,
                                 r.quality_score DESC,
                                 r.id ASC
                        LIMIT 8
                    ) sample_rows
                ) AS samples
            FROM grouped g
            ORDER BY g.active_count DESC, g.newest_at DESC NULLS LAST
            LIMIT :limit
            """,
            {"limit": limit},
        )

        empty_link_samples = await _fetch_mappings(
            session,
            f"""
            SELECT
                id,
                title,
                pan,
                link,
                is_active,
                source_ref,
                source_upload_id,
                quality_score,
                created_at,
                verified_at,
                updated_at,
                'hide_preview' AS preview_action
            FROM netdisk_resources
            WHERE {KDOCS_WHERE}
              AND is_active
              AND nullif(trim(link), '') IS NULL
            ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST
            LIMIT :limit
            """,
            {"limit": limit},
        )

        missing_source_ref_samples = await _fetch_mappings(
            session,
            f"""
            SELECT
                id,
                title,
                pan,
                link,
                is_active,
                source_ref,
                source_upload_id,
                quality_score,
                created_at,
                verified_at,
                updated_at,
                'manual_review_preview' AS preview_action
            FROM netdisk_resources
            WHERE {KDOCS_WHERE}
              AND is_active
              AND nullif(trim(source_ref), '') IS NULL
            ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST
            LIMIT :limit
            """,
            {"limit": limit},
        )

    return {
        "mode": "preview_only_no_delete_no_update",
        "cleanup_policy": {
            "same_link_active_duplicates": "建议保留有 source_ref 且验证/更新时间最新的一条，其余预览为 hide_preview。",
            "same_source_ref_duplicates": "同一个 KDocs 来源位重复入库，建议保留有来源且最新的一条，其余隐藏。",
            "same_title_pan_active_duplicates": "同名同盘但链接不同，先人工复核，不自动隐藏。",
            "active_empty_link": "活跃资源没有链接，建议隐藏。",
            "active_missing_source_ref": "活跃 KDocs 资源缺少来源引用，先人工复核。",
        },
        "overview": overview,
        "issue_counts": issue_counts,
        "groups": {
            "same_link_active_duplicates": same_link_groups,
            "same_source_ref_duplicates": same_source_ref_groups,
            "same_title_pan_active_duplicates": same_title_pan_groups,
        },
        "dirty_samples": {
            "active_empty_link": empty_link_samples,
            "active_missing_source_ref": missing_source_ref_samples,
        },
    }


async def main() -> None:
    preview = await build_preview()
    print(json.dumps(preview, ensure_ascii=False, indent=2, default=_json_default))


if __name__ == "__main__":
    asyncio.run(main())
