# core/middleware.py
from fastapi import Request
from typing import Any
from core.response import response
# from fastapi.responses import StreamingResponse
from fastapi.exceptions import RequestValidationError
import redis.asyncio as redis

# 全局异常处理中间件
async def gloglobal_middleware(request: Request, call_next: Any):
    pool = request.app.state.redis_pool
    r = redis.Redis(connection_pool=pool, decode_responses=True)

    try:
        await r.incr("global_request_count")
    except Exception:
        pass
    finally:
        await r.aclose()

    try:
        responseRes = await call_next(request)
        return responseRes
    except Exception as err:
        return response([], 500, str(err))

# 全局参数校验函数
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    first_error = exc.errors()[0]
    msg = first_error['msg']
    if msg in ['Field required']:
        msg = '缺少必传参数'
    return response(code=422, msg=msg, data=[])
    