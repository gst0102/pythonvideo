# routers/video.py
import asyncio
import json
import urllib.parse
import logging
import uuid
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, field_validator
from typing import Any
from core.video_service import VideoService
from core.response import response
from core.databaseApi import redis_pool
import requests
import yt_dlp
import time

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 简单的内存速率限制器
rate_limit_store = {}
RATE_LIMIT = 5  # 每分钟最大请求数
RATE_LIMIT_WINDOW = 60  # 时间窗口（秒）

router = APIRouter(prefix="/video", tags=["视频相关接口"])

class VideoRequest(BaseModel):
    url: str
    user_id: str = "anonymous"
    format_preset: str = "fast"  # fast, medium, quality

    @field_validator("url", "format_preset", mode="before")
    @classmethod
    def check_not_empty(cls, v: Any, info: Any) -> Any:
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"{info.field_name}必填")
        return v
    
    @field_validator("format_preset")
    @classmethod
    def validate_format_preset(cls, v: str) -> str:
        # 验证格式预设值
        valid_presets = ["fast", "medium", "quality"]
        if v not in valid_presets:
            raise ValueError(f"格式预设必须是以下之一: {', '.join(valid_presets)}")
        return v

def check_rate_limit(client_ip: str) -> bool:
    """检查客户端IP是否超过速率限制"""
    current_time = time.time()
    
    if client_ip not in rate_limit_store:
        rate_limit_store[client_ip] = []
    
    # 清理过期的请求记录
    rate_limit_store[client_ip] = [t for t in rate_limit_store[client_ip] if current_time - t < RATE_LIMIT_WINDOW]
    
    # 检查是否超过限制
    if len(rate_limit_store[client_ip]) >= RATE_LIMIT:
        return False
    
    # 记录本次请求
    rate_limit_store[client_ip].append(current_time)
    return True

@router.post('/video_info', summary='获取视频信息')
async def get_video_info(request: Request, video_request: VideoRequest):
    client_ip = request.client.host
    user_id = video_request.user_id
    logger.info(f"收到视频信息请求 from 用户 {user_id} (IP: {client_ip}): {video_request.url}")
    
    try:
        # 检查速率限制
        rate_limit_key = f"{user_id}:{client_ip}"
        if not check_rate_limit(rate_limit_key):
            logger.warning(f"速率限制触发 for 用户 {user_id} (IP: {client_ip})")
            raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
        
        # 在线程池中运行阻塞操作
        logger.info(f"开始获取视频信息 for 用户 {user_id}: {video_request.url}")
        video_info = await asyncio.to_thread(VideoService.get_video_info, video_request.url)
        logger.info(f"视频信息获取完成 for 用户 {user_id}")
        
        return response(
            data=video_info,
            code=200,
            msg="获取视频信息成功"
        )
        
    except ValueError as e:
        logger.error(f"值错误 for 用户 {user_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"服务器内部错误 for 用户 {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.get('/user_video', summary='下载视频(GET-查询参数)')
async def get_video_url_get(
    request: Request, 
    user_id: str, 
    url: str, 
    format_preset: str = "fast"
):
    """GET 方式，参数通过查询字符串传递"""
    return await _download_video(request, user_id, url, format_preset)


@router.post('/user_video', summary='下载视频(POST-JSON body，推荐)')
async def get_video_url_post(
    request: Request,
    body: VideoRequest,
):
    """POST 方式，参数通过 JSON body 传递，适合长 URL"""
    return await _download_video(request, body.user_id, body.url, body.format_preset)


# ═══ Token 下载（解决长 URL 编码 + 小程序文件限额）═══

# Redis token 存储（支持多 worker 进程共享）
_DOWNLOAD_TOKEN_PREFIX = "video:download:"
_TOKEN_TTL = 300  # 5分钟有效


@router.post('/download-token', summary='生成下载Token')
async def create_download_token(body: VideoRequest):
    """POST 接收长 URL，返回短 token。前端用 token 调 GET /download/{token} 下载"""
    token = uuid.uuid4().hex[:16]
    redis_key = f"{_DOWNLOAD_TOKEN_PREFIX}{token}"

    entry = json.dumps({
        "url": body.url,
        "user_id": body.user_id,
        "format_preset": body.format_preset,
    })

    if redis_pool:
        import redis.asyncio as aioredis
        client = aioredis.Redis(connection_pool=redis_pool, decode_responses=True)
        await client.setex(redis_key, _TOKEN_TTL, entry)
        await client.aclose()

    logger.info(f"[Token] 生成 token={token} for {body.url[:60]}...")
    return response(data={"token": token, "expires_in": _TOKEN_TTL}, code=200, msg="Token 已生成")


@router.get('/download/{token}', summary='Token下载视频')
async def download_by_token(request: Request, token: str):
    """通过 token 下载视频，避免长 URL 在查询参数中"""
    redis_key = f"{_DOWNLOAD_TOKEN_PREFIX}{token}"
    entry = None

    if redis_pool:
        import redis.asyncio as aioredis
        client = aioredis.Redis(connection_pool=redis_pool, decode_responses=True)
        raw = await client.get(redis_key)
        if raw:
            entry = json.loads(raw)
            await client.delete(redis_key)  # 一次性 token，用完即删
        await client.aclose()

    if not entry:
        raise HTTPException(status_code=404, detail="Token 无效或已过期")

    return await _download_video(
        request, entry["user_id"], entry["url"], entry["format_preset"]
    )


# ═══ 核心下载逻辑 ═══

async def _download_video(request: Request, user_id: str, url: str, format_preset: str):
    client_ip = request.client.host
    logger.info(f"收到视频下载请求 from 用户 {user_id} (IP: {client_ip}): {url}")
    
    try:
        # 验证参数
        if not user_id or not user_id.strip():
            raise ValueError("用户ID不能为空")
        if not url or not url.strip():
            raise ValueError("视频URL不能为空")
        
        # 验证URL格式
        import re
        url_pattern = re.compile(r'^https?://[\w\-]+(\.[\w\-]+)+([\w\-.,@?^=%&:/~+#]*[\w\-@?^=%&/~+#])?$')
        if not url_pattern.match(url):
            raise ValueError("URL格式无效")
        
        # 验证格式预设
        valid_presets = ["fast", "medium", "quality"]
        if format_preset not in valid_presets:
            raise ValueError(f"格式预设必须是以下之一: {', '.join(valid_presets)}")
        
        # 检查速率限制（基于用户ID和IP的组合，确保每个用户都有独立的限制）
        rate_limit_key = f"{user_id}:{client_ip}"
        if not check_rate_limit(rate_limit_key):
            logger.warning(f"速率限制触发 for 用户 {user_id} (IP: {client_ip})")
            raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
        
        # 在线程池中运行阻塞操作，避免阻塞事件循环
        logger.info(f"开始处理视频 for 用户 {user_id}: {url}")
        video_title, video_generator, source_headers = await asyncio.to_thread(
            VideoService.create_stream_generator, 
            url, 
            format_preset
        )
        logger.info(f"视频处理完成 for 用户 {user_id}，标题: {video_title}")
        
        # 使用统一 response 返回流
        # 关键点：传入生成器，并指定 media_type 为 video/mp4
        # 使用视频标题作为文件名
        encoded_title = urllib.parse.quote(video_title)
        
        # 构建响应头，合并源站头信息和自定义头信息
        headers = source_headers.copy() if source_headers else {}
        headers["Content-Disposition"] = f"attachment; filename={encoded_title}.mp4" # 告诉浏览器要下载文件
        
        # 如果源站没有提供Content-Type，设置默认值
        if "Content-Type" not in headers:
            headers["Content-Type"] = "video/mp4"
        
        logger.info(f"返回视频流 for 用户 {user_id}: {video_title}")
        logger.info(f"响应头信息: {headers}")
        
        return response(
            data=video_generator, 
            code=200, 
            msg="开始下载",
            media_type=headers.get("Content-Type", "video/mp4"),
            headers=headers
        )
        
    except ValueError as e:
        # 处理值错误，如无法提取视频信息
        logger.error(f"值错误 for 用户 {user_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except requests.exceptions.RequestException as e:
        # 处理网络请求错误
        logger.error(f"网络请求失败 for 用户 {user_id}: {str(e)}")
        raise HTTPException(status_code=502, detail=f"网络请求失败: {str(e)}")
    except yt_dlp.utils.DownloadError as e:
        # 处理视频下载错误
        logger.error(f"视频下载失败 for 用户 {user_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=f"视频下载失败: {str(e)}")
    except Exception as e:
        # 处理其他未预期的错误
        logger.error(f"服务器内部错误 for 用户 {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.post('/video_download_with_progress', summary='带进度的视频下载')
async def download_video_with_progress(request: Request, video_request: VideoRequest):
    client_ip = request.client.host
    user_id = video_request.user_id
    logger.info(f"收到带进度的视频下载请求 from 用户 {user_id} (IP: {client_ip}): {video_request.url}")
    
    try:
        # 检查速率限制
        rate_limit_key = f"{user_id}:{client_ip}"
        if not check_rate_limit(rate_limit_key):
            logger.warning(f"速率限制触发 for 用户 {user_id} (IP: {client_ip})")
            raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
        
        # 生成唯一的下载ID
        import uuid
        download_id = str(uuid.uuid4())
        
        async def progress_generator():
            import json
            import time
            
            # 1. 首先返回开始状态
            yield json.dumps({"status": "start", "download_id": download_id, "message": "开始处理视频"}) + "\n"
            
            # 2. 在线程池中执行视频处理
            start_time = time.time()
            video_title, video_generator, source_headers = await asyncio.to_thread(
                VideoService.create_stream_generator, 
                video_request.url, 
                video_request.format_preset
            )
            
            # 3. 计算处理时间
            process_time = time.time() - start_time
            yield json.dumps({"status": "processing", "progress": 30, "message": f"视频处理完成，用时 {process_time:.2f} 秒"}) + "\n"
            
            # 4. 准备下载链接
            encoded_title = urllib.parse.quote(video_title)
            download_url = f"/video/user_video?url={urllib.parse.quote(video_request.url)}&user_id={user_id}&format_preset={video_request.format_preset}"
            
            # 5. 模拟下载准备进度
            for i in range(40, 101, 10):
                yield json.dumps({"status": "preparing", "progress": i, "message": f"准备下载... {i}%"}) + "\n"
                await asyncio.sleep(0.5)
            
            # 6. 返回完成状态和下载链接
            yield json.dumps({
                "status": "completed", 
                "progress": 100, 
                "message": "生成完毕，这是下载链接",
                "download_url": download_url,
                "video_title": video_title
            }) + "\n"
        
        # 返回进度流，使用 application/x-ndjson 格式
        return response(
            data=progress_generator(),
            code=200,
            msg="开始下载",
            media_type="application/x-ndjson"
        )
        
    except ValueError as e:
        logger.error(f"值错误 for 用户 {user_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"服务器内部错误 for 用户 {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")