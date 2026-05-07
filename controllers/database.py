# main.py
from fastapi import FastAPI, HTTPException,APIRouter, Depends, Request
from pydantic import BaseModel
from typing import Optional
import httpx
import os
import json
from dotenv import load_dotenv
from core.databaseApi import get_redis,RedisClient,get_access_token
import redis.asyncio as redis
# 加载环境变量
load_dotenv()
# 1. 定义全局变量存储连接池（通过 app.state 管理）
# 注意：这里只定义类型，实际实例在 lifespan 中创建
redis_pool: redis.ConnectionPool | None = None


# 微信云开发环境
evn = os.getenv('evn')
appid = os.getenv('APPID')
secret = os.getenv('SECRET')
grant_type='client_credential'
CLOUD_FUNCTION_NAME = "database"      # 你在微信后台部署的云函数名称




router = APIRouter(prefix="/db", tags=["数据库操作"])



class UserQueryRequest(BaseModel):
    user_id: Optional[str] = None
    collection_name: Optional[str] = "user-info"


@router.post("/api/users")
async def call_cloud_function(
    query: Optional[UserQueryRequest] = None,
    redis: RedisClient = Depends(get_redis)
):
    """查询用户信息接口
    
    Args:
        query: 查询参数（可选），如果不传则查询所有用户
    """
    # 1. 拼接 invokeCloudFunction 的接口地址
    ACCESS_TOKEN  = await get_access_token(redis_client=redis)
    access_token_str = ACCESS_TOKEN.get("token") 
    print("ACCESS_TOKEN:", ACCESS_TOKEN)
    CLOUD_FUNCTION_URL = f"https://api.weixin.qq.com/tcb/invokecloudfunction?access_token={access_token_str}&env={evn}&name={CLOUD_FUNCTION_NAME}"
    
    # 2. 构造要传给云函数的参数 (对应云函数里的 event 对象)
    cloud_event = {
        "action": "get",
        "collectionName": query.collection_name if query else "user-info"
    }
    
    # 如果传入了 user_id，则添加查询条件
    if query and query.user_id:
        cloud_event["query"] = {"_id": query.user_id}
    
    # 3. 发起 POST 请求调用云函数
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(CLOUD_FUNCTION_URL, json=cloud_event)
            result = response.json()
            print("云函数返回结果:", result)
            return result
    except Exception as e:
        return {"code": 500, "msg": "请求云函数异常", "error": str(e)}




