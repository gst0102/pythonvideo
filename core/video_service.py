# core/video_service.py
import yt_dlp
import os
import requests
import logging
from typing import Iterator ,Tuple
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

COOKIE_FILE = os.getenv('COOKIE_FILE', 'cookies.txt')
PROXY_URL = os.getenv('PROXY_URL', None) 

class VideoService:
    @staticmethod
    def get_ytdlp_options(format_preset: str = "fast"):
        # 根据预设选择格式
        format_map = {
            "fast": "best[ext=mp4]/best",  # 优先选择 MP4 格式，通用
            "medium": "best[filesize<100M]/best",  # 100MB以内最佳质量
            "quality": "best/best"  # 最佳质量，通用格式
        }
        
        return {
            'cookiefile': COOKIE_FILE,
            'format': format_map.get(format_preset, format_map["fast"]),
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'retries': 3,
            'fragment_retries': 3,
        }

    @staticmethod
    def fetch_stream(real_url: str) -> tuple[requests.Response, dict]:
        """建立到源站的流式连接，返回响应对象和头信息"""
        proxies = {'http': PROXY_URL, 'https': PROXY_URL} if PROXY_URL else None
        # 核心优化3: 配置底层 Session，使用更高效的流读取方式
        session = requests.Session()
        # 这是一个黑科技参数，让 urllib3 保持连接活跃，减少握手开销
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=10,
            max_retries=3
        )
        session.mount('http://', adapter)
        session.mount('https://', adapter)

        logger.info(f"建立流式连接到: {real_url}")
        # stream=True 是必须的
        # 核心优化4: timeout 设置防止无限期挂起
        response = session.get(
            real_url, 
            stream=True, 
            proxies=proxies, 
            headers={'User-Agent': 'Mozilla/5.0'},
            timeout=(5, 10) # 连接超时5秒，读取超时10秒
        )
        response.raise_for_status()
        
        # 提取关键头信息
        headers = {}
        if 'content-length' in response.headers:
            headers['Content-Length'] = response.headers['content-length']
        if 'content-type' in response.headers:
            headers['Content-Type'] = response.headers['content-type']
        if 'content-range' in response.headers:
            headers['Content-Range'] = response.headers['content-range']
        if 'accept-ranges' in response.headers:
            headers['Accept-Ranges'] = response.headers['accept-ranges']
        
        logger.info(f"获取到源站头信息: {headers}")
        return response, headers

    @classmethod
    def get_video_info(cls, video_url: str) -> dict:
        """
        获取视频信息，包括标题、封面图和清晰度选项
        """
        ydl_opts = cls.get_ytdlp_options("fast")
        logger.info(f"开始获取视频信息: {video_url}")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            if not info:
                raise ValueError("无法提取视频信息")
            
            # 构建视频信息
            video_info = {
                "title": info.get('title', 'video'),
                "thumbnail": info.get('thumbnail', ''),
                "formats": [
                    {"preset": "fast", "label": "快速", "description": "优先MP4格式，解析速度快"},
                    {"preset": "medium", "label": "中等", "description": "100MB以内最佳质量"},
                    {"preset": "quality", "label": "高质量", "description": "最佳画质"}
                ]
            }
            
            logger.info(f"视频信息获取成功: {video_info['title']}")
            return video_info

    @classmethod 
    def create_stream_generator(cls, video_url: str, format_preset: str = "fast") -> Tuple[str, Iterator[bytes], dict]:
        """
        生成器：解析 -> 连接 -> 流式转发
        先获取视频信息，再返回生成器和头信息
        """
        logger.info(f"开始处理视频URL: {video_url}")

        # 尝试不同的格式预设
        presets_to_try = [format_preset, "fast"]
        last_error = None

        for preset in presets_to_try:
            try:
                ydl_opts = cls.get_ytdlp_options(preset)
                logger.info(f"尝试使用格式预设: {preset}")

                # 先获取视频信息和真实URL
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    logger.info("正在提取视频信息...")
                    info = ydl.extract_info(video_url, download=False)
                    if not info:
                        raise ValueError("无法提取视频信息")
                    
                    real_url = None
                    if 'url' in info:
                        real_url = info['url']
                    elif 'formats' in info and len(info['formats']) > 0:
                        # 优先选择 mp4，避免 flv 等需要转码的格式
                        for f in info['formats']:
                            if f.get('ext') == 'mp4' and f.get('url'):
                                real_url = f['url']
                                break
                        if not real_url:
                            # 尝试获取第一个可用格式
                            for f in info['formats']:
                                if f.get('url'):
                                    real_url = f['url']
                                    break
                    if not real_url:
                        raise ValueError("无法获取视频URL")

                    # 获取视频标题
                    video_title = info.get('title', 'video')
                    logger.info(f"视频标题: {video_title}")

                # 先获取源站头信息
                source_resp, source_headers = cls.fetch_stream(real_url)

                # 定义生成器函数
                def stream_generator() -> Iterator[bytes]:
                    try:
                        logger.info(f"【连接源站】准备拉取视频流: {video_title}")

                        # 使用 raw.stream 直接读取，性能比 iter_content 高 10%-20%
                        # decode_content=True 会自动处理 gzip/deflate 等编码
                        for chunk in source_resp.raw.stream(65536, decode_content=True):
                            if chunk: 
                                # 如果是 bytes 直接 yield；如果是 memoryview 转换一下
                                yield chunk.tobytes() if hasattr(chunk, 'tobytes') else chunk

                        logger.info("【传输完成】视频流传输结束")

                    except Exception as e:
                        logger.error(f"【传输错误】流式传输中断: {str(e)}")
                        raise
                    finally:
                        if source_resp and hasattr(source_resp, 'close'):
                            source_resp.close()
                            logger.info("【连接关闭】源站连接已释放")

                # 返回视频标题、生成器和头信息
                return video_title, stream_generator(), source_headers

            except Exception as e:
                logger.warning(f"使用预设 {preset} 失败: {str(e)}")
                last_error = e
                continue

        # 如果所有预设都失败，抛出最后一个错误
        if last_error:
            raise last_error
        else:
            raise ValueError("无法处理视频")

