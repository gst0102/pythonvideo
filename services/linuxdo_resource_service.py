"""LinuxDo cloud asset collection and netdisk ingestion service."""

from __future__ import annotations

import asyncio
import csv
import hashlib
import json
import logging
import os
import re
from contextlib import suppress
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable, Sequence
from urllib.parse import urljoin, urlparse

from sqlmodel import select

from core.browser_guard import browser_slot, chromium_launch_args
from models.base import get_session_ctx
from models.netdisk_collected_resource import NetdiskCollectedResource
from models.netdisk_resource import NetdiskResource as NetdiskResourceModel
from services.netdisk_resource_service import _calculate_resource_quality_score
from services.resource_classification_service import (
    classify_resource,
    media_level_and_cost,
    normalize_resource_title,
)

logger = logging.getLogger("linuxdo_sync")

LINUXDO_CATEGORY_URL = os.getenv("LINUXDO_CATEGORY_URL", "https://linux.do/c/resource/cloud-asset/94")
LINUXDO_SYNC_ENABLED = os.getenv("LINUXDO_SYNC_ENABLED", "true").lower() == "true"
LINUXDO_SYNC_PAGES = int(os.getenv("LINUXDO_SYNC_PAGES", "1"))
LINUXDO_SYNC_LIMIT = int(os.getenv("LINUXDO_SYNC_LIMIT", "20"))
LINUXDO_STATE_FILE = Path(os.getenv("LINUXDO_STATE_FILE", "storage/linuxdo_storage_state.json"))
LINUXDO_OUTPUT_DIR = Path(os.getenv("LINUXDO_OUTPUT_DIR", "output"))

NETDISK_HOSTS = {
    "pan.baidu.com": "百度",
    "yun.baidu.com": "百度",
    "aliyundrive.com": "阿里",
    "alipan.com": "阿里",
    "pan.quark.cn": "夸克",
    "quark.cn": "夸克",
    "pan.xunlei.com": "迅雷",
    "xunlei.com": "迅雷",
    "123pan.com": "123云盘",
    "123684.com": "123云盘",
    "cloud.189.cn": "天翼云盘",
    "weiyun.com": "腾讯微云",
}

CODE_PATTERNS = [
    re.compile(r"(?:提取码|访问码|取件码|密码|pwd|pass\s*code)\s*[:：]?\s*([A-Za-z0-9]{3,8})", re.I),
    re.compile(r"(?:邀请码|转存码|口令|兑换码)\s*[:：]?\s*([A-Za-z0-9_\-]{3,16})", re.I),
]
URL_RE = re.compile(r"https?://[^\s<>'\"，。；、)）\]]+", re.I)


@dataclass(frozen=True)
class LinuxDoTopic:
    topic_id: int
    title: str
    created_at: str
    slug: str


@dataclass(frozen=True)
class LinuxDoAssetRow:
    topic_id: int
    title: str
    posted_at: str
    crawled_at: str
    crawl_status: str
    error: str
    topic_url: str
    netdisk: str
    link: str
    code: str


class LinkTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self.text_parts: list[str] = []
        self._active_href: str | None = None
        self._active_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: Sequence[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "a":
            self._active_href = attrs_dict.get("href")
            self._active_text = []
        if tag in {"br", "p", "div", "li"}:
            self.text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._active_href:
            self.links.append((unescape(self._active_href), unescape("".join(self._active_text).strip())))
            self._active_href = None
            self._active_text = []
        if tag in {"p", "div", "li"}:
            self.text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.text_parts.append(data)
        if self._active_href is not None:
            self._active_text.append(data)

    @property
    def text(self) -> str:
        return unescape(" ".join("".join(self.text_parts).split()))


def normalize_url(url: str) -> str:
    value = unescape((url or "").strip())
    if value.startswith("//"):
        return "https:" + value
    return value


def netdisk_type(url: str, nearby_text: str = "") -> str:
    parsed = urlparse(url)
    haystack = f"{parsed.netloc.lower()} {nearby_text}".lower()
    for key, name in NETDISK_HOSTS.items():
        if key in haystack:
            return name
    return "其他网盘"


def looks_like_netdisk(url: str, nearby_text: str = "") -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = parsed.netloc.lower()
    if host.endswith("linux.do"):
        return False
    text = f"{host} {nearby_text}".lower()
    disk_words = ["网盘", "云盘", "夸克", "百度", "迅雷", "阿里", "drive", "pan."]
    return any(key in text for key in NETDISK_HOSTS) or any(word in text for word in disk_words)


def extract_code(text: str, link: str = "") -> str:
    source = f"{text}\n{link}"
    for pattern in CODE_PATTERNS:
        match = pattern.search(source)
        if match:
            return match.group(1)
    query = urlparse(link).query
    for key in ("pwd", "password", "passcode", "code", "p"):
        match = re.search(rf"(?:^|[?&]){key}=([^&]+)", query, re.I)
        if match:
            return match.group(1)
    return ""


def parse_cooked_html(cooked: str) -> tuple[str, list[tuple[str, str]]]:
    parser = LinkTextParser()
    parser.feed(cooked or "")
    found = list(parser.links)
    for url in URL_RE.findall(unescape(cooked or "")):
        found.append((normalize_url(url), ""))
    return parser.text, found


def topic_url(topic: LinuxDoTopic) -> str:
    return f"https://linux.do/t/{topic.slug or 'topic'}/{topic.topic_id}"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def make_asset_row(
    topic: LinuxDoTopic,
    crawled_at: str,
    crawl_status: str,
    error: str = "",
    netdisk: str = "",
    link: str = "",
    code: str = "",
) -> LinuxDoAssetRow:
    return LinuxDoAssetRow(topic.topic_id, topic.title, topic.created_at, crawled_at, crawl_status, error, topic_url(topic), netdisk, link, code)


async def sync_linuxdo_resources(
    pages: int | None = None,
    browser_fallback: bool = False,
    limit: int | None = None,
    since_date: str | date | None = None,
    until_date: str | date | None = None,
) -> dict:
    if not LINUXDO_SYNC_ENABLED:
        return {"synced": 0, "auto_published": 0, "review_required": 0, "skipped": 0, "error": "disabled"}
    if not LINUXDO_STATE_FILE.exists():
        return {"synced": 0, "auto_published": 0, "review_required": 0, "skipped": 0, "error": f"missing login state: {LINUXDO_STATE_FILE}"}
    rows = await crawl_linuxdo_assets(
        pages=pages or LINUXDO_SYNC_PAGES,
        state_file=LINUXDO_STATE_FILE,
        browser_fallback=browser_fallback,
        limit=LINUXDO_SYNC_LIMIT if limit is None else limit,
        since_date=since_date,
        until_date=until_date,
    )
    async with get_session_ctx() as session:
        result = await ingest_linuxdo_rows(session, rows)
        await session.commit()
        return result


async def crawl_linuxdo_assets(
    pages: int,
    state_file: Path,
    browser_fallback: bool = False,
    limit: int | None = None,
    since_date: str | date | None = None,
    until_date: str | date | None = None,
) -> list[LinuxDoAssetRow]:
    from playwright.async_api import async_playwright

    since_dt = _parse_boundary_date(since_date, is_end=False)
    until_dt = _parse_boundary_date(until_date, is_end=True)

    with browser_slot("linuxdo_resource_service.crawl_assets"):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=chromium_launch_args())
            context = None
            page = None
            try:
                context_options = {"storage_state": str(state_file)} if state_file.exists() else {}
                context = await browser.new_context(**context_options)
                page = await context.new_page()
                await page.goto(LINUXDO_CATEGORY_URL, wait_until="domcontentloaded")
                topics = await _collect_topics(page, pages, limit=limit, since_dt=since_dt, until_dt=until_dt)
                rows: list[LinuxDoAssetRow] = []
                for topic in topics:
                    crawled_at = utc_now()
                    try:
                        topic_rows = await _collect_from_topic_json(page, topic)
                        if browser_fallback and not topic_rows:
                            topic_rows = await _collect_from_browser_page(page, topic)
                        rows.extend(topic_rows or [make_asset_row(topic, crawled_at, "no_link")])
                    except Exception as exc:
                        rows.append(make_asset_row(topic, crawled_at, "error", str(exc)))
                return dedupe_rows(rows)
            finally:
                if page:
                    with suppress(Exception):
                        await page.close()
                if context:
                    with suppress(Exception):
                        await context.close()
                with suppress(Exception):
                    await browser.close()


def _parse_boundary_date(value: str | date | None, is_end: bool) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, date):
        return datetime.combine(value, time.max if is_end else time.min, tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    try:
        if len(text) == 10:
            parsed_date = date.fromisoformat(text)
            return datetime.combine(parsed_date, time.max if is_end else time.min, tzinfo=timezone.utc)
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        logger.warning("[linuxdo] invalid date boundary ignored: %s", value)
        return None


async def ingest_linuxdo_rows(session, rows: Iterable[LinuxDoAssetRow | dict]) -> dict:
    result = {"synced": 0, "auto_published": 0, "review_required": 0, "skipped": 0, "error": None}
    for raw in rows:
        row = raw if isinstance(raw, LinuxDoAssetRow) else LinuxDoAssetRow(**raw)
        if row.crawl_status != "ok" or not row.link:
            result["skipped"] += 1
            continue
        classification = await classify_resource(row.title, "", row.netdisk)
        normalized_title = normalize_resource_title(row.title)
        duplicate_status = await _duplicate_status(session, normalized_title, row.netdisk, row.link, classification.category)
        source_ref = _source_ref(row)
        if duplicate_status in {"same_link", "same_title_same_pan"}:
            await _upsert_candidate(session, row, classification, normalized_title, duplicate_status, "skip_duplicate", "skipped")
            result["skipped"] += 1
            continue
        if classification.confidence >= 75 and duplicate_status in {"none", "supplement_pan"}:
            await _publish_resource(session, row, classification, normalized_title, duplicate_status, source_ref)
            result["auto_published"] += 1
        else:
            await _upsert_candidate(session, row, classification, normalized_title, duplicate_status, "review_required", "pending")
            result["review_required"] += 1
        result["synced"] += 1
    await session.flush()
    return result


def _topic_created_datetime(topic: LinuxDoTopic) -> datetime | None:
    if not topic.created_at:
        return None
    try:
        parsed = datetime.fromisoformat(topic.created_at.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _topic_in_date_range(topic: LinuxDoTopic, since_dt: datetime | None, until_dt: datetime | None) -> bool:
    created_at = _topic_created_datetime(topic)
    if not created_at:
        return True
    if since_dt and created_at < since_dt:
        return False
    if until_dt and created_at > until_dt:
        return False
    return True


async def _collect_topics(
    page,
    pages: int,
    limit: int | None = None,
    since_dt: datetime | None = None,
    until_dt: datetime | None = None,
) -> list[LinuxDoTopic]:
    topics: list[LinuxDoTopic] = []
    seen: set[int] = set()
    max_topics = limit if limit and limit > 0 else None
    for page_num in range(max(1, pages)):
        data = await _fetch_json(page, f"/c/resource/cloud-asset/94.json?page={page_num}")
        page_topics = data.get("topic_list", {}).get("topics", [])
        if not page_topics:
            break
        hit_older_than_since = False
        for item in page_topics:
            topic_id = item.get("id")
            if not topic_id or topic_id in seen:
                continue
            topic = LinuxDoTopic(topic_id, item.get("title", ""), item.get("created_at", ""), item.get("slug", ""))
            created_at = _topic_created_datetime(topic)
            if since_dt and created_at and created_at < since_dt:
                hit_older_than_since = True
                continue
            if not _topic_in_date_range(topic, since_dt, until_dt):
                continue
            seen.add(topic_id)
            topics.append(topic)
            if max_topics and len(topics) >= max_topics:
                return topics
        if hit_older_than_since:
            break
    return topics


async def _fetch_json(page, path_or_url: str) -> dict:
    url = urljoin("https://linux.do", path_or_url)
    return await page.evaluate(
        """async (url) => {
            const response = await fetch(url, { credentials: 'include' });
            if (!response.ok) throw new Error(`${response.status} ${response.statusText} for ${url}`);
            return await response.json();
        }""",
        url,
    )


async def _collect_from_topic_json(page, topic: LinuxDoTopic) -> list[LinuxDoAssetRow]:
    crawled_at = utc_now()
    data = await _fetch_json(page, f"/t/{topic.topic_id}.json")
    combined_text: list[str] = []
    links: list[tuple[str, str]] = []
    for post in data.get("post_stream", {}).get("posts", []):
        text, post_links = parse_cooked_html(post.get("cooked", ""))
        combined_text.append(text)
        links.extend(post_links)
    all_text = "\n".join(combined_text)
    rows: list[LinuxDoAssetRow] = []
    seen_links: set[str] = set()
    for raw_link, label in links:
        link = normalize_url(raw_link)
        if link in seen_links or not looks_like_netdisk(link, label):
            continue
        seen_links.add(link)
        rows.append(make_asset_row(topic, crawled_at, "ok", netdisk=netdisk_type(link, label), link=link, code=extract_code(all_text, link)))
    return rows


async def _collect_from_browser_page(page, topic: LinuxDoTopic) -> list[LinuxDoAssetRow]:
    crawled_at = utc_now()
    await page.goto(topic_url(topic), wait_until="domcontentloaded")
    await page.wait_for_timeout(1000)
    data = await page.evaluate(
        """() => ({
            text: document.body ? document.body.innerText : '',
            links: Array.from(document.querySelectorAll('a[href]')).map(a => ({ href: a.href, label: a.innerText || a.textContent || '' }))
        })"""
    )
    text = data.get("text", "")
    found = [(item.get("href", ""), item.get("label", "")) for item in data.get("links", [])]
    for url in URL_RE.findall(text):
        found.append((url, ""))
    rows: list[LinuxDoAssetRow] = []
    seen_links: set[str] = set()
    for raw_link, label in found:
        link = normalize_url(raw_link)
        if link in seen_links or not looks_like_netdisk(link, label):
            continue
        seen_links.add(link)
        rows.append(make_asset_row(topic, crawled_at, "ok", netdisk=netdisk_type(link, label), link=link, code=extract_code(text, link)))
    return rows


def dedupe_rows(rows: Iterable[LinuxDoAssetRow]) -> list[LinuxDoAssetRow]:
    result: list[LinuxDoAssetRow] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = (row.topic_url, row.link)
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


async def _duplicate_status(session, normalized_title: str, pan: str, link: str, category: str) -> str:
    same_link = await session.execute(select(NetdiskResourceModel).where(NetdiskResourceModel.link == link).limit(1))
    if same_link.scalar_one_or_none():
        return "same_link"
    if category != "影视剧" or not normalized_title:
        return "none"
    result = await session.execute(
        select(NetdiskResourceModel).where(
            NetdiskResourceModel.category == "影视剧",
            NetdiskResourceModel.normalized_title == normalized_title,
            NetdiskResourceModel.is_active == True,  # noqa: E712
        )
    )
    matches = result.scalars().all()
    if not matches:
        legacy_result = await session.execute(
            select(NetdiskResourceModel).where(
                NetdiskResourceModel.category == "影视剧",
                NetdiskResourceModel.is_active == True,  # noqa: E712
            )
        )
        matches = [
            item for item in legacy_result.scalars().all()
            if normalize_resource_title(item.title) == normalized_title
        ]
    if not matches:
        return "none"
    if any(item.pan == pan for item in matches):
        return "same_title_same_pan"
    return "supplement_pan"


async def _publish_resource(session, row: LinuxDoAssetRow, classification, normalized_title: str, duplicate_status: str, source_ref: str) -> None:
    existing = await _get_resource_by_source_ref(session, source_ref)
    level, cost, media_tags = media_level_and_cost(row.title) if classification.category == "影视剧" else ("normal", 5, [])
    tags = sorted(set([*classification.tags, *media_tags, row.netdisk]))
    if existing:
        resource = existing
        resource.title = row.title[:120]
        resource.category = classification.category
        resource.pan = row.netdisk[:32]
        resource.link = row.link
        resource.extract_code = row.code or ""
        resource.tags = json.dumps(tags, ensure_ascii=False)
        resource.level = level
        resource.cost_points = cost
        resource.normalized_title = normalized_title
        resource.updated_at = datetime.utcnow()
        resource.is_active = True
    else:
        resource = NetdiskResourceModel(
            id=f"linuxdo-{hashlib.sha1(source_ref.encode('utf-8')).hexdigest()[:20]}",
            title=row.title[:120],
            category=classification.category,
            pan=row.netdisk[:32],
            level=level,
            cost_points=cost,
            downloads=0,
            favorites=0,
            description=f"系统从 LinuxDo 云资产采集的资源，来源帖子：{row.topic_url}",
            link=row.link,
            extract_code=row.code or "",
            unzip_code="",
            tags=json.dumps(tags, ensure_ascii=False),
            source_type="linuxdo",
            source_ref=source_ref,
            normalized_title=normalized_title,
            source_upload_id=f"linuxdo:{row.topic_id}",
            uploader_user_id=None,
            is_active=True,
            verified_at=datetime.utcnow(),
        )
        session.add(resource)
    resource.quality_score = _calculate_resource_quality_score(resource)
    await _upsert_candidate(session, row, classification, normalized_title, duplicate_status, "auto_publish", "published")


async def _get_resource_by_source_ref(session, source_ref: str) -> NetdiskResourceModel | None:
    result = await session.execute(select(NetdiskResourceModel).where(NetdiskResourceModel.source_ref == source_ref).limit(1))
    return result.scalar_one_or_none()


async def _upsert_candidate(session, row: LinuxDoAssetRow, classification, normalized_title: str, duplicate_status: str, ingest_action: str, status: str) -> None:
    source_ref = _source_ref(row)
    result = await session.execute(select(NetdiskCollectedResource).where(NetdiskCollectedResource.source_ref == source_ref).limit(1))
    item = result.scalar_one_or_none()
    tags = json.dumps(classification.tags, ensure_ascii=False)
    if item:
        item.title = row.title[:180]
        item.category = classification.category
        item.pan = row.netdisk[:32]
        item.link = row.link
        item.extract_code = row.code or ""
        item.tags = tags
        item.normalized_title = normalized_title
        item.source_url = row.topic_url
        item.confidence = classification.confidence
        item.duplicate_status = duplicate_status
        item.ingest_action = ingest_action
        item.status = status
        item.error = row.error or ""
        item.updated_at = datetime.utcnow()
        return
    session.add(
        NetdiskCollectedResource(
            title=row.title[:180],
            category=classification.category,
            pan=row.netdisk[:32],
            link=row.link,
            extract_code=row.code or "",
            tags=tags,
            normalized_title=normalized_title,
            source_type="linuxdo",
            source_ref=source_ref,
            source_url=row.topic_url,
            confidence=classification.confidence,
            duplicate_status=duplicate_status,
            ingest_action=ingest_action,
            status=status,
            error=row.error or "",
        )
    )


def _source_ref(row: LinuxDoAssetRow) -> str:
    digest = hashlib.sha1(f"{row.topic_id}:{row.link}".encode("utf-8")).hexdigest()[:24]
    return f"linuxdo:{row.topic_id}:{digest}"[:180]


def write_outputs(rows: Sequence[LinuxDoAssetRow], csv_path: Path, json_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(asdict(rows[0]).keys()) if rows else ["topic_id", "title", "posted_at", "crawled_at", "crawl_status", "error", "topic_url", "netdisk", "link", "code"])
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))
    with json_path.open("w", encoding="utf-8") as file:
        json.dump([asdict(row) for row in rows], file, ensure_ascii=False, indent=2)


def create_linuxdo_scheduler():
    if not LINUXDO_SYNC_ENABLED:
        logger.info("[linuxdo] sync disabled by LINUXDO_SYNC_ENABLED=false")
        return None
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    scheduler = AsyncIOScheduler(
        timezone=os.getenv("TZ", "Asia/Shanghai"),
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 120,
        },
    )
    scheduler.add_job(
        sync_linuxdo_resources,
        "interval",
        hours=int(os.getenv("LINUXDO_SYNC_INTERVAL_HOURS", "12")),
        kwargs={"limit": LINUXDO_SYNC_LIMIT},
        id="linuxdo_netdisk_12h_sync",
        name="LinuxDo云资产每12小时同步",
        replace_existing=True,
    )
    return scheduler
