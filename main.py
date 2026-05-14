
from fastapi import FastAPI
from core.certKey import init_wechat_cert_manager, init_wechat_cert_manager_async
from core.middleware import gloglobal_middleware,validation_exception_handler
from fastapi.staticfiles import StaticFiles
import os
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from core.databaseApi import init_redis_pool, close_redis_pool
# 用户相关的接口
from controllers.user import router as user_router
# 视频相关的接口
from controllers.video import router as video_router
# 微信支付相关的接口
from controllers.weixinpay import router as weixinpay_router
# 数据库相关接口
from controllers.database import router as database_router
# PC管理端接口
from controllers.pcRouter import router as pc_router
# , init_wechatpay, close_wechatpay
# 生命周期管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 应用启动时
    print('应用启动执行')
    await init_redis_pool() # 初始化 Redis 连接池
    # await init_wechatpay()  # 初始化微信支付
        # 将连接池挂载到 app.state，方便全局访问
    # 从你的 databaseApi 模块导入那个已经初始化好的 pool 实例
    from core.databaseApi import redis_pool 
    # 初始化微信证书管理器（传入 Redis 连接池）- 使用异步版本
    await init_wechat_cert_manager_async(redis_pool)
    # 把实例赋值给 app.state，这样中间件才能用到真正的连接池
    app.state.redis_pool = redis_pool

    yield
    # 应用关闭时
    # await close_wechatpay()  # 关闭微信支付
    await close_redis_pool()
    print('应用关闭执行')

app =  FastAPI(lifespan=lifespan)


# 全局注册中间件
app.middleware('http')(gloglobal_middleware)
# 注册全局参数校验器
app.add_exception_handler(RequestValidationError,validation_exception_handler)
# 3. CORS 跨域配置 (关键！)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# 配置静态文件访问
image_folder = os.path.join(os.getcwd(), "image")
os.makedirs(image_folder, exist_ok=True)
app.mount("/image", StaticFiles(directory=image_folder))
@app.get("/health")
def health_check():
    return {"status": "ok", "message": "服务运行正常"}
# --------------------------接口-------------------------
app.include_router(user_router)
app.include_router(video_router)
app.include_router(weixinpay_router)
app.include_router(database_router)
app.include_router(pc_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app="main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
