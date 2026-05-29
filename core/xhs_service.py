import logging
import os
import re
from pathlib import Path
from typing import Iterator

import requests

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/136.0.0.0 Safari/537.36"
)


class XiaohongshuService:
    @staticmethod
    def is_xhs_url(url: str) -> bool:
        return bool(
            re.search(
                r"(?:https?://)?(?:www\.)?(?:xhslink\.com|xiaohongshu\.com|xhscdn\.com)",
                url,
                re.IGNORECASE,
            )
        )

    @staticmethod
    def sanitize_filename(name: str) -> str:
        return re.sub(r'[<>:"/\\|?*]', "_", name).strip() or "xhs_video"

    @staticmethod
    def resolve_cookie_file() -> Path | None:
        candidates: list[Path] = []
        configured = os.getenv("COOKIE_FILE") or os.getenv("XHS_COOKIE_FILE")
        if configured:
            configured_path = Path(configured)
            if not configured_path.is_absolute():
                configured_path = PROJECT_ROOT / configured_path
            candidates.append(configured_path)

        candidates.extend(
            [
                PROJECT_ROOT / "cookies.txt.dan",
                PROJECT_ROOT / "cookies.txt",
            ]
        )

        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return candidate
        return None

    @classmethod
    def resolve_short_link(cls, short_url: str) -> str:
        """Follow xhslink.com redirect to get the real xiaohongshu URL."""
        logger.info("[XHS] 正在解析短链接: %s", short_url)
        try:
            resp = requests.get(
                short_url,
                headers={"User-Agent": USER_AGENT},
                allow_redirects=True,
                timeout=15,
            )
            final_url = resp.url
            logger.info("[XHS] 短链接解析结果: %s", final_url)
            return final_url
        except requests.RequestException as e:
            logger.warning("[XHS] 短链接解析失败，使用原始 URL: %s", e)
            return short_url

    @staticmethod
    def parse_netscape_cookies(filepath: Path | None) -> list[dict]:
        cookies: list[dict] = []
        if not filepath or not filepath.exists():
            return cookies

        with filepath.open("r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                parts = line.split("\t")
                if len(parts) < 7 or not parts[5]:
                    continue

                cookies.append(
                    {
                        "name": parts[5],
                        "value": parts[6],
                        "domain": parts[0].lstrip("."),
                        "path": parts[2] or "/",
                        "secure": parts[3] == "TRUE",
                        "httpOnly": False,
                    }
                )

        return cookies

    @classmethod
    def get_video_info(cls, raw_url: str) -> dict:
        url = raw_url
        if "xhslink.com" in url:
            url = cls.resolve_short_link(url)

        return {
            "title": "小红书视频",
            "thumbnail": "",
            "formats": [
                {"preset": "fast", "label": "快速", "description": "优先 MP4 格式"},
                {"preset": "medium", "label": "标准", "description": "限制 100MB 内"},
                {"preset": "quality", "label": "高清", "description": "优先更高质量源"},
            ],
        }

    @classmethod
    def extract_stream_info(cls, raw_url: str) -> dict:
        import yt_dlp

        url = raw_url
        if "xhslink.com" in url:
            url = cls.resolve_short_link(url)

        logger.info("[XHS] 最终 URL: %s", url)

        cookie_file = cls.resolve_cookie_file()
        cookies = cls.parse_netscape_cookies(cookie_file)
        if cookies:
            logger.info("[XHS] 加载了 %d 个 cookie", len(cookies))
        else:
            logger.warning("[XHS] 未找到 cookie 文件，可能无法下载")

        ydl_opts = {
            "format": "best[ext=mp4]/best",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "user_agent": USER_AGENT,
            "retries": 3,
            "fragment_retries": 3,
        }

        if cookie_file:
            ydl_opts["cookiefile"] = str(cookie_file)

        logger.info("[XHS] 使用 yt-dlp 提取视频信息...")
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    raise ValueError("无法提取小红书视频信息")

                title = info.get("title", "小红书视频")
                real_url = None
                if "url" in info:
                    real_url = info["url"]
                elif "formats" in info and info["formats"]:
                    for fmt in info["formats"]:
                        if fmt.get("ext") == "mp4" and fmt.get("url"):
                            real_url = fmt["url"]
                            break
                    if not real_url:
                        for fmt in info["formats"]:
                            if fmt.get("url"):
                                real_url = fmt["url"]
                                break

                if not real_url:
                    raise ValueError("无法从小红书提取视频地址")

                logger.info("[XHS] 标题: %s", title)
                logger.info("[XHS] 视频地址: %s...", real_url[:100])

                return {
                    "title": cls.sanitize_filename(title),
                    "stream_url": real_url,
                    "referer": url,
                }
        except Exception as e:
            logger.error("[XHS] yt-dlp 提取失败: %s，回退到 API 方式", e)
            return cls._extract_via_api(url, cookie_file, cookies)

    @classmethod
    def _extract_via_api(cls, url: str, cookie_file, cookies) -> dict:
        note_id = cls._extract_note_id(url)
        if not note_id:
            raise ValueError(f"无法从小红书链接中提取笔记ID: {url}")

        logger.info("[XHS] 笔记ID: %s", note_id)

        headers = {
            "User-Agent": USER_AGENT,
            "Referer": "https://www.xiaohongshu.com/",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://www.xiaohongshu.com",
        }

        cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
        if cookie_str:
            headers["Cookie"] = cookie_str

        api_url = f"https://edith.xiaohongshu.com/api/sns/web/v1/feed?source_note_id={note_id}"
        logger.info("[XHS] 请求API: %s", api_url)

        try:
            resp = requests.get(api_url, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.error("[XHS] API请求失败: %s", e)
            raise ValueError(f"小红书API请求失败: {e}")

        if not data.get("success"):
            raise ValueError(f"小红书API返回失败: {data.get('msg', '未知错误')}")

        items = data.get("data", {}).get("items", [])
        if not items:
            raise ValueError("小红书API未返回视频数据")

        note = items[0].get("note_card", items[0])
        title = note.get("display_title", note.get("title", "小红书视频"))
        video_info = note.get("video", {})

        if not video_info:
            raise ValueError("该笔记不包含视频")

        media = video_info.get("media", {})
        stream_data = media.get("stream", {})

        stream_url = ""
        for quality in ("h264", "h265", "h266"):
            candidates = stream_data.get(quality, [])
            for candidate in candidates:
                master_url = candidate.get("master_url", "")
                if master_url:
                    stream_url = master_url
                    break
            if stream_url:
                break

        if not stream_url:
            stream_url = video_info.get("url", "") or video_info.get("video_url", "")

        if not stream_url:
            raise ValueError("无法从小红书提取视频地址")

        logger.info("[XHS-API] 标题: %s", title)
        logger.info("[XHS-API] 视频地址: %s...", stream_url[:100])

        return {
            "title": cls.sanitize_filename(title),
            "stream_url": stream_url,
            "referer": url,
        }

    @staticmethod
    def _extract_note_id(url: str) -> str | None:
        patterns = [
            r"/explore/([a-zA-Z0-9]+)",
            r"/discovery/item/([a-zA-Z0-9]+)",
            r"/note/([a-zA-Z0-9]+)",
            r"note_id=([a-zA-Z0-9]+)",
            r"source_note_id=([a-zA-Z0-9]+)",
        ]
        for p in patterns:
            m = re.search(p, url)
            if m:
                return m.group(1)
        logger.warning("[XHS] 无法从URL提取笔记ID: %s", url)
        return None

    @staticmethod
    def bytes_to_stream(video_bytes: bytes, chunk_size: int = 65536) -> Iterator[bytes]:
        for offset in range(0, len(video_bytes), chunk_size):
            yield video_bytes[offset : offset + chunk_size]