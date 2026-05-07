# routers/video.py
import asyncio
import urllib.parse
import logging
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, field_validator
from typing import Any
from core.video_service import VideoService
from core.response import response # 导入修改后的 response
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
    user_id: str
    format_preset: str = "fast"  # fast, medium, quality

    @field_validator("url", "user_id", "format_preset", mode="before")
    @classmethod
    def check_not_empty(cls, v: Any, info: Any) -> Any:
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"{info.field_name}必填")
        return v


    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        # 简单验证 user_id 格式，可根据实际需求调整
        if not v or len(v.strip()) == 0:
            raise ValueError("用户ID不能为空")
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


@router.get('/user_video', summary='下载视频')
async def get_video_url(
    request: Request, 
    user_id: str, 
    url: str, 
    format_preset: str = "fast"
):
    """
    下载视频
    - user_id: 用户ID
    - url: 视频URL
    - format_preset: 格式预设 (fast, medium, quality)
    """
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