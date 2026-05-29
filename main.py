
from fastapi import FastAPI
from core.certKey import init_wechat_cert_manager, init_wechat_cert_manager_async
from core.middleware import gloglobal_middleware,validation_exception_handler
from fastapi.staticfiles import StaticFiles
import os
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from core.databaseApi import init_redis_pool, close_redis_pool
# === PostgreSQL 数据库 ===
from models.base import init_db, close_db

# ── Controllers ────────────────────────────────────────────────
# 用户接口（已升级：直接操作 PostgreSQL）
from controllers.user import router as user_router
# 视频接口（保持不变）
from controllers.video import router as video_router
# 微信支付接口（回调已升级：使用 PaymentService）
from controllers.weixinpay import router as weixinpay_router
# 企业微信接口（保持不变）
from controllers.wecom import router as wecom_router

# === 🆕 新增 Controller ===
from controllers.vip import router as vip_router
from controllers.commission import router as commission_router
from controllers.withdrawal import router as withdrawal_router
from controllers.chat import router as chat_router
from controllers.admin import router as admin_router

# === 🆕 番剧订阅 ===
from controllers.anime import router as anime_router

# === 🗑️ 旧版云函数代理（保留兼容，完全迁移后删除）===
from controllers.database import router as database_router
from controllers.pcRouter import router as pc_router


# 生命周期管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── 应用启动时 ──────────────────────────────────────────────────────────────
    print("🚀 应用启动执行")

    # Redis 连接池
    await init_redis_pool()
    from core.databaseApi import redis_pool
    app.state.redis_pool = redis_pool

    # PostgreSQL 数据库（生产环境需要，本地开发可选）
    try:
        await init_db()
        print("✅ PostgreSQL 数据库连接成功")
    except Exception as e:
        print(f"⚠️ PostgreSQL 未连接（本地开发可忽略）: {e}")

    # 微信支付证书管理器
    await init_wechat_cert_manager_async(redis_pool)

    # 番剧数据定时同步（APScheduler）
    try:
        from services.sync_service import create_scheduler, sync_anime_from_external, SYNC_ENABLED
        scheduler = create_scheduler()
        if scheduler:
            scheduler.start()
            app.state.anime_scheduler = scheduler
            print("✅ 番剧定时同步已启动（每15分钟）")
        else:
            print("⏸️ 番剧定时同步已关闭（ANIME_SYNC_ENABLED=false）")
    except Exception as e:
        print(f"⚠️ 番剧同步服务启动失败: {e}")

    yield
    # ── 应用关闭时 ──────────────────────────────────────────
    if hasattr(app.state, "anime_scheduler"):
        app.state.anime_scheduler.shutdown(wait=False)
    await close_db()
    await close_redis_pool()
    print("👋 应用关闭执行")

app =  FastAPI(lifespan=lifespan)


# 全局注册中间件
app.middleware('http')(gloglobal_middleware)
app.add_exception_handler(RequestValidationError,validation_exception_handler)

# CORS 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件
image_folder = os.path.join(os.getcwd(), "image")
os.makedirs(image_folder, exist_ok=True)
app.mount("/image", StaticFiles(directory=image_folder))

downloads_folder = os.path.join(os.getcwd(), "downloads")
os.makedirs(downloads_folder, exist_ok=True)
app.mount("/downloads", StaticFiles(directory=downloads_folder))

# 健康检查
@app.get("/health")
def health_check():
    return {"status": "ok", "message": "服务运行正常"}

# ═══════════════════════════════════════════════════════════════
#  注册路由（新架构）
# ═══════════════════════════════════════════════════════════════

app.include_router(user_router)          # /user
app.include_router(video_router)         # /video（不变）
app.include_router(weixinpay_router)     # /wxpay（回调已升级）
app.include_router(wecom_router)         # /wecom（不变）
app.include_router(vip_router)           # 🆕 /vip
app.include_router(commission_router)    # 🆕 /commission
app.include_router(withdrawal_router)    # 🆕 /withdrawal
app.include_router(chat_router)          # 🆕 /chat
app.include_router(admin_router)         # 🆕 /admin
app.include_router(anime_router)         # 🆕 /anime（番剧订阅）

# === 旧版云函数代理（兼容过渡，完全迁移后删除）===
app.include_router(database_router)      # /db → 云函数代理
app.include_router(pc_router, prefix="/api")  # /api/pc → 云函数代理


# 番剧数据手动同步接口（调试/首次部署用）
@app.get("/admin/sync-anime")
async def manual_sync_anime(type: str = "anime"):
    """手动触发数据同步（type=anime|movie|4k，逗号分隔多个）"""
    try:
        from services.sync_service import sync_anime_from_external
        types = [t.strip() for t in type.split(",") if t.strip()]
        result = await sync_anime_from_external(types)
        return {"code": 0, "message": "同步完成", "data": result}
    except Exception as e:
        return {"code": 500, "message": f"同步失败: {str(e)}"}


if __name__ == "__main__":
    import uvicorn
    import os

    # 请求体大小限制（默认 16MB，natapp 免费版仅 ~1-2MB）
    # 如果你的生产环境前面有 nginx/natapp 等代理，这个值应小于代理的限制
    max_body_mb = int(os.getenv("UVICORN_LIMIT_MAX_BODY_MB", "50"))
    max_body_bytes = max_body_mb * 1024 * 1024

    uvicorn.run(
        app="main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        # 请求体大小限制：超过此值返回 413，而非被代理拦截为 400
        limit_max_requests=None,       # 不限制并发请求数
        limit_concurrency=100,          # 最大并发连接
        timeout_keep_alive=30,          # keep-alive 超时
        h11_max_incomplete_event_size=max_body_bytes,  # h11 协议最大不完整事件大小
    )
