# controllers/wecom.py
# 企业微信视频号下载功能
# 完整流程: 用户转发视频到企业微信 -> 回调接收URL -> 发送小程序卡片 -> 前端传后端下载保存

import os
import yt_dlp
import asyncio
import uuid
import time
import logging
import re
import hashlib
import base64
import struct
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any, Optional

import httpx
from Crypto.Cipher import AES
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, field_validator

from core.response import response
from core.databaseApi import redis_pool

# 确保每次都重新加载 .env（uvicorn reload 不会重新读取 .env）
load_dotenv(override=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wecom", tags=["企业微信视频下载接口"])

DOWNLOADS_DIR = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

rate_limit_store = {}
RATE_LIMIT = 10
RATE_LIMIT_WINDOW = 60

WECOM_TOKEN_URL = os.getenv(
    "WECOM_API_GET_TOKEN",
    "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
)
WECOM_SEND_URL = os.getenv(
    "WECOM_API_SEND_MESSAGE",
    "https://qyapi.weixin.qq.com/cgi-bin/message/send"
)
WECOM_TOKEN_CACHE_KEY = os.getenv("WECOM_TOKEN_CACHE_KEY", "wecom:access_token")
WECOM_TOKEN_REFRESH_AHEAD = int(os.getenv("WECOM_TOKEN_REFRESH_AHEAD", "300"))


class WecomSaveVideoRequest(BaseModel):
    url: str
    user_id: str

    @field_validator("url", "user_id", mode="before")
    @classmethod
    def check_not_empty(cls, v: Any, info: Any) -> Any:
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"{info.field_name} 必填")
        return v

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        url_pattern = re.compile(r'^https?://[\w\-]+(\.[\w\-]+)+([\w\-.,@?^=%&:/~+#]*[\w\-@?^=%&/~+#])?$')
        if not url_pattern.match(v):
            raise ValueError("URL格式无效")
        return v


def check_rate_limit(client_ip: str) -> bool:
    current_time = time.time()
    if client_ip not in rate_limit_store:
        rate_limit_store[client_ip] = []
    rate_limit_store[client_ip] = [t for t in rate_limit_store[client_ip] if current_time - t < RATE_LIMIT_WINDOW]
    if len(rate_limit_store[client_ip]) >= RATE_LIMIT:
        return False
    rate_limit_store[client_ip].append(current_time)
    return True


def sanitize_filename(filename: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', '_', filename)


# ============================================================
#  企业微信 access_token 管理（Redis 缓存）
# ============================================================

async def get_wecom_access_token() -> str:
    cached_token = await _get_cached_token()
    if cached_token:
        return cached_token

    corp_id = os.getenv("WECOM_CORP_ID")
    secret = os.getenv("WECOM_SECRET")

    if not corp_id or not secret:
        raise RuntimeError("环境变量 WECOM_CORP_ID 或 WECOM_SECRET 未配置，请检查 .env 文件")

    async with httpx.AsyncClient() as client:
        resp = await client.get(WECOM_TOKEN_URL, params={
            "corpid": corp_id,
            "corpsecret": secret,
        })
        data = resp.json()

    if data.get("errcode") != 0:
        raise RuntimeError(f"获取企业微信 access_token 失败: {data.get('errmsg')}")

    access_token = data["access_token"]
    expires_in = data.get("expires_in", 7200)

    cache_ttl = max(expires_in - WECOM_TOKEN_REFRESH_AHEAD, 60)
    await _set_cached_token(access_token, cache_ttl)

    logger.info(f"[WeCom] access_token 已获取并缓存, TTL={cache_ttl}s")
    return access_token


async def _get_cached_token() -> Optional[str]:
    if not redis_pool:
        return None
    import redis.asyncio as redis
    client = redis.Redis(connection_pool=redis_pool, decode_responses=True)
    try:
        return await client.get(WECOM_TOKEN_CACHE_KEY)
    except Exception as e:
        logger.warning(f"[WeCom] Redis 读取 access_token 失败: {e}")
        return None
    finally:
        await client.aclose()


async def _set_cached_token(token: str, ttl: int) -> None:
    if not redis_pool:
        return
    import redis.asyncio as redis
    client = redis.Redis(connection_pool=redis_pool, decode_responses=True)
    try:
        await client.setex(WECOM_TOKEN_CACHE_KEY, ttl, token)
    except Exception as e:
        logger.warning(f"[WeCom] Redis 写入 access_token 失败: {e}")
    finally:
        await client.aclose()


# ============================================================
#  企业微信消息加解密工具函数
# ============================================================

def _verify_signature(signature: str, timestamp: str, nonce: str, content: str, token: str) -> bool:
    params = sorted([token, timestamp, nonce, content])
    sha1 = hashlib.sha1("".join(params).encode("utf-8")).hexdigest()
    return sha1 == signature


def _aes_decrypt(cipher_text: bytes, encoding_aes_key: str) -> bytes:
    aes_key = base64.b64decode(encoding_aes_key + "=")
    iv = aes_key[:16]
    cipher = AES.new(aes_key, AES.MODE_CBC, iv)
    plain_text = cipher.decrypt(cipher_text)
    pad_len = plain_text[-1]
    plain_text = plain_text[:-pad_len]
    return plain_text


def _decrypt_echostr(echostr: str, encoding_aes_key: str) -> str:
    cipher_text = base64.b64decode(echostr)
    plain_text = _aes_decrypt(cipher_text, encoding_aes_key)
    msg_len = struct.unpack(">I", plain_text[16:20])[0]
    msg = plain_text[20:20 + msg_len].decode("utf-8")
    received_corpid = plain_text[20 + msg_len:].decode("utf-8")

    expected_corpid = os.getenv("WECOM_CORP_ID", "")
    if received_corpid != expected_corpid:
        raise ValueError(f"CorpID 不匹配: expected={expected_corpid}, received={received_corpid}")

    return msg


def _decrypt_message(encrypt_xml: str, encoding_aes_key: str) -> str:
    root = ET.fromstring(encrypt_xml)
    encrypt_text = root.find("Encrypt").text
    cipher_text = base64.b64decode(encrypt_text)
    plain_text = _aes_decrypt(cipher_text, encoding_aes_key)
    msg_len = struct.unpack(">I", plain_text[16:20])[0]
    return plain_text[20:20 + msg_len].decode("utf-8")


def _parse_message_xml(xml_str: str) -> dict:
    root = ET.fromstring(xml_str)
    msg = {}
    for child in root:
        msg[child.tag] = child.text
    return msg


# ============================================================
#  企业微信回调接口
# ============================================================

@router.get('/callback', summary='企业微信回调URL验证')
async def verify_callback(
    msg_signature: str = Query(..., description="签名"),
    timestamp: str = Query(..., description="时间戳"),
    nonce: str = Query(..., description="随机数"),
    echostr: str = Query(..., description="加密的随机字符串"),
):
    token = os.getenv("WECOM_TOKEN", "")
    encoding_aes_key = os.getenv("WECOM_ENCODING_AES_KEY", "")

    if not token or not encoding_aes_key:
        logger.error("[WeCom] 回调验证失败: 缺少 WECOM_TOKEN 或 WECOM_ENCODING_AES_KEY")
        return PlainTextResponse("配置错误: 缺少 Token 或 EncodingAESKey", status_code=500)

    try:
        if not _verify_signature(msg_signature, timestamp, nonce, echostr, token):
            logger.error("[WeCom] 回调验证失败: 签名不匹配")
            return PlainTextResponse("签名验证失败", status_code=403)

        decrypted = _decrypt_echostr(echostr, encoding_aes_key)
        logger.info("[WeCom] 回调 URL 验证成功")
        return PlainTextResponse(decrypted)

    except Exception as e:
        logger.error(f"[WeCom] 回调验证异常: {str(e)}")
        return PlainTextResponse(f"验证失败: {str(e)}", status_code=500)


@router.post('/callback', summary='接收企业微信消息推送')
async def receive_message(request: Request):
    params = request.query_params
    msg_signature = params.get("msg_signature", "")
    timestamp = params.get("timestamp", "")
    nonce = params.get("nonce", "")

    token = os.getenv("WECOM_TOKEN", "")
    encoding_aes_key = os.getenv("WECOM_ENCODING_AES_KEY", "")
    corp_id = os.getenv("WECOM_CORP_ID", "")

    if not token or not encoding_aes_key:
        logger.error("[WeCom] 消息接收失败: 缺少配置")
        return PlainTextResponse("配置错误", status_code=500)

    xml_body = await request.body()
    xml_str = xml_body.decode("utf-8")

    try:
        root = ET.fromstring(xml_str)
        encrypt_text = root.find("Encrypt").text

        if not _verify_signature(msg_signature, timestamp, nonce, encrypt_text, token):
            logger.error("[WeCom] 消息签名验证失败")
            return PlainTextResponse("签名验证失败", status_code=403)

        decrypted_xml = _decrypt_message(xml_str, encoding_aes_key)
        msg = _parse_message_xml(decrypted_xml)
        msg_type = msg.get("MsgType", "")

        logger.info(f"[WeCom] 收到消息: MsgType={msg_type}, From={msg.get('FromUserName')}")

        if msg_type == "link":
            video_url = msg.get("Url", "")
            user_id = msg.get("FromUserName", "")
            title = msg.get("Title", "视频链接")

            if video_url:
                logger.info(f"[WeCom] 检测到视频链接: {video_url}")
                asyncio.create_task(_reply_with_miniprogram_card(user_id, video_url, title))

        return PlainTextResponse("")

    except Exception as e:
        logger.error(f"[WeCom] 处理消息异常: {str(e)}")
        return PlainTextResponse("")


# ============================================================
#  发送小程序卡片回复
# ============================================================

async def _reply_with_miniprogram_card(touser: str, video_url: str, title: str = "视频链接") -> None:
    try:
        access_token = await get_wecom_access_token()
        app_id = os.getenv("APPID", "wx5b74bb5779e91393")
        page_path = os.getenv("WECOM_MINIPROGRAM_PAGE", "pages/wecom/download")
        encoded_url = urllib.parse.quote(video_url, safe="")

        payload = {
            "touser": touser,
            "msgtype": "miniprogram_notice",
            "agentid": int(os.getenv("WECOM_AGENT_ID", "0")),
            "miniprogram_notice": {
                "appid": app_id,
                "page": f"{page_path}?url={encoded_url}",
                "title": "视频处理中",
                "description": f"点击查看 {title[:20]} 的下载进度",
                "emphasis_first_item": True,
                "content_item": [
                    {
                        "key": "视频链接",
                        "value": video_url[:30] + ("..." if len(video_url) > 30 else "")
                    },
                    {
                        "key": "状态",
                        "value": "点击卡片开始下载"
                    }
                ]
            }
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                WECOM_SEND_URL,
                params={"access_token": access_token},
                json=payload,
            )
            result = resp.json()

        if result.get("errcode") == 0:
            logger.info(f"[WeCom] 小程序卡片已发送给 {touser}")
        else:
            logger.error(f"[WeCom] 发送卡片失败: {result}")

    except Exception as e:
        logger.error(f"[WeCom] 发送小程序卡片异常: {e}")


# ============================================================
#  视频下载接口（已有，保持不变）
# ============================================================

@router.post('/save_video', summary='企业微信 - 保存视频到服务器')
async def wecom_save_video(request: Request, req: WecomSaveVideoRequest):
    client_ip = request.client.host
    user_id = req.user_id
    video_url = req.url

    logger.info(f"[WeCom] 收到来自用户 {user_id} 的视频保存请求: {video_url}")

    rate_limit_key = f"wecom:{user_id}:{client_ip}"
    if not check_rate_limit(rate_limit_key):
        logger.warning(f"[WeCom] 速率限制触发: {rate_limit_key}")
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")

    try:
        logger.info("[WeCom] 正在解析视频信息...")
        video_info = await asyncio.to_thread(extract_video_info, video_url)
        video_title = video_info.get("title", f"video_{int(time.time())}")
        logger.info(f"[WeCom] 视频标题: {video_title}")

        user_dir = os.path.join(DOWNLOADS_DIR, sanitize_filename(user_id))
        os.makedirs(user_dir, exist_ok=True)

        safe_title = sanitize_filename(video_title)
        unique_id = str(uuid.uuid4())[:8]
        output_template = os.path.join(user_dir, f"{safe_title}_{unique_id}.%(ext)s")

        logger.info(f"[WeCom] 开始下载视频, 保存到: {user_dir}")
        start_time = time.time()
        downloaded_file = await asyncio.to_thread(
            download_video, video_url, output_template
        )
        elapsed = time.time() - start_time
        logger.info(f"[WeCom] 视频下载完成, 耗时 {elapsed:.1f} 秒")

        if not downloaded_file or not os.path.exists(downloaded_file):
            raise HTTPException(status_code=500, detail="视频下载失败，文件不存在")

        file_size = os.path.getsize(downloaded_file)
        file_name = os.path.basename(downloaded_file)

        public_url = f"/downloads/{sanitize_filename(user_id)}/{file_name}"

        result = {
            "video_title": video_title,
            "file_name": file_name,
            "file_size": file_size,
            "file_size_display": format_file_size(file_size),
            "local_path": downloaded_file,
            "download_url": public_url,
            "elapsed_seconds": round(elapsed, 1),
        }

        return response(data=result, code=200, msg="视频保存成功")

    except ValueError as e:
        logger.error(f"[WeCom] 值错误: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"[WeCom] 下载错误: {str(e)}")
        raise HTTPException(status_code=400, detail=f"视频下载失败: {str(e)}")
    except Exception as e:
        logger.error(f"[WeCom] 服务器错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.get('/download_list', summary='企业微信 - 获取用户下载记录')
async def get_download_list(user_id: str):
    if not user_id or not user_id.strip():
        raise HTTPException(status_code=400, detail="用户ID不能为空")

    user_dir = os.path.join(DOWNLOADS_DIR, sanitize_filename(user_id))
    if not os.path.exists(user_dir):
        return response(data=[], code=200, msg="暂无下载记录")

    files = []
    for f in os.listdir(user_dir):
        fpath = os.path.join(user_dir, f)
        if os.path.isfile(fpath):
            files.append({
                "file_name": f,
                "file_size": os.path.getsize(fpath),
                "file_size_display": format_file_size(os.path.getsize(fpath)),
                "download_url": f"/downloads/{sanitize_filename(user_id)}/{f}",
                "modified_time": os.path.getmtime(fpath),
            })

    files.sort(key=lambda x: x["modified_time"], reverse=True)

    return response(data=files, code=200, msg="获取成功")


# ============================================================
#  视频下载工具函数
# ============================================================

def _resolve_cookiefile() -> str | None:
    from pathlib import Path
    project_root = Path(__file__).resolve().parent.parent
    candidates: list[Path] = []
    configured = os.getenv("COOKIE_FILE", "cookies.txt")
    configured_path = Path(configured)
    if not configured_path.is_absolute():
        configured_path = project_root / configured_path
    candidates.append(configured_path)
    for fallback_name in ("cookies.txt.dan", "cookies.txt"):
        fallback_path = project_root / fallback_name
        if fallback_path not in candidates:
            candidates.append(fallback_path)
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            logger.info(f"[WeCom] 使用 cookie 文件: {candidate}")
            return str(candidate)
    logger.warning("[WeCom] 未找到 cookie 文件，可能无法下载需要登录的视频")
    return None


def extract_video_info(video_url: str) -> dict:
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'retries': 3,
        'fragment_retries': 3,
    }

    cookiefile = _resolve_cookiefile()
    if cookiefile:
        ydl_opts['cookiefile'] = cookiefile
        logger.info(f"[WeCom] 使用 cookie 文件: {cookiefile}")
    else:
        logger.warning("[WeCom] 未找到 cookie 文件，可能无法下载需要登录的视频")

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=False)
        if not info:
            raise ValueError("无法提取视频信息")
        return {
            "title": info.get('title', 'video'),
            "thumbnail": info.get('thumbnail', ''),
            "duration": info.get('duration', 0),
        }


def download_video(video_url: str, output_template: str) -> str:
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'retries': 5,
        'fragment_retries': 5,
    }

    cookiefile = _resolve_cookiefile()
    if cookiefile:
        ydl_opts['cookiefile'] = cookiefile

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=True)
        if not info:
            raise ValueError("视频下载失败：无法提取信息")

        file_path = ydl.prepare_filename(info)
        for ext in ['.mp4', '.webm', '.mkv', '.flv']:
            test_path = file_path.replace('.%(ext)s', ext)
            if os.path.exists(test_path):
                return test_path
            if ext in file_path:
                test_path2 = file_path
                if os.path.exists(test_path2):
                    return test_path2

        base = output_template.replace('.%(ext)s', '')
        for ext in ['.mp4', '.webm', '.mkv', '.flv']:
            test = base + ext
            if os.path.exists(test):
                return test

        raise ValueError("无法定位下载后的视频文件")


def format_file_size(size_bytes: int) -> str:
    if size_bytes == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(units) - 1:
        size_bytes /= 1024
        i += 1
    return f"{size_bytes:.1f} {units[i]}"