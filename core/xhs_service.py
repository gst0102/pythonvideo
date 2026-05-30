import logging
import os
import re
from pathlib import Path
from typing import Iterator

import requests

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 代理配置（与 video_service 共用 PROXY_URL）
PROXY_URL = os.getenv("PROXY_URL")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/136.0.0.0 Safari/537.36"
)


def _build_proxies() -> dict | None:
    """构造代理字典，供所有 HTTP 请求使用"""
    if PROXY_URL:
        return {"http": PROXY_URL, "https": PROXY_URL}
    return None


def _build_session() -> requests.Session:
    """创建带连接池的 Session（可选代理）"""
    session = requests.Session()
    session.proxies = _build_proxies()
    adapter = requests.adapters.HTTPAdapter(
        pool_connections=5,
        pool_maxsize=5,
        max_retries=2,
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


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
                logger.info("[XHS] 找到 cookie 文件: %s", candidate)
                return candidate
            elif candidate.exists() and not candidate.is_file():
                logger.warning("[XHS] cookie 路径存在但不是文件（可能是目录）: %s", candidate)
        return None

    @classmethod
    def resolve_short_link(cls, short_url: str) -> str:
        """Follow xhslink.com redirect to get the real xiaohongshu URL."""
        logger.info("[XHS] 正在解析短链接: %s", short_url)
        try:
            session = _build_session()
            resp = session.get(
                short_url,
                headers={"User-Agent": USER_AGENT},
                allow_redirects=True,
                timeout=15,
            )
            final_url = resp.url
            logger.info("[XHS] 短链接解析结果: %s (status=%s)", final_url, resp.status_code)
            session.close()
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

        logger.info("[XHS] 最终 URL: %s (代理: %s)", url, "有" if PROXY_URL else "无")

        cookie_file = cls.resolve_cookie_file()
        cookies = cls.parse_netscape_cookies(cookie_file)
        if cookies:
            logger.info("[XHS] 加载了 %d 个 cookie (来源: %s)", len(cookies), cookie_file)
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

        # 如果有代理，也传给 yt-dlp
        if PROXY_URL:
            ydl_opts["proxy"] = PROXY_URL

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
        logger.info("[XHS] 请求API: %s (代理: %s)", api_url, "有" if PROXY_URL else "无")

        try:
            session = _build_session()
            resp = session.get(api_url, headers=headers, timeout=30)
            logger.info("[XHS] API响应状态: %s", resp.status_code)

            # 先尝试解析 JSON，即使状态码非 200 也可能有错误信息
            try:
                data = resp.json()
            except ValueError:
                logger.error("[XHS] API返回非JSON: %s...", resp.text[:500])
                raise ValueError(f"小红书API返回非JSON (HTTP {resp.status_code}): {resp.text[:200]}")

            resp.raise_for_status()
            session.close()
        except requests.HTTPError as e:
            logger.error("[XHS] API HTTP错误 %s: %s", resp.status_code if 'resp' in dir() else '?', e)
            # 尝试从响应中提取错误信息
            error_msg = data.get("msg", str(e)) if 'data' in dir() else str(e)
            raise ValueError(f"小红书API请求失败 (HTTP {getattr(resp, 'status_code', '?')}): {error_msg}")
        except requests.RequestException as e:
            logger.error("[XHS] API网络错误: %s (代理=%s)", e, PROXY_URL or "无")
            raise ValueError(f"小红书API网络请求失败: {e}")

        if not data.get("success"):
            msg = data.get("msg", "未知错误")
            logger.error("[XHS] API返回失败: success=False, msg=%s", msg)
            raise ValueError(f"小红书API返回失败: {msg}")

        items = data.get("data", {}).get("items", [])
        if not items:
            logger.error("[XHS] API返回空items, 完整响应: %s", 
                         str(data)[:500])
            raise ValueError("小红书API未返回视频数据（可能是链接无效或需要登录）")

        note = items[0].get("note_card", items[0])
        title = note.get("display_title", note.get("title", "小红书视频"))
        video_info = note.get("video", {})

        if not video_info:
            logger.error("[XHS] 笔记不包含视频, note_card keys: %s", list(note.keys())[:10])
            raise ValueError("该笔记不包含视频（可能是图文笔记）")

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
            logger.error("[XHS] 未能提取视频地址, stream keys: %s, video_info keys: %s",
                         list(stream_data.keys()), list(video_info.keys())[:10])
            raise ValueError("无法从小红书提取视频地址（视频流字段为空）")

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