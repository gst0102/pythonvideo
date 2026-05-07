# controllers/weixinpay.py

from fastapi import Request, HTTPException, APIRouter, Depends
from pydantic import BaseModel
import json
import os
import httpx
import random
import string
import time
import datetime
import base64
import logging
from typing import Optional
from decimal import Decimal

from core.certKey import verify_signature
from core.wepay import WeChatPayV3
from core.databaseApi import get_redis, RedisClient, get_access_token
from dotenv import load_dotenv
from Crypto.Cipher import AES

# 配置日志
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wxpay", tags=["微信支付相关接口"])

# 加载环境变量
load_dotenv()

# 微信云开发环境
evn = os.getenv('evn')
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 初始化配置	

config = {
    "mch_id": os.getenv('mchid'),
    "app_id": os.getenv('APPID'),
    "api_v3_key": os.getenv('APIv3'),
    "private_key_path": os.path.join(BASE_DIR, 'certs', 'apiclient_key.pem'),
    "serial_no": os.getenv('serial_no'),
    "notify_url": os.getenv('NOTIFY_URL', 'http://gf6f3987.natappfree.cc/wxpay/api/pay/notify'),
}

wx_pay = WeChatPayV3(**config)


# ==================== 请求模型 ====================
class OrderRequest(BaseModel):
    openid: str
    total: float  # 单位：分
    description: str


class OrderCreateRequest(BaseModel):
    userId: str
    period: str
    price: float  # 单位：元
    description: str
    openid: str


# ==================== 辅助函数 ====================
def generate_out_trade_no() -> str:
    """生成唯一商户订单号"""
    return str(int(time.time())) + ''.join(random.choices(string.digits, k=6))


def convert_yuan_to_fen(price: float) -> int:
    """将元转换为分，使用 Decimal 避免浮点精度问题"""
    return int(Decimal(str(price)) * 100)


def convert_fen_to_yuan(price_in_fen: int) -> float:
    """将分转换为元"""
    return float(round(Decimal(str(price_in_fen)) / 100, 2))


# ==================== 核心：创建订单接口 ====================
@router.post("/api/newcreateOrder")
async def create_ordervalue(data: OrderCreateRequest, redis: RedisClient = Depends(get_redis)):
    """创建订单并调用微信支付"""
    
    # 转换金额（元 -> 分）用于微信支付
    price_in_fen = convert_yuan_to_fen(data.price)
    
    # 获取微信 access_token
    token_result = await get_access_token(redis_client=redis)
    access_token_str = token_result.get("token")
    if not access_token_str:
        return {"code": 500, "msg": "获取Token失败"}

    # 拼接调用云函数的 URL
    cloud_func_url = f"https://api.weixin.qq.com/tcb/invokecloudfunction?access_token={access_token_str}&env={evn}&name=database"
    
    # 生成商户订单号
    out_trade_no = generate_out_trade_no()
    now_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 数据库存储元

    price_in_yuan = float(convert_fen_to_yuan(price_in_fen))
    # 准备写入云数据库的订单数据
    order_data = {
        "user_id": data.userId,
        "price": price_in_yuan,
        "paymentStatus": "001",  # 001 代表未支付
        "period": data.period,
        "out_trade_no": out_trade_no,
        "create_time": now_time,
        "update_time": now_time,
        "transaction_id": None,
        "pay_time": None,
        "expire_time": None,
        "description": data.description
    }

    # 调用云函数将订单存入云数据库
    doc_id = None
    
    async with httpx.AsyncClient() as client:
        db_res = await client.post(cloud_func_url, json={
            "action": "add",
            "collectionName": "order-info",
            "data": order_data
        })
        db_result = db_res.json()
        logger.info(f"数据库写入结果: {db_result}")
        
        # 从返回结果中提取 _id
        if db_result.get("success") and db_result.get("data", {}).get("_id"):
            doc_id = db_result["data"]["_id"]
            logger.info(f"订单创建成功，文档ID: {doc_id}")

    # 调用微信统一下单（传入分）
    try:
        prepay_id = wx_pay.create_jsapi_order(
            description=data.description,
            out_trade_no=out_trade_no,
            total=price_in_fen,
            openid=data.openid,
            notify_url=config.get('notify_url')
        )

        # 生成前端调起支付需要的参数
        pay_params = wx_pay.get_jsapi_params(prepay_id)
        logger.info(f'支付参数生成成功, prepay_id: {prepay_id}')
        
        return {"code": 200, "msg": "success", "data": pay_params, "doc_id": doc_id}

    except Exception as e:
        logger.error(f"创建订单失败: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


# ==================== 回调相关函数 ====================
def decrypt_aes_256_gcm(ciphertext: str, nonce: str, key: str, associated_data: str) -> str:
    """解密微信支付回调的 AES-256-GCM 加密数据"""
    try:
        key_bytes = key.encode('utf-8')
        nonce_bytes = nonce.encode('utf-8')
        ciphertext_bytes = base64.b64decode(ciphertext)
        associated_data_bytes = associated_data.encode('utf-8')

        cipher = AES.new(key_bytes, AES.MODE_GCM, nonce=nonce_bytes)
        cipher.update(associated_data_bytes)

        tag = ciphertext_bytes[-16:]
        encrypted_data = ciphertext_bytes[:-16]

        decrypted_data = cipher.decrypt_and_verify(encrypted_data, tag)
        return decrypted_data.decode('utf-8')

    except Exception as e:
        logger.error(f"解密失败: {str(e)}")
        raise


async def update_order_payment_status(
    out_trade_no: str, 
    transaction_id: str, 
    total_fee_in_fen: int, 
    success_time: str,
    openid: str,
    redis_client: RedisClient
):
    """更新订单支付状态"""
    try:
        # 1. 获取 access_token（使用传入的 redis_client，它在 main.py 中已配置）
        token_result = await get_access_token(redis_client=redis_client)
        access_token_str = token_result.get("token")
        if not access_token_str:
            logger.error("获取Token失败，无法更新订单状态")
            return False

        # 云函数 URL
        cloud_func_url = f"https://api.weixin.qq.com/tcb/invokecloudfunction?access_token={access_token_str}&env={evn}&name=database"
        
        # 更新订单数据
        update_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 将分转换为元存储到数据库
        total_fee_in_yuan = float(convert_fen_to_yuan(total_fee_in_fen))
        
        # 使用 filter 更新
        async with httpx.AsyncClient() as client:
            update_res = await client.post(cloud_func_url, json={
                "action": "update",
                "collectionName": "order-info",
                "filter": {
                    "out_trade_no": out_trade_no,  # ← 必须保留！精确定位订单
                    "_openid": openid               # ← 权限验证
                },
                "data": {
                    "paymentStatus": "002",
                    "transaction_id": transaction_id,
                    "pay_time": success_time,
                    "update_time": update_time,
                    "price": total_fee_in_yuan
                }
            })
            result = update_res.json()
            logger.info(f"更新订单状态结果: {result}")
            print("更新订单状态结果result",result)
            
            if result.get("success"):
                logger.info(f"✅ 订单 {out_trade_no} 支付状态更新成功")
                return True
            else:
                logger.error(f"❌ 订单更新失败: {result.get('error')}")
                return False
            
    except Exception as e:
        logger.error(f"更新订单状态失败: {str(e)}", exc_info=True)
        return False


# ==================== 回调接口 ====================
@router.post("/api/pay/notify")
async def pay_notify(request: Request):
    """处理微信支付回调"""
    logger.info("\n" + "🔔" * 30)
    logger.info("微信支付回调被触发！")
    logger.info(f"时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("🔔" * 30)
    
    try:
        # 1. 获取请求体
        body = await request.body()
        body_str = body.decode('utf-8')
        logger.info(f"📦 原始请求体:\n{body_str}")
        
        # 2. 获取请求头
        headers = request.headers
        timestamp = headers.get("wechatpay-timestamp")
        nonce = headers.get("wechatpay-nonce")
        signature = headers.get("wechatpay-signature")
        serial = headers.get("wechatpay-serial")
        
        logger.info(f"📋 请求头: timestamp={timestamp}, nonce={nonce}, serial={serial}")
        logger.info(f"📋 signature={signature[:50]}...")
        # 3. 验证必要参数
        if not all([timestamp, nonce, signature, serial]):
            logger.error("❌ 缺少必要参数")
            return {"code": "FAIL", "message": "缺少必要参数"}
        
        # 4. 构造待签名字符串并验证签名
        sign_str = f"{timestamp}\n{nonce}\n{body_str}\n"
        is_valid = await verify_signature(sign_str, signature, serial)
        if not is_valid:
            logger.error("❌ 签名验证失败")
            return {"code": "FAIL", "message": "签名验证失败"}
        logger.info("✅ 签名验证成功")
        
        # 5. 解析通知数据
        notify_data = json.loads(body_str)
        event_type = notify_data.get("event_type")
        logger.info(f"📌 事件类型: {event_type}")
        
        # 6. 只处理支付成功事件
        if event_type != "TRANSACTION.SUCCESS":
            logger.info(f"⏭️ 跳过非支付成功事件: {event_type}")
            return {"code": "SUCCESS", "message": "事件类型不处理"}
        
        # 7. 解密 resource 数据
        resource = notify_data.get("resource", {})
        ciphertext = resource.get("ciphertext")
        nonce_decrypt = resource.get("nonce")
        associated_data = resource.get("associated_data", "")
        
        if not all([ciphertext, nonce_decrypt]):
            logger.error("❌ 缺少解密数据")
            return {"code": "FAIL", "message": "缺少解密数据"}
        
        # 解密
        api_v3_key = wx_pay.api_v3_key
        decrypted_data = decrypt_aes_256_gcm(
            ciphertext, nonce_decrypt, api_v3_key, associated_data
        )
        print("订单特殊信息请求头ciphertext",decrypted_data)
        # 8. 解析业务数据
        trade_data = json.loads(decrypted_data)
        trade_state = trade_data.get('trade_state')
        logger.info(f"💰 支付状态: {trade_state}")
        logger.debug(f"💰 完整支付数据: {json.dumps(trade_data, ensure_ascii=False, indent=2)}")
        
        # 9. 只处理支付成功状态
        if trade_state != 'SUCCESS':
            logger.info(f"❌ 订单状态不是 SUCCESS: {trade_state}")
            return {"code": "SUCCESS", "message": f"订单状态: {trade_state}"}
        
        # 10. 提取订单信息
        out_trade_no = trade_data.get('out_trade_no')
        transaction_id = trade_data.get('transaction_id')
        amount_info = trade_data.get('amount', {})
        total_fee_in_fen = amount_info.get('total')
        success_time = trade_data.get('success_time')
        # 🔥 获取 payer 信息（包含 openid）
        payer_info = trade_data.get('payer', {})
        openid = payer_info.get('openid', '')
        
        logger.info(f"📝 订单信息: out_trade_no={out_trade_no}, transaction_id={transaction_id}")
        logger.info(f"📝 支付金额: {total_fee_in_fen}分 = {convert_fen_to_yuan(total_fee_in_fen)}元")
        logger.info(f"📝 支付时间: {success_time}")
        
        if not out_trade_no:
            logger.error("❌ 缺少订单号")
            return {"code": "FAIL", "message": "缺少订单号"}
        
        # 11. 使用 main.py 中管理的 Redis 连接池创建客户端
        import redis.asyncio as redis_async
        pool = request.app.state.redis_pool
        redis_client = redis_async.Redis(connection_pool=pool, decode_responses=True)
        
        try:
            # 更新数据库中的订单状态
            update_success = await update_order_payment_status(
                out_trade_no, transaction_id, total_fee_in_fen, success_time,openid, redis_client
            )
            
            if update_success:
                logger.info("✅ 订单状态更新成功")
                # 缓存订单状态到 Redis
                await redis_client.setex(
                    f"order:{out_trade_no}:status",
                    3600,
                    "paid"
                )
                await redis_client.setex(
                    f"order:{out_trade_no}:transaction",
                    3600,
                    json.dumps({
                        "transaction_id": transaction_id,
                        "paid_time": success_time,
                        "amount": convert_fen_to_yuan(total_fee_in_fen)
                    })
                )
                logger.info(f"✅ Redis 缓存更新成功: order:{out_trade_no}")
            else:
                logger.error("❌ 订单状态更新失败")
        finally:
            # 重要：释放从连接池获取的 Redis 连接
            await redis_client.aclose()
        
        logger.info("✅ 回调处理完成")
        return {"code": "SUCCESS", "message": "成功"}
        
    except Exception as e:
        logger.error(f"❌ 回调处理失败: {str(e)}", exc_info=True)
        # 即使处理失败，也要返回 SUCCESS，避免微信重复回调
        return {"code": "SUCCESS", "message": "处理完成"}


# ==================== 查询订单接口（调试用） ====================
@router.get("/api/queryOrder")
async def query_order(out_trade_no: str, redis: RedisClient = Depends(get_redis)):
    """查询订单状态（调试用）"""
    try:
        # 获取 access_token
        token_result = await get_access_token(redis_client=redis)
        access_token_str = token_result.get("token")
        if not access_token_str:
            return {"code": 500, "msg": "获取Token失败"}

        # 云函数 URL
        cloud_func_url = f"https://api.weixin.qq.com/tcb/invokecloudfunction?access_token={access_token_str}&env={evn}&name=database"
        
        async with httpx.AsyncClient() as client:
            query_res = await client.post(cloud_func_url, json={
                "action": "get",
                "collectionName": "order-info",
                "query": {"out_trade_no": out_trade_no}
            })
            result = query_res.json()
            logger.info(f"查询订单结果: {result}")
            
            if result.get("success"):
                data = result.get("data", {}).get("data", [])
                if data:
                    return {"code": 200, "msg": "success", "data": data[0]}
                else:
                    return {"code": 404, "msg": "订单不存在"}
            else:
                return {"code": 500, "msg": result.get("error")}
                
    except Exception as e:
        logger.error(f"查询订单失败: {str(e)}")
        return {"code": 500, "msg": str(e)}


# ==================== 证书状态检查（调试用） ====================
@router.get("/cert-status")
async def get_cert_status():
    """检查证书管理器状态（调试用）"""
    from core.certKey import get_cert_manager
    cert_manager = get_cert_manager()
    
    status = {
        "cert_manager_initialized": cert_manager is not None,
        "redis_available": False,
        "memory_cache_count": 0,
        "memory_cache_keys": [],
        "wechatpay_public_key_loaded": False,
        "merchant_cert_exists": os.path.exists(os.path.join(BASE_DIR, "certs", "apiclient_cert.pem")),
        "merchant_private_key_exists": os.path.exists(os.path.join(BASE_DIR, "certs", "apiclient_key.pem")),
        "wechatpay_public_key_exists": os.path.exists(os.path.join(BASE_DIR, "certs", "pub_key.pem")),  # ← 改这里
    }
    
    if cert_manager:
        memory_cache = getattr(cert_manager, '_memory_cache', {})
        status["memory_cache_count"] = len(memory_cache)
        status["memory_cache_keys"] = list(memory_cache.keys())
        # 检查微信支付公钥是否已加载到内存
        status["wechatpay_public_key_loaded"] = getattr(cert_manager, '_wechatpay_public_key', None) is not None
        try:
            # 使用 main.py 中的 Redis 连接池
            if hasattr(cert_manager, 'redis_pool') and cert_manager.redis_pool:
                import redis.asyncio as redis_async
                redis_client = redis_async.Redis(connection_pool=cert_manager.redis_pool)
                await redis_client.ping()
                status["redis_available"] = True
                
                # 检查 Redis 中的证书缓存
                keys = []
                try:
                    redis_keys = await redis_client.keys("wechat:cert:*")
                    keys = [k.decode() if isinstance(k, bytes) else k for k in redis_keys]
                except Exception:
                    pass
                
                status["redis_cache_keys"] = keys
                await redis_client.aclose()
        except Exception as e:
            status["redis_error"] = str(e)
    
    return status