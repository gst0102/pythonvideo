"""
四平台逆向下载服务 v2（已去掉 Playwright / 快手）
原理：
- 小红书: 纯 Python SSR 解析，绕过 API 签名
- B站: 纯 Python 公开 API
- 抖音: 短链解析 → API 直调
- 头条: yt-dlp 提取

所有平台均返回可直接流式传输的 CDN URL。
"""
import json
import logging
import os
import re
from pathlib import Path
from typing import Iterator

import requests

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/148.0.0.0 Safari/537.36"
)


class ReverseService:
    XHS_DOMAIN = re.compile(r"(?:xhslink\.com|xiaohongshu\.com|xhscdn\.com)", re.I)
    BILI_DOMAIN = re.compile(r"(?:bilibili\.com|b23\.tv)", re.I)
    DOUYIN_DOMAIN = re.compile(r"(?:douyin\.com|iesdouyin\.com)", re.I)
    TOUTIAO_DOMAIN = re.compile(r"toutiao\.com", re.I)

    @staticmethod
    def sanitize_filename(name: str) -> str:
        return re.sub(r'[<>:"/\\|?*]', "_", name).strip() or "video"

    @classmethod
    def is_supported(cls, url: str) -> bool:
        return bool(
            cls.XHS_DOMAIN.search(url)
            or cls.BILI_DOMAIN.search(url)
            or cls.DOUYIN_DOMAIN.search(url)
            or cls.TOUTIAO_DOMAIN.search(url)
        )

    @classmethod
    def get_platform(cls, url: str) -> str:
        if cls.XHS_DOMAIN.search(url):
            return "xiaohongshu"
        if cls.BILI_DOMAIN.search(url):
            return "bilibili"
        if cls.DOUYIN_DOMAIN.search(url):
            return "douyin"
        if cls.TOUTIAO_DOMAIN.search(url):
            return "toutiao"
        return "unknown"

    @classmethod
    def extract(cls, url: str, format_preset: str = "fast") -> dict:
        platform = cls.get_platform(url)
        logger.info("[Reverse] 平台: %s, URL: %s", platform, url)
        if platform == "xiaohongshu":
            return cls._extract_xhs(url)
        if platform == "bilibili":
            return cls._extract_bilibili(url)
        if platform == "douyin":
            return cls._extract_douyin(url)
        if platform == "toutiao":
            return cls._extract_toutiao(url)
        raise ValueError(f"不支持的平台: {platform}")

    @classmethod
    def get_video_info(cls, url: str) -> dict:
        platform = cls.get_platform(url)
        if platform == "xiaohongshu":
            return cls._xhs_video_info(url)
        if platform == "bilibili":
            return cls._bili_video_info(url)
        if platform == "douyin":
            return cls._douyin_video_info(url)
        if platform == "toutiao":
            return cls._toutiao_video_info(url)
        return {
            "title": "未知视频",
            "thumbnail": "",
            "cover_url": "",
            "formats": [{"preset": "fast", "label": "快速", "description": "优先 MP4 格式"}],
        }

    # ============================================================
    #  小红书 — 纯 Python SSR，绕过 API 签名
    # ============================================================

    @classmethod
    def _resolve_xhs_short(cls, share_url: str) -> tuple[str, str, requests.Session]:
        session = requests.Session()
        session.headers.update({"User-Agent": UA})
        r = session.get(share_url, allow_redirects=False, timeout=15)
        loc = r.headers.get("Location", "")
        if not loc:
            raise ValueError("小红书短链接无重定向")
        if loc.startswith("/"):
            loc = "https://www.xiaohongshu.com" + loc
        note_id = ""
        m = re.search(r"/item/([a-f0-9]+)", loc)
        if m:
            note_id = m.group(1)
        return loc, note_id, session

    @classmethod
    def _extract_xhs(cls, url: str) -> dict:
        logger.info("[XHS] 解析: %s", url)
        loc, note_id, session = cls._resolve_xhs_short(url)
        resp = session.get(loc, timeout=15)
        html = resp.text
        if "你访问的页面不见了" in html:
            raise ValueError("小红书页面被拦截")
        pos = html.find("__INITIAL_STATE__=")
        if pos == -1:
            raise ValueError("小红书页面无 SSR 数据")
        pos = html.index("{", pos)
        depth = 0
        end = pos
        for i, ch in enumerate(html[pos:], pos):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        data = json.loads(html[pos:end].replace("undefined", "null"))
        note_map = data.get("note", {}).get("noteDetailMap", {})
        keys = [k for k in note_map if k != "null"]
        if not keys:
            raise ValueError("小红书无笔记数据")
        note = note_map[keys[0]].get("note", {})
        title = note.get("title") or note.get("displayTitle", "小红书视频")
        if note.get("type") != "video":
            raise ValueError("该笔记不是视频")
        video = note.get("video", {})
        media = video.get("media", {})
        stream = media.get("stream", {})
        video_urls = []
        for codec in ("h264", "h265", "av1"):
            for item in stream.get(codec, []):
                u = item.get("masterUrl") or item.get("master_url") or ""
                if u:
                    video_urls.append({"url": u, "codec": codec, "bitrate": item.get("bitrate") or item.get("bitRate") or 0})
        if not video_urls:
            raise ValueError("小红书未提取到视频流")
        video_urls.sort(key=lambda x: x["bitrate"], reverse=True)
        best = video_urls[0]["url"]
        cover = ""
        imgs = note.get("imageList") or note.get("image_list") or []
        if imgs:
            cover = imgs[0].get("urlDefault") or imgs[0].get("url_default") or ""
        logger.info("[XHS] 标题: %s, 流数: %d", title, len(video_urls))
        return {"title": cls.sanitize_filename(title), "stream_url": best, "cover_url": cover, "referer": loc, "all_streams": video_urls}

    @classmethod
    def _xhs_video_info(cls, url: str) -> dict:
        try:
            result = cls._extract_xhs(url)
            return {"title": result["title"], "thumbnail": result.get("cover_url", ""), "cover_url": result.get("cover_url", ""), "formats": [{"preset": "fast", "label": "快速", "description": "优先 MP4"}, {"preset": "quality", "label": "高清", "description": "最高码率"}]}
        except Exception:
            return {"title": "小红书视频", "thumbnail": "", "cover_url": "", "formats": [{"preset": "fast", "label": "快速", "description": "优先 MP4"}]}

    # ============================================================
    #  B站 — 纯 API
    # ============================================================

    @classmethod
    def _extract_bilibili(cls, url: str) -> dict:
        bvid = ""
        for p in (r"/video/(BV[a-zA-Z0-9]+)", r"bvid=(BV[a-zA-Z0-9]+)"):
            m = re.search(p, url)
            if m:
                bvid = m.group(1)
                break
        if not bvid:
            raise ValueError("无法提取 B站 BV 号")
        logger.info("[B站] BV: %s", bvid)
        hdrs = {"User-Agent": UA, "Referer": f"https://www.bilibili.com/video/{bvid}/", "Origin": "https://www.bilibili.com"}
        r = requests.get(f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}", headers=hdrs, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data.get("code") != 0:
            raise ValueError(f"B站 view API 失败: {data.get('message', '')}")
        d = data["data"]
        title = d["title"]
        cover = "https:" + d["pic"] if d["pic"].startswith("//") else d["pic"].replace("http://", "https://", 1)
        cid = d["pages"][0]["cid"]
        r2 = requests.get(f"https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&qn=112&fnval=1&fourk=1", headers=hdrs, timeout=10)
        r2.raise_for_status()
        play = r2.json()
        if play.get("code") != 0:
            raise ValueError(f"B站 playurl API 失败: {play.get('message', '')}")
        durl = play.get("data", {}).get("durl", [])
        if not durl:
            raise ValueError("B站无视频流")
        video_url = durl[0].get("url", "")
        if not video_url:
            raise ValueError("B站视频 URL 为空")
        logger.info("[B站] 标题: %s", title)
        return {"title": cls.sanitize_filename(title), "stream_url": video_url, "cover_url": cover, "referer": "https://www.bilibili.com/"}

    @classmethod
    def _bili_video_info(cls, url: str) -> dict:
        try:
            result = cls._extract_bilibili(url)
            return {"title": result["title"], "thumbnail": result.get("cover_url", ""), "cover_url": result.get("cover_url", ""), "formats": [{"preset": "fast", "label": "快速", "description": "优先 MP4"}, {"preset": "quality", "label": "高清", "description": "最高质量"}]}
        except Exception:
            return {"title": "B站视频", "thumbnail": "", "cover_url": "", "formats": [{"preset": "fast", "label": "快速", "description": "优先 MP4"}]}

    # ============================================================
    #  抖音 — 短链解析 → API 直调（无 Playwright 回退）
    # ============================================================

    @classmethod
    def _resolve_douyin_short(cls, raw_url: str) -> str | None:
        import httpx
        with httpx.Client(follow_redirects=False, timeout=15) as client:
            resp = client.get(raw_url, headers={"User-Agent": UA})
            location = resp.headers.get("location", "")
            m = re.search(r"/video/(\d+)", location)
            return m.group(1) if m else None

    @classmethod
    def _douyin_api_direct(cls, video_id: str) -> dict | None:
        import httpx
        cookies_str = cls._get_douyin_cookies_str()
        url = f"https://www.douyin.com/aweme/v1/web/aweme/detail/?aweme_id={video_id}&aid=6383&version_name=23.5.0&device_platform=web"
        headers = {"User-Agent": UA, "Referer": f"https://www.douyin.com/video/{video_id}", "Cookie": cookies_str}
        try:
            resp = httpx.get(url, headers=headers, timeout=15)
            if resp.status_code != 200:
                return None
            data = resp.json()
        except Exception:
            logger.warning("[抖音-API] 请求失败")
            return None
        aweme = data.get("aweme_detail", {})
        if not aweme:
            return None
        title = aweme.get("desc", "抖音视频")
        video = aweme.get("video", {})
        play_addr = video.get("play_addr", {}) or video.get("play_addr_h264", {})
        url_list = play_addr.get("url_list", []) or video.get("download_addr", {}).get("url_list", [])
        if not url_list:
            return None
        cover = ""
        cover_info = video.get("cover", {})
        if cover_info:
            cover_urls = cover_info.get("url_list", [])
            cover = cover_urls[0] if cover_urls else ""
        logger.info("[抖音-API] 标题: %s", title)
        return {"title": cls.sanitize_filename(title), "stream_url": url_list[0], "cover_url": cover, "referer": f"https://www.douyin.com/video/{video_id}"}

    @classmethod
    def _get_douyin_cookies_str(cls) -> str:
        candidates = [PROJECT_ROOT / "cookies.txt.dan", PROJECT_ROOT / "cookies.txt"]
        for c in candidates:
            if c.exists() and c.is_file():
                with c.open("r", encoding="utf-8") as f:
                    parts = []
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        seg = line.split("\t")
                        if len(seg) >= 7 and seg[5]:
                            domain = seg[0].lstrip(".")
                            if domain in ("douyin.com", "www.douyin.com", ".douyin.com"):
                                parts.append(f"{seg[5]}={seg[6]}")
                    return "; ".join(parts)
        return ""

    @classmethod
    def _extract_douyin(cls, url: str) -> dict:
        logger.info("[抖音] 解析: %s", url)
        video_id = cls._resolve_douyin_short(url)
        if not video_id:
            raise ValueError(f"无法从抖音链接提取视频ID: {url}")
        logger.info("[抖音] video_id: %s", video_id)
        result = cls._douyin_api_direct(video_id)
        if not result:
            raise ValueError("抖音API未返回视频数据（可能需要有效cookies或代理）")
        return result

    @classmethod
    def _douyin_video_info(cls, url: str) -> dict:
        try:
            result = cls._extract_douyin(url)
            return {"title": result["title"], "thumbnail": result.get("cover_url", ""), "cover_url": result.get("cover_url", ""), "formats": [{"preset": "fast", "label": "快速", "description": "优先 MP4"}, {"preset": "quality", "label": "高清", "description": "最高质量"}]}
        except Exception:
            return {"title": "抖音视频", "thumbnail": "", "cover_url": "", "formats": [{"preset": "fast", "label": "快速", "description": "优先 MP4"}]}

    # ============================================================
    #  头条 — yt-dlp（最稳定，无需浏览器）
    # ============================================================

    @classmethod
    def _extract_toutiao(cls, url: str) -> dict:
        import yt_dlp
        ydl_opts = {"format": "best[ext=mp4]/best", "noplaylist": True, "quiet": True, "no_warnings": True, "user_agent": UA, "retries": 3}
        cookiefile = cls._resolve_cookie()
        if cookiefile:
            ydl_opts["cookiefile"] = cookiefile
        logger.info("[头条] yt-dlp 提取: %s", url)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                raise ValueError("头条无法提取视频信息")
            real_url = info.get("url", "")
            if not real_url and info.get("formats"):
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
                raise ValueError("头条未提取到视频地址")
            title = info.get("title", "头条视频")
            cover = info.get("thumbnail", "")
            logger.info("[头条] 标题: %s", title)
            return {"title": cls.sanitize_filename(title), "stream_url": real_url, "cover_url": cover, "referer": url}

    @classmethod
    def _toutiao_video_info(cls, url: str) -> dict:
        try:
            result = cls._extract_toutiao(url)
            return {"title": result["title"], "thumbnail": result.get("cover_url", ""), "cover_url": result.get("cover_url", ""), "formats": [{"preset": "fast", "label": "快速", "description": "优先 MP4"}, {"preset": "quality", "label": "高清", "description": "最高质量"}]}
        except Exception:
            return {"title": "头条视频", "thumbnail": "", "cover_url": "", "formats": [{"preset": "fast", "label": "快速", "description": "优先 MP4"}]}

    @classmethod
    def _resolve_cookie(cls) -> str | None:
        import os
        candidates = [PROJECT_ROOT / "cookies.txt.dan", PROJECT_ROOT / "cookies.txt"]
        configured = os.getenv("COOKIE_FILE")
        if configured:
            p = Path(configured)
            if not p.is_absolute():
                p = PROJECT_ROOT / p
            candidates.insert(0, p)
        for c in candidates:
            if c.exists() and c.is_file():
                return str(c)
        return None