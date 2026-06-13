"""
金山文档(kdocs) 逆向爬取服务
========================================

核心接口: POST /api/v3/office/file/{fileId}/open/otl
参数来源: 页面 window.__WPSENV__ (conn_id, user_group, file_version, csrf_token)

支持多文档配置，通过 KDOCS_SOURCES 环境变量或默认配置指定。
每个文档对应一个 category (anime / movie / 4k)。
"""

import json
import hashlib
import logging
import os
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterator
from urllib.parse import urlparse

import httpx
from playwright.sync_api import sync_playwright

from core.browser_guard import browser_slot, chromium_launch_args

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/148.0.0.0 Safari/537.36"
)

DATE_LINE_PATTERNS = [
    re.compile(r"(20\d{2})\s*[年./-]\s*(\d{1,2})\s*[月./-]\s*(\d{1,2})\s*(?:日|号)?"),
    re.compile(r"(\d{1,2})\s*月\s*(\d{1,2})\s*(?:日|号)?"),
    re.compile(r"(\d{1,2})[./-](\d{1,2})"),
]
DATE_HINT_WORDS = ("更新", "新增", "上新", "日期", "分割", "今日", "今天", "昨日", "昨天")

DEFAULT_SOURCES = [
    {
        "name": "番剧",
        "category": "anime",
        "share_url": "https://www.kdocs.cn/l/co72a28MWkmI",
        "file_id": "434428384518",
        "share_code": "co72a28MWkmI",
    },
    {
        "name": "电影",
        "category": "movie",
        "share_url": "https://www.kdocs.cn/l/cmbapmIwVsfi",
        "file_id": "",
        "share_code": "cmbapmIwVsfi",
    },
    {
        "name": "4K影视",
        "category": "4k",
        "share_url": "https://www.kdocs.cn/l/cdv0WUisFk3x",
        "file_id": "",
        "share_code": "cdv0WUisFk3x",
    },
]


def _load_sources() -> list[dict]:
    configured = os.getenv("KDOCS_SOURCES", "")
    if configured:
        try:
            sources = json.loads(configured)
            if isinstance(sources, list) and sources:
                return sources
        except json.JSONDecodeError:
            logger.warning("[KDocs] KDOCS_SOURCES JSON 解析失败，使用默认配置")
    return DEFAULT_SOURCES


KDOCS_SOURCES = _load_sources()


def extract_text_nodes(block, texts=None):
    if texts is None:
        texts = []
    if isinstance(block, dict):
        if block.get("type") == "text" and "text" in block:
            texts.append(block["text"])
        if "content" in block:
            for child in block["content"]:
                extract_text_nodes(child, texts)
    elif isinstance(block, list):
        for child in block:
            extract_text_nodes(child, texts)
    return texts


def _is_resource_link(text: str) -> bool:
    value = (text or "").strip().lower()
    return value.startswith(("http://", "https://", "magnet:", "thunder://", "ed2k://"))


def _extract_inline_link(text: str) -> str:
    match = re.search(r"(https?://\S+|magnet:\?\S+|thunder://\S+|ed2k://\S+)", text or "", re.I)
    return match.group(1).strip() if match else ""


def _read_following_link(all_texts: list[str], index: int) -> tuple[str, int]:
    i = index + 1
    while i < len(all_texts):
        line = all_texts[i].strip()
        inline = _extract_inline_link(line)
        if inline:
            return inline, i + 1
        if line in {"链接:", "链接：", "链接"} or "链接" in line:
            i += 1
            continue
        if _is_resource_link(line):
            return line, i + 1
        if not line or line.startswith(("提取码", "密码")):
            i += 1
            continue
        break
    return "", index + 1


def _parse_section_date(text: str, current_year: int, today: date | None = None) -> date | None:
    value = (text or "").strip()
    if not value:
        return None

    today = today or date.today()
    compact_value = re.sub(r"[\s\-—_｜|\[\]【】（）()：:]", "", value)
    if compact_value in {"今日", "今天", "今日更新", "今天更新", "今日新增", "今天新增", "今日上新", "今天上新"}:
        return today
    if compact_value in {"昨日", "昨天", "昨日更新", "昨天更新", "昨日新增", "昨天新增", "昨日上新", "昨天上新"}:
        return today - timedelta(days=1)

    for index, pattern in enumerate(DATE_LINE_PATTERNS):
        match = pattern.search(value)
        if not match:
            continue
        date_text = match.group(0).strip()
        is_plain_date_line = value.strip(" -—_｜|[]【】（）()：:").strip() == date_text
        has_date_hint = any(word in value for word in DATE_HINT_WORDS)
        if not is_plain_date_line and not has_date_hint:
            continue
        try:
            if index == 0:
                return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            return date(current_year, int(match.group(1)), int(match.group(2)))
        except ValueError:
            return None
    return None


def _filter_latest_section_entries(entries: list[dict], limit: int | None = None) -> list[dict]:
    if not entries:
        return []

    dated_entries = [entry for entry in entries if entry.get("source_date")]
    if not dated_entries:
        return entries[:limit] if limit and limit > 0 else entries

    latest_date = max(entry["source_date"] for entry in dated_entries)
    latest_entries = [entry for entry in dated_entries if entry.get("source_date") == latest_date]
    return latest_entries[:limit] if limit and limit > 0 else latest_entries


def parse_doc(doc_data: dict, crawl_time: str) -> list[dict]:
    content = doc_data.get("content", {}).get("content", [])
    if not content:
        return []

    entries = []
    all_texts = extract_text_nodes(content)
    current_year = datetime.now().year
    current_section_date: date | None = None

    SKIP_PREFIXES = [
        "http", "百度", "夸克", "提取码", "4K", "注意", "搜索", "解决",
        "①", "②", "③", "④", "⑤", "热门剧", "链接", "迅雷", "磁力",
    ]
    SKIP_KEYWORDS = ["登录", "查找和替换", "关键字", "搜不到"]

    i = 0
    while i < len(all_texts):
        text = all_texts[i].strip()

        if not text:
            i += 1
            continue

        section_date = _parse_section_date(text, current_year)
        if section_date:
            current_section_date = section_date
            i += 1
            continue

        if "日期分割线" in text or "置顶分割线" in text:
            i += 1
            continue

        if text.startswith("【") or text.startswith("-"):
            i += 1
            continue

        is_skip = any(text.startswith(p) for p in SKIP_PREFIXES)
        if is_skip:
            i += 1
            continue

        has_skip_kw = any(kw in text for kw in SKIP_KEYWORDS)
        if has_skip_kw:
            i += 1
            continue

        if len(text) < 4:
            i += 1
            continue

        name = text
        i += 1

        while i < len(all_texts):
            next_text = all_texts[i].strip()
            if (next_text.startswith(".") or
                next_text.startswith("更") or
                next_text.startswith("第")):
                name += next_text
                i += 1
            else:
                break

        baidu_link = ""
        baidu_code = ""
        quark_link = ""
        k4_link = ""
        xunlei_link = ""

        while i < len(all_texts):
            line = all_texts[i].strip()

            if "百度链接" in line or line == "百度":
                inline = _extract_inline_link(line)
                if inline:
                    baidu_link = inline
                    i += 1
                else:
                    baidu_link, i = _read_following_link(all_texts, i)
            elif "提取码" in line:
                m = re.search(r"提取码[：:]\s*(\S+)", line)
                if m:
                    baidu_code = m.group(1)
                else:
                    i += 1
                    if i < len(all_texts):
                        baidu_code = all_texts[i].strip().strip("：:")
                i += 1
            elif "夸克" in line:
                inline = _extract_inline_link(line)
                if inline:
                    quark_link = inline
                    i += 1
                else:
                    quark_link, i = _read_following_link(all_texts, i)
            elif "4K链接" in line:
                inline = _extract_inline_link(line)
                if inline:
                    k4_link = inline
                    i += 1
                else:
                    k4_link, i = _read_following_link(all_texts, i)
            elif "迅雷" in line or "磁力" in line:
                inline = _extract_inline_link(line)
                if inline:
                    xunlei_link = inline
                    i += 1
                else:
                    xunlei_link, i = _read_following_link(all_texts, i)
            else:
                if (not line or
                    _is_resource_link(line) or
                    line.startswith("百度") or
                    line.startswith("夸克") or
                    line.startswith("提取码") or
                    line.startswith("4K") or
                    line.startswith("链接") or
                    line.startswith("迅雷") or
                    line.startswith("磁力") or
                    line.startswith("【")):
                    i += 1
                    continue

                if (len(line) > 3 and
                    not line.startswith("-") and
                    not any(line.startswith(p) for p in SKIP_PREFIXES) and
                    "日期分割线" not in line and
                    "置顶分割线" not in line):
                    break
                i += 1

        entries.append({
            "name": name.strip(),
            "baidu_link": baidu_link,
            "baidu_code": baidu_code,
            "quark_link": quark_link,
            "4k_link": k4_link,
            "xunlei_link": xunlei_link,
            "update_time": crawl_time,
            "source_date": current_section_date.isoformat() if current_section_date else "",
        })

    return entries


class KDocsService:
    @staticmethod
    def fetch_params_via_playwright(share_url: str) -> dict | None:
        logger.info("[KDocs] Playwright 获取参数: %s", share_url)
        with browser_slot("kdocs_service.fetch_params"), sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=chromium_launch_args("--disable-blink-features=AutomationControlled"),
            )
            context = browser.new_context(user_agent=UA, viewport={"width": 1280, "height": 720})
            page = context.new_page()

            captured_params = {}

            def on_response(resp):
                rurl = resp.url
                if "/api/v3/office/session/" in rurl and "/otl" in rurl and resp.status == 200:
                    try:
                        body = resp.json()
                        data = body.get("data", {})
                        if data.get("connid"):
                            captured_params["conn_id"] = data["connid"]
                        if data.get("group"):
                            captured_params["user_group"] = data["group"]
                        if data.get("file_version") or data.get("frontVer"):
                            captured_params["file_version"] = data.get("file_version") or data.get("frontVer")
                        sid = data.get("sessionId", "")
                        if sid and not captured_params.get("file_id"):
                            m = re.search(r"edit/(\d+)", sid)
                            if m:
                                captured_params["file_id"] = m.group(1)
                    except Exception:
                        pass

                if "/api/v3/office/collaboration/" in rurl and resp.status == 200:
                    try:
                        body = resp.json()
                        data = body.get("data", {})
                        if data.get("csrf_token"):
                            captured_params["csrf_token"] = data["csrf_token"]
                        if data.get("file_version"):
                            captured_params["file_version"] = data["file_version"]
                    except Exception:
                        pass

            page.on("response", on_response)

            try:
                page.goto(share_url, wait_until="domcontentloaded", timeout=60000)
                for _ in range(15):
                    page.wait_for_timeout(1000)
                    if captured_params.get("conn_id") and captured_params.get("csrf_token"):
                        break

                if not captured_params.get("conn_id"):
                    env_data = page.evaluate("""
                        () => {
                            const env = window.__WPSENV__ || {};
                            return {
                                conn_id: env.conn_id || env.connid || '',
                                user_group: env.user_group || env.group || '',
                                file_version: env.file_version || env.front_ver || 0,
                                csrf_token: env.csrf_token || env.csrf_rand || '',
                            };
                        }
                    """)
                    if env_data.get("conn_id"):
                        captured_params.update(env_data)

                if not captured_params.get("conn_id"):
                    logger.error("[KDocs] 未能获取 conn_id")
                    return None

                if not captured_params.get("file_id"):
                    fid = page.evaluate("""() => {
                        try {
                            const app = window.app || window.App || {};
                            const sid = app.sessionId || '';
                            const m = sid.match(/edit\\/(\\d+)/);
                            return m ? m[1] : '';
                        } catch(e) { return ''; }
                    }""")
                    if fid:
                        captured_params["file_id"] = fid

                logger.info("[KDocs] 获取参数成功: conn_id=%s", captured_params.get("conn_id", "")[:12])
                return captured_params

            finally:
                browser.close()

    @staticmethod
    def fetch_doc_via_api(share_code: str, file_id: str, share_url: str,
                          conn_id: str, user_group: str, file_version, csrf_token: str) -> dict | None:
        logger.info("[KDocs] API 请求文档: share_code=%s", share_code)

        with httpx.Client(timeout=30, verify=False) as client:
            client.post(
                f"https://www.kdocs.cn/api/v3/office/session/{share_code}/otl?first",
                headers={
                    "content-type": "text/plain;charset=UTF-8",
                    "x-csrf-rand": csrf_token,
                    "origin": "https://www.kdocs.cn",
                    "referer": share_url,
                    "user-agent": UA,
                },
                json={
                    "token": "",
                    "group": user_group,
                    "connid": conn_id,
                    "fileid": file_id,
                    "front_ver": file_version,
                    "endpoint_id": "",
                    "args": {"auto_slim": True},
                },
            )

            resp = client.post(
                f"https://www.kdocs.cn/api/v3/office/file/{share_code}/open/otl",
                headers={
                    "content-type": "text/plain;charset=UTF-8",
                    "x-csrf-rand": csrf_token,
                    "origin": "https://www.kdocs.cn",
                    "referer": share_url,
                    "user-agent": UA,
                },
                json={
                    "connid": conn_id,
                    "args": {
                        "password": "",
                        "readonly": False,
                        "modifyPassword": "",
                        "sync": True,
                        "startVersion": 0,
                        "endVersion": 0,
                        "autoSlim": True,
                    },
                    "ex_args": {
                        "queryInitArgs": {
                            "enableCopyComments": False,
                            "checkAuditRule": False,
                        }
                    },
                    "group": user_group,
                    "front_ver": file_version,
                },
            )

            if resp.status_code != 200:
                logger.error("[KDocs] API 请求失败: HTTP %s", resp.status_code)
                return None

            return resp.json()

    @classmethod
    def crawl_source(cls, source: dict, limit: int | None = None) -> list[dict]:
        share_url = source.get("share_url", "")
        file_id = source.get("file_id", "")
        share_code = source.get("share_code", "")
        category = source.get("category", "anime")

        if not share_url or not share_code:
            logger.warning("[KDocs] 源 %s 配置不完整，跳过", source.get("name", ""))
            return []

        now = datetime.now().strftime("%m月%d日 %H:%M")

        params = cls.fetch_params_via_playwright(share_url)
        if not params:
            logger.error("[KDocs] 获取参数失败: %s", share_url)
            return []

        if not file_id and params.get("file_id"):
            file_id = params["file_id"]

        doc_data = cls.fetch_doc_via_api(
            share_code, file_id, share_url,
            params["conn_id"],
            params["user_group"],
            params.get("file_version", 0),
            params["csrf_token"],
        )
        if not doc_data:
            logger.error("[KDocs] 获取文档数据失败: %s", share_url)
            return []

        entries = parse_doc(doc_data, now)
        total_entries = len(entries)
        entries = _filter_latest_section_entries(entries, limit=limit)
        logger.info(
            "[KDocs] %s 爬取完成: 本次入库候选 %d/%d 条",
            source.get("name", ""),
            len(entries),
            total_entries,
        )

        results = []
        for idx, entry in enumerate(entries):
            digest = hashlib.sha1(f"{category}:{entry['name']}".encode("utf-8")).hexdigest()[:12]
            anime_id = f"{category}_{idx}_{digest}"
            results.append({
                "anime_id": anime_id,
                "title": entry["name"],
                "category": category,
                "quality": "",
                "episode": "",
                "status": "",
                "baidu_url": entry.get("baidu_link", ""),
                "baidu_password": entry.get("baidu_code", ""),
                "quark_url": entry.get("quark_link", ""),
                "4k_url": entry.get("4k_link", ""),
                "xunlei_url": entry.get("xunlei_link", ""),
                "update_time": entry.get("source_date") or now,
            })

        return results

    @classmethod
    def crawl_all(cls, categories: list[str] | None = None, limit_per_source: int | None = None) -> list[dict]:
        all_entries = []
        for source in KDOCS_SOURCES:
            if categories and source.get("category") not in categories:
                continue
            try:
                entries = cls.crawl_source(source, limit=limit_per_source)
                all_entries.extend(entries)
            except Exception as e:
                logger.error("[KDocs] 爬取 %s 失败: %s", source.get("name", ""), e)
        return all_entries
