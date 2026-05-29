import base64
import json
import logging
import os
import re
from pathlib import Path
from typing import Iterator

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PLAYWRIGHT_BROWSERS_PATH = PROJECT_ROOT / "down-test" / "pw_browsers"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/136.0.0.0 Safari/537.36"
)


class DouyinService:
    @staticmethod
    def is_douyin_url(url: str) -> bool:
        return bool(
            re.search(
                r"(?:https?://)?(?:www\.)?(?:v\.douyin\.com|douyin\.com|www\.douyin\.com|iesdouyin\.com)",
                url,
                re.IGNORECASE,
            )
        )

    @staticmethod
    def sanitize_filename(name: str) -> str:
        return re.sub(r'[<>:"/\\|?*]', "_", name).strip() or "douyin_video"

    @staticmethod
    def resolve_cookie_file() -> Path | None:
        candidates: list[Path] = []
        configured = os.getenv("DOUYIN_COOKIE_FILE")
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

    @staticmethod
    def extract_video_data(page) -> dict | None:
        """多策略提取抖音视频数据：RENDER_DATA → SSR_HYDRATION → script 标签"""
        result = page.evaluate(
            """
            () => {
                function firstString(items) {
                    if (!Array.isArray(items)) return '';
                    for (const item of items) {
                        if (typeof item === 'string' && item.startsWith('http')) return item;
                        if (item && typeof item.src === 'string' && item.src.startsWith('http')) return item.src;
                    }
                    return '';
                }

                function extractDetail(detail) {
                    if (!detail) return null;
                    const title = detail.desc || document.title || '';
                    const downloadUrl = firstString(detail.download?.urlList);
                    const playUrl = firstString(detail.video?.playAddr) || firstString(detail.video?.bitRateList?.[0]?.playAddr);
                    const videoUrl = downloadUrl || playUrl;
                    // 封面：优先取 cover/thumbnail，其次取 video 的 cover
                    const cover = firstString(detail.video?.cover?.urlList) ||
                                  firstString(detail.video?.dynamicCover?.urlList) ||
                                  firstString(detail.video?.originCover?.urlList) ||
                                  firstString(detail.images) || '';
                    return videoUrl ? { title, videoUrl, cover } : null;
                }

                // ═══ 策略1: RENDER_DATA ═══
                const renderData = document.getElementById('RENDER_DATA');
                if (renderData && renderData.textContent) {
                    try {
                        const raw = renderData.textContent.trim();
                        const decoded = raw.startsWith('%') ? decodeURIComponent(raw) : raw;
                        const data = JSON.parse(decoded);
                        const result = extractDetail(data?.app?.videoDetail);
                        if (result) { result.source = 'RENDER_DATA'; return result; }
                    } catch(e) {}
                }

                // ═══ 策略2: SSR_HYDRATION_DATA ═══
                const ssr = document.getElementById('SSR_HYDRATION_DATA');
                if (ssr && ssr.textContent) {
                    try {
                        const data = JSON.parse(ssr.textContent);
                        const result = extractDetail(data?.app?.videoDetail || data?.videoDetail);
                        if (result) { result.source = 'SSR_HYDRATION'; return result; }
                    } catch(e) {}
                }

                // ═══ 策略3: 从所有 script 标签里找 video 数据 ═══
                const scripts = document.querySelectorAll('script');
                for (const script of scripts) {
                    const text = script.textContent || script.innerHTML || '';
                    if (!text || text.length < 100) continue;
                    if (!text.includes('video') && !text.includes('playAddr')) continue;
                    try {
                        const data = JSON.parse(text);
                        const result = extractDetail(
                            data?.app?.videoDetail || data?.videoDetail ||
                            data?.props?.pageProps?.videoData ||
                            data?.serverRouter?.videoDetail
                        );
                        if (result) { result.source = 'script_tag'; return result; }
                    } catch(e) {}
                }

                return null;
            }
            """
        )
        return result

    @staticmethod
    def fetch_blob_bytes(page, blob_url: str) -> bytes:
        payload = page.evaluate(
            f"""
            async () => {{
                const response = await fetch({json.dumps(blob_url)});
                const blob = await response.blob();
                const buffer = await blob.arrayBuffer();
                const bytes = new Uint8Array(buffer);
                let binary = '';
                for (let i = 0; i < bytes.length; i++) {{
                    binary += String.fromCharCode(bytes[i]);
                }}
                return btoa(binary);
            }}
            """
        )
        return base64.b64decode(payload)

    @classmethod
    def get_video_info(cls, raw_url: str) -> dict:
        stream_info = cls.extract_stream_info(raw_url)
        return {
            "title": stream_info["title"],
            "thumbnail": stream_info.get("cover", ""),
            "formats": [
                {"preset": "fast", "label": "quick", "description": "Prefer fast direct stream"},
                {"preset": "medium", "label": "standard", "description": "Keep response shape consistent"},
                {"preset": "quality", "label": "hd", "description": "Use the best direct URL available"},
            ],
        }

    @classmethod
    def extract_stream_info(cls, raw_url: str) -> dict:
        if "PLAYWRIGHT_BROWSERS_PATH" not in os.environ and DEFAULT_PLAYWRIGHT_BROWSERS_PATH.exists():
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(DEFAULT_PLAYWRIGHT_BROWSERS_PATH)

        cookie_file = cls.resolve_cookie_file()
        cookies = cls.parse_netscape_cookies(cookie_file)
        captured_network_urls: list[str] = []

        logger.info("Start parsing douyin url: %s", raw_url)

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
            context = browser.new_context(
                user_agent=USER_AGENT,
                viewport={"width": 1536, "height": 864},
            )

            if cookies:
                context.add_cookies(cookies)

            page = context.new_page()
            page.add_init_script(
                """
                Object.defineProperty(navigator, 'webdriver', { get: () => false });
                """
            )

            def on_response(response) -> None:
                url = response.url
                # 更宽泛的视频 URL 匹配
                if any(token in url for token in (".mp4", ".m3u8", "video", "playwm", "play/")):
                    excluded = ("douyinstatic.com", "/obj/", "/static/", "live.douyin.com")
                    if not any(token in url for token in excluded):
                        if any(token in url for token in ("douyinvod", "bytecdn", "snssdk", "vod", "ixigua", "byteimg")):
                            captured_network_urls.append(url)

            page.on("response", on_response)

            try:
                try:
                    page.goto(raw_url, wait_until="domcontentloaded", timeout=60_000)
                except PlaywrightTimeout:
                    logger.warning("Douyin page load timed out, continue extracting from DOM")

                video_data = None
                for _ in range(8):  # 减少到 8 秒，多策略提取更快
                    page.wait_for_timeout(1000)
                    video_data = cls.extract_video_data(page)
                    if video_data and video_data.get("videoUrl"):
                        logger.info("Douyin 提取成功，数据源: %s", video_data.get("source", "?"))
                        break

                    if captured_network_urls:
                        video_data = {
                            "title": page.title() or "",
                            "author": "",
                            "videoUrl": captured_network_urls[0],
                            "duration": 0,
                            "cover": "",
                        }
                        break

                if not video_data or not video_data.get("videoUrl"):
                    raise ValueError("Unable to extract douyin video url")

                title = cls.sanitize_filename(video_data.get("title") or page.title() or "douyin_video")
                stream_url = video_data["videoUrl"]
                referer = page.url or raw_url
                cover = video_data.get("cover", "")

                # 兜底：从页面 meta/poster/img 提取封面
                if not cover:
                    cover = page.evaluate("""
                        () => {
                            const m = document.querySelector('meta[property="og:image"],meta[name="twitter:image"],meta[itemprop="image"]');
                            if (m) { const v = m.content || m.getAttribute('content'); if (v && v.startsWith('http')) return v; }
                            const v = document.querySelector('video[poster]');
                            if (v) { const p = v.getAttribute('poster'); if (p && p.startsWith('http')) return p; }
                            const imgs = document.querySelectorAll('img');
                            for (const img of imgs) {
                                const s = img.src || img.getAttribute('data-src') || '';
                                if (s.startsWith('http') && img.naturalWidth > 200 && !s.includes('douyinstatic') && !s.includes('logo'))
                                    return s;
                            }
                            return '';
                        }
                    """)
                    if cover:
                        logger.info("Douyin cover from fallback: %s", cover[:80])

                if stream_url.startswith("blob:"):
                    blob_bytes = cls.fetch_blob_bytes(page, stream_url)
                    return {
                        "title": title,
                        "cover": cover,
                        "blob_bytes": blob_bytes,
                        "content_type": "video/mp4",
                        "content_length": str(len(blob_bytes)),
                    }

                return {
                    "title": title,
                    "cover": cover,
                    "stream_url": stream_url,
                    "referer": referer,
                }
            finally:
                browser.close()

    @staticmethod
    def bytes_to_stream(video_bytes: bytes, chunk_size: int = 65536) -> Iterator[bytes]:
        for offset in range(0, len(video_bytes), chunk_size):
            yield video_bytes[offset : offset + chunk_size]
