# core/middleware.py
from fastapi import Request
from typing import Any
from core.response import response
# from fastapi.responses import StreamingResponse
from fastapi.exceptions import RequestValidationError
import redis.asyncio as redis

# 全局异常处理中间件
async def gloglobal_middleware(request: Request, call_next: Any):
    # 1. 从 app.state 获取连接池 (这是启动时初始化好的单例)
    pool = request.app.state.redis_pool
    
    # 2. 创建一个临时的 Redis 客户端
    # 注意：这里不要 await client.aclose()，因为连接池会管理
    # 但为了安全，建议用完即走，或者只读操作
    r = redis.Redis(connection_pool=pool, decode_responses=True)

    try:
        await r.incr("global_request_count")
    except Exception as e:
        print(f"Redis Error in middleware: {e}")
    try:
        # 调用下一个中间件
        print('进入了中间件')
        responseRes = await call_next(request)
        # 如果是流式响应，直接返回，不做处理
        # if isinstance(response, StreamingResponse):
        #     return response
        # 否则继续处理
        return responseRes
    except Exception as err:
        print('出现错误了')
        # 接受异常
        return response([], 500, str(err))

# 全局参数校验函数
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    first_error = exc.errors()[0]
    msg = first_error['msg']
    if msg in ['Field required']:
        msg = '缺少必传参数'
    return response(code=422, msg=msg, data=[])
    