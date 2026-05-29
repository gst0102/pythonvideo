import logging
import os
from pathlib import Path
from typing import Iterator, Tuple

import requests
import yt_dlp
from dotenv import load_dotenv

from core.douyin_service import DouyinService
from core.xhs_service import XiaohongshuService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

PROXY_URL = os.getenv("PROXY_URL")

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class VideoService:
    @staticmethod
    def resolve_cookie_file() -> str | None:
        configured = os.getenv("COOKIE_FILE", "cookies.txt")
        candidates: list[Path] = []

        configured_path = Path(configured)
        if not configured_path.is_absolute():
            configured_path = PROJECT_ROOT / configured_path
        candidates.append(configured_path)

        for fallback_name in ("cookies.txt.dan", "cookies.txt"):
            fallback_path = PROJECT_ROOT / fallback_name
            if fallback_path not in candidates:
                candidates.append(fallback_path)

        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                logger.info("[VideoService] 找到 cookie 文件: %s", candidate)
                return str(candidate)
        logger.warning("[VideoService] 未找到 cookie 文件: %s，可能无法下载需要登录的视频", candidates[0] if candidates else "N/A")
        return None

    @classmethod
    def get_ytdlp_options(cls, format_preset: str = "fast") -> dict:
        format_map = {
            "fast": "best[ext=mp4]/best",
            "medium": "best[filesize<100M]/best",
            "quality": "best/best",
        }

        options = {
            "format": format_map.get(format_preset, format_map["fast"]),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "retries": 3,
            "fragment_retries": 3,
        }

        cookiefile = cls.resolve_cookie_file()
        if cookiefile:
            options["cookiefile"] = cookiefile

        return options

    @staticmethod
    def fetch_stream(real_url: str, request_headers: dict | None = None) -> tuple[requests.Response, dict]:
        proxies = {"http": PROXY_URL, "https": PROXY_URL} if PROXY_URL else None
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=10,
            max_retries=3,
        )
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        headers = {"User-Agent": "Mozilla/5.0"}
        if request_headers:
            headers.update(request_headers)

        logger.info("建立流式连接: %s", real_url)
        source_response = session.get(
            real_url,
            stream=True,
            proxies=proxies,
            headers=headers,
            timeout=(5, 10),
        )
        source_response.raise_for_status()

        source_headers = {}
        if "content-length" in source_response.headers:
            source_headers["Content-Length"] = source_response.headers["content-length"]
        if "content-type" in source_response.headers:
            source_headers["Content-Type"] = source_response.headers["content-type"]
        if "content-range" in source_response.headers:
            source_headers["Content-Range"] = source_response.headers["content-range"]
        if "accept-ranges" in source_response.headers:
            source_headers["Accept-Ranges"] = source_response.headers["accept-ranges"]

        logger.info("源站响应头: %s", source_headers)
        return source_response, source_headers

    @classmethod
    def get_video_info(cls, video_url: str) -> dict:
        # 抖音：先试 DouyinService，失败则降级到 yt-dlp
        if DouyinService.is_douyin_url(video_url):
            try:
                return DouyinService.get_video_info(video_url)
            except Exception as e:
                logger.warning("DouyinService 提取失败，降级到 yt-dlp: %s", e)

        if XiaohongshuService.is_xhs_url(video_url):
            return XiaohongshuService.get_video_info(video_url)

        ydl_opts = cls.get_ytdlp_options("fast")
        logger.info("开始获取视频信息: %s", video_url)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            if not info:
                raise ValueError("无法提取视频信息")

            video_info = {
                "title": info.get("title", "video"),
                "thumbnail": info.get("thumbnail", ""),
                "formats": [
                    {"preset": "fast", "label": "快速", "description": "优先 MP4 格式，解析速度快"},
                    {"preset": "medium", "label": "标准", "description": "限制 100MB 内的较优格式"},
                    {"preset": "quality", "label": "高清", "description": "优先更高质量源"},
                ],
            }

            logger.info("视频信息获取成功: %s", video_info["title"])
            return video_info

    @classmethod
    def create_stream_generator(cls, video_url: str, format_preset: str = "fast") -> Tuple[str, Iterator[bytes], dict]:
        logger.info("开始处理视频 URL: %s", video_url)

        # 抖音：先试 DouyinService，失败则降级到 yt-dlp
        if DouyinService.is_douyin_url(video_url):
            try:
                return cls._create_douyin_stream_generator(video_url)
            except Exception as e:
                logger.warning("DouyinService 流提取失败，降级到 yt-dlp: %s", e)
                # fall through to yt-dlp below

        if XiaohongshuService.is_xhs_url(video_url):
            return cls._create_xhs_stream_generator(video_url)

        presets_to_try = [format_preset, "fast"]
        last_error = None

        for preset in presets_to_try:
            try:
                ydl_opts = cls.get_ytdlp_options(preset)
                logger.info("尝试使用格式预设: %s", preset)

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    logger.info("正在提取视频信息...")
                    info = ydl.extract_info(video_url, download=False)
                    if not info:
                        raise ValueError("无法提取视频信息")

                    real_url = None
                    if "url" in info:
                        real_url = info["url"]
                    elif "formats" in info and info["formats"]:
                        for item in info["formats"]:
                            if item.get("ext") == "mp4" and item.get("url"):
                                real_url = item["url"]
                                break
                        if not real_url:
                            for item in info["formats"]:
                                if item.get("url"):
                                    real_url = item["url"]
                                    break

                    if not real_url:
                        raise ValueError("无法获取视频 URL")

                    video_title = info.get("title", "video")
                    logger.info("视频标题: %s", video_title)

                source_resp, source_headers = cls.fetch_stream(real_url)

                def stream_generator() -> Iterator[bytes]:
                    try:
                        logger.info("开始转发视频流: %s", video_title)
                        for chunk in source_resp.raw.stream(65536, decode_content=True):
                            if chunk:
                                yield chunk.tobytes() if hasattr(chunk, "tobytes") else chunk
                        logger.info("视频流传输完成: %s", video_title)
                    except Exception as exc:
                        logger.error("视频流传输失败: %s", exc)
                        raise
                    finally:
                        source_resp.close()
                        logger.info("源站连接已关闭: %s", video_title)

                return video_title, stream_generator(), source_headers

            except Exception as exc:
                logger.warning("使用预设 %s 失败: %s", preset, exc)
                last_error = exc
                continue

        if last_error:
            raise last_error
        raise ValueError("无法处理视频")

    @classmethod
    def _create_douyin_stream_generator(cls, video_url: str) -> Tuple[str, Iterator[bytes], dict]:
        stream_info = DouyinService.extract_stream_info(video_url)
        video_title = stream_info["title"]

        if "blob_bytes" in stream_info:
            source_headers = {
                "Content-Type": stream_info.get("content_type", "video/mp4"),
                "Content-Length": stream_info.get("content_length", ""),
            }
            source_headers = {key: value for key, value in source_headers.items() if value}
            return video_title, DouyinService.bytes_to_stream(stream_info["blob_bytes"]), source_headers

        source_resp, source_headers = cls.fetch_stream(
            stream_info["stream_url"],
            request_headers={"Referer": stream_info.get("referer", video_url)},
        )

        def stream_generator() -> Iterator[bytes]:
            try:
                logger.info("开始转发抖音视频流: %s", video_title)
                for chunk in source_resp.raw.stream(65536, decode_content=True):
                    if chunk:
                        yield chunk.tobytes() if hasattr(chunk, "tobytes") else chunk
                logger.info("抖音视频流传输完成: %s", video_title)
            finally:
                source_resp.close()
                logger.info("抖音源站连接已关闭: %s", video_title)

        return video_title, stream_generator(), source_headers

    @classmethod
    def _create_xhs_stream_generator(cls, video_url: str) -> Tuple[str, Iterator[bytes], dict]:
        stream_info = XiaohongshuService.extract_stream_info(video_url)
        video_title = stream_info["title"]

        source_resp, source_headers = cls.fetch_stream(
            stream_info["stream_url"],
            request_headers={"Referer": stream_info.get("referer", video_url)},
        )

        def stream_generator() -> Iterator[bytes]:
            try:
                logger.info("开始转发小红书视频流: %s", video_title)
                for chunk in source_resp.raw.stream(65536, decode_content=True):
                    if chunk:
                        yield chunk.tobytes() if hasattr(chunk, "tobytes") else chunk
                logger.info("小红书视频流传输完成: %s", video_title)
            finally:
                source_resp.close()
                logger.info("小红书源站连接已关闭: %s", video_title)

        return video_title, stream_generator(), source_headers