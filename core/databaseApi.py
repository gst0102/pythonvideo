
import redis.asyncio as redis
from fastapi import FastAPI, Depends, Request
from typing import AsyncGenerator
import httpx,os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


# 微信云开发环境
evn = os.getenv('evn')
appid = os.getenv('APPID')
secret = os.getenv('SECRET')
grant_type='client_credential'
async def get_access_token(redis_client: redis.Redis):
    cached_token = await redis_client.get("access_token")
    if cached_token:
        print("✅ 命中缓存，直接返回 Redis 中的 Token")
        return {"message": "从缓存获取成功", "token": cached_token, "source": "redis"}

    print("🌐 缓存未命中，正在请求微信服务器...")
    tokenUrl = f'https://api.weixin.qq.com/cgi-bin/token?appid={appid}&secret={secret}&grant_type={grant_type}'
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(tokenUrl)
            data = response.json()
            access_token = data.get("access_token")
            if not access_token:
                print(f"❌ 获取 access_token 失败: {data}")
                return {"message": "获取Token失败", "token": None, "source": "wechat"}
            await redis_client.set("access_token", access_token, ex=7200)
            print("✅ 已获取新 Token 并缓存到 Redis")
            return {"message": "从微信获取成功", "token": access_token, "source": "wechat"}
    except Exception as e:
        print(f"❌ 请求微信服务器异常: {e}")
        return {"message": f"请求异常: {str(e)}", "token": None, "source": "error"}
    
# 1. 定义全局变量存储连接池（通过 app.state 管理）
# 注意：这里只定义类型，实际实例在 lifespan 中创建
redis_pool: redis.ConnectionPool | None = None
async def init_redis_pool():
    """初始化 Redis 连接池"""
    global redis_pool
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    print(f"🔴 正在初始化 Redis 连接池: {redis_url}")
    redis_pool = redis.ConnectionPool.from_url(redis_url, decode_responses=True, encoding="utf-8")

async def close_redis_pool():
    """关闭 Redis 连接池"""
    global redis_pool
    if redis_pool:
        print("🔴 正在关闭 Redis 连接池")
        await redis_pool.disconnect()
        redis_pool = None

# 2. 定义依赖注入函数 (核心！)
# 这个函数会在中间件和路由中被调用
async def get_redis(request: Request) -> AsyncGenerator[redis.Redis, None]:
    """
    获取 Redis 客户端实例。
    从 app.state 获取连接池，并为当前请求创建一个客户端。
    """
    # 从应用状态中获取连接池
    pool = request.app.state.redis_pool
    
    # 创建一个 Redis 客户端（轻量级，内部复用连接池）
    client = redis.Redis(connection_pool=pool, decode_responses=True)
    
    
    try:
        yield client
    finally:
        # 请求结束后关闭客户端（归还连接到池）
        await client.aclose()

# 定义一个类型别名，方便在代码中提示
RedisClient = redis.Redis

# # 数据库插入语句
# async addRecord(user_data: dict):

#     # 构造调用云函数所需的参数
#     cloud_function_event = {
#         "action": "add",
#         "collectionName": "users", # 数据库集合名称
#         "data": user_data
#     }

#     async with httpx.AsyncClient() as client:
#         try:
#             # 向云函数的 HTTP 地址 发送 POST 请求
#             response = await client.post()