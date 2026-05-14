from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import Optional, Any, Dict
import httpx
import os
from dotenv import load_dotenv
from core.response import response
from core.databaseApi import get_access_token, RedisClient

load_dotenv()

ENV_ID = os.getenv('evn')
CLOUD_FUNCTION_NAME = 'admin-api'
CLOUD_UPLOAD_FUNCTION = 'admin-upload'

router = APIRouter(prefix="/pc", tags=["PC管理端接口"])


class AdminRequest(BaseModel):
    action: str
    data: Optional[Dict[str, Any]] = {}


async def call_cloud_function(action: str, data: Dict[str, Any], redis_client: RedisClient) -> Dict[str, Any]:
    token_result = await get_access_token(redis_client=redis_client)
    access_token = token_result.get("token")

    if not access_token:
        return {"code": 500, "msg": "获取微信 access_token 失败"}

    invoke_url = (
        f"https://api.weixin.qq.com/tcb/invokecloudfunction"
        f"?access_token={access_token}"
        f"&env={ENV_ID}"
        f"&name={CLOUD_FUNCTION_NAME}"
    )

    cloud_event = {"action": action, "data": data}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(invoke_url, json=cloud_event)
        result = resp.json()

    if result.get("errcode") and result.get("errcode") != 0:
        return {"code": result["errcode"], "msg": result.get("errmsg", "云函数调用失败"), "data": None}

    inner_result = result.get("resp_data", result)
    if isinstance(inner_result, str):
        import json
        try:
            inner_result = json.loads(inner_result)
        except (json.JSONDecodeError, TypeError):
            pass

    if isinstance(inner_result, dict) and "code" in inner_result and inner_result["code"] == 200:
        return {"code": 200, "msg": "SUCCESS", "data": inner_result.get("data")}
    elif isinstance(inner_result, dict) and "code" in inner_result and inner_result["code"] == 0:
        return {"code": 200, "msg": "SUCCESS", "data": inner_result.get("data")}

    return {"code": 200, "msg": "SUCCESS", "data": inner_result}


@router.post("/call", summary="统一管理端云函数调用")
async def pc_call(req: AdminRequest, request: Request):
    redis_client = await request.app.state.redis_pool.get_redis() if hasattr(request.app.state.redis_pool, 'get_redis') else None
    if redis_client is None:
        from core.databaseApi import get_redis
        redis_gen = get_redis(request)
        redis_client = await redis_gen.__anext__()

    try:
        result = await call_cloud_function(req.action, req.data or {}, redis_client)
        return response(data=result.get("data"), code=result.get("code", 200), msg=result.get("msg", "SUCCESS"))
    finally:
        if redis_client:
            try:
                await redis_client.aclose()
            except Exception:
                pass


@router.post("/dashboard", summary="获取仪表盘统计")
async def get_dashboard_stats(request: Request):
    result = await _call_with_redis(request, 'getDashboardStats', {})
    return response(data=result.get("data"), code=result.get("code", 200), msg=result.get("msg", "SUCCESS"))


@router.post("/user-growth", summary="用户增长统计")
async def get_user_growth_stats(request: Request, days: int = 7):
    result = await _call_with_redis(request, 'getUserGrowthStats', {"days": days})
    return response(data=result.get("data"), code=result.get("code", 200), msg=result.get("msg", "SUCCESS"))


@router.post("/withdrawal-stats", summary="提现统计")
async def get_withdrawal_stats(request: Request, days: int = 7):
    result = await _call_with_redis(request, 'getWithdrawalStats', {"days": days})
    return response(data=result.get("data"), code=result.get("code", 200), msg=result.get("msg", "SUCCESS"))


class UserListRequest(BaseModel):
    page: int = 1
    pageSize: int = 20
    keyword: Optional[str] = None


@router.post("/user-list", summary="用户列表")
async def get_user_list(req: UserListRequest, request: Request):
    result = await _call_with_redis(request, 'getUserList', req.model_dump(exclude_none=True))
    return response(data=result.get("data"), code=result.get("code", 200), msg=result.get("msg", "SUCCESS"))


@router.post("/user-detail", summary="用户详情")
async def get_user_detail(request: Request, userId: str):
    result = await _call_with_redis(request, 'getUserDetail', {"userId": userId})
    return response(data=result.get("data"), code=result.get("code", 200), msg=result.get("msg", "SUCCESS"))


class ConfigRequest(BaseModel):
    type: str


@router.post("/config", summary="获取配置")
async def get_config(req: ConfigRequest, request: Request):
    result = await _call_with_redis(request, 'getConfig', req.model_dump())
    return response(data=result.get("data"), code=result.get("code", 200), msg=result.get("msg", "SUCCESS"))


@router.post("/config-update", summary="更新配置")
async def update_config(request: Request, configData: Dict[str, Any]):
    result = await _call_with_redis(request, 'updateConfig', configData)
    return response(data=result.get("data"), code=result.get("code", 200), msg=result.get("msg", "SUCCESS"))


@router.post("/withdrawal-list", summary="提现列表")
async def get_withdrawal_list(request: Request, status: Optional[int] = None):
    data = {}
    if status is not None:
        data["status"] = status
    result = await _call_with_redis(request, 'getWithdrawalList', data)
    return response(data=result.get("data"), code=result.get("code", 200), msg=result.get("msg", "SUCCESS"))


class ProcessWithdrawalRequest(BaseModel):
    recordId: str
    action: str
    reason: Optional[str] = None


@router.post("/withdrawal-process", summary="处理提现")
async def process_withdrawal(req: ProcessWithdrawalRequest, request: Request):
    result = await _call_with_redis(request, 'processWithdrawal', req.model_dump(exclude_none=True))
    return response(data=result.get("data"), code=result.get("code", 200), msg=result.get("msg", "SUCCESS"))


@router.post("/chat-messages", summary="聊天消息")
async def get_chat_messages(request: Request, userId: Optional[str] = None):
    data = {}
    if userId:
        data["userId"] = userId
    result = await _call_with_redis(request, 'getChatMessages', data)
    return response(data=result.get("data"), code=result.get("code", 200), msg=result.get("msg", "SUCCESS"))


class SendReplyRequest(BaseModel):
    userId: str
    content: str


@router.post("/chat-reply", summary="发送回复")
async def send_reply(req: SendReplyRequest, request: Request):
    result = await _call_with_redis(request, 'sendReply', req.model_dump())
    return response(data=result.get("data"), code=result.get("code", 200), msg=result.get("msg", "SUCCESS"))


class UploadRequest(BaseModel):
    action: str
    data: Dict[str, Any] = {}


@router.post("/upload", summary="文件上传承接")
async def upload_to_cloud(req: UploadRequest, request: Request):
    from core.databaseApi import get_redis
    redis_gen = get_redis(request)
    redis_client = await redis_gen.__anext__()
    try:
        token_result = await get_access_token(redis_client=redis_client)
        access_token = token_result.get("token")

        if not access_token:
            return response(data=None, code=500, msg="获取微信 access_token 失败")

        invoke_url = (
            f"https://api.weixin.qq.com/tcb/invokecloudfunction"
            f"?access_token={access_token}"
            f"&env={ENV_ID}"
            f"&name={CLOUD_UPLOAD_FUNCTION}"
        )

        cloud_event = {"action": req.action, "data": req.data}

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(invoke_url, json=cloud_event)
            result = resp.json()

        if result.get("errcode") and result.get("errcode") != 0:
            return response(data=None, code=result["errcode"], msg=result.get("errmsg", "上传失败"))

        inner_result = result.get("resp_data", result)
        if isinstance(inner_result, str):
            import json
            try:
                inner_result = json.loads(inner_result)
            except (json.JSONDecodeError, TypeError):
                pass

        return response(data=inner_result, code=200, msg="SUCCESS")
    finally:
        try:
            await redis_client.aclose()
        except Exception:
            pass


async def _call_with_redis(request: Request, action: str, data: Dict[str, Any]) -> Dict[str, Any]:
    from core.databaseApi import get_redis
    redis_gen = get_redis(request)
    redis_client = await redis_gen.__anext__()
    try:
        return await call_cloud_function(action, data, redis_client)
    finally:
        try:
            await redis_client.aclose()
        except Exception:
            pass