#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FastAPI async example for WeChat Pay v3 SDK
演示如何在 FastAPI 中使用异步版本的微信支付 SDK
"""
import json
import logging
import os
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from core.wxpay import generate_mch_id

from wechatpayv3.async_ import AsyncWeChatPay, WeChatPayType

router = APIRouter(prefix="/wxpay", tags=["微信支付相关接口"])

# 加载环境变量
load_dotenv()

# 配置日志
log_level = os.getenv('LOG_LEVEL', 'INFO')
logging.basicConfig(level=getattr(logging, log_level))
logger = logging.getLogger(__name__)

# 全局 WeChat Pay 实例
wxpay: Optional[AsyncWeChatPay] = None


async def init_wechatpay():
    """初始化微信支付客户端（在应用启动时调用）"""
    global wxpay
    
    # 启动时初始化 WeChat Pay 客户端
    # 从环境变量加载配置
    wechatpay_type_str = os.getenv('WECHATPAY_TYPE', 'NATIVE')
    wechatpay_type_map = {
        'NATIVE': WeChatPayType.NATIVE,
        'JSAPI': WeChatPayType.JSAPI,
        'APP': WeChatPayType.APP,
        'H5': WeChatPayType.H5,
        'MINIPROG': WeChatPayType.MINIPROG
    }
    pub_key_path  = os.getenv('WECHATPAY_PRIVATE_KEY_PATH')
    with open(pub_key_path , mode="r") as f:
        private_key = f.read()

    
    config = {
        'wechatpay_type': wechatpay_type_map.get(wechatpay_type_str, WeChatPayType.JSAPI),
        'mchid': os.getenv('mchid'), # 商户ID
        'private_key':private_key, # 商户证书私钥私钥
        'cert_serial_no': os.getenv('serial_no'), # 商户证书序列号
        'appid': os.getenv('APPID'), # 应用ID（例如微信小程序、公众号..）
        'apiv3_key': os.getenv('APIv3'), # API v3密钥， https://pay.weixin.qq.com/wiki/doc/apiv3/wechatpay/wechatpay3_2.shtml
        'notify_url': "https://www.baidu.com/", # 回调地址，也可以在调用接口的时候覆盖
        'cert_dir': os.getenv('WECHATPAY_CERT_DIR', './certs'), # 证书目录
        'logger': logger,
    }
    
    # 验证必需的配置
    required_fields = ['mchid', 'private_key', 'cert_serial_no', 'appid', 'apiv3_key']
    missing_fields = [field for field in required_fields if not config.get(field)]
    
    if missing_fields:
        logger.error(f"Missing required configuration: {', '.join(missing_fields)}")
        logger.error("Please check your .env file or environment variables")
        raise ValueError(f"Missing required configuration: {', '.join(missing_fields)}")
    
    # 初始化异步 WeChat Pay 客户端
    wxpay = AsyncWeChatPay(**config)
    await wxpay.__aenter__()
    logger.info("WeChat Pay client initialized successfully")


async def close_wechatpay():
    """关闭微信支付客户端（在应用关闭时调用）"""
    global wxpay
    
    # 关闭时清理资源
    if wxpay:
        await wxpay.__aexit__(None, None, None)
        logger.info("WeChat Pay client closed")




# 请求模型
class PaymentRequest(BaseModel):
    description: str
    out_trade_no: str
    total: int  # 金额，单位：分
    openid: Optional[str] = None  # JSAPI 支付时必填


class RefundRequest(BaseModel):
    out_trade_no: str
    out_refund_no: str
    refund: int  # 退款金额，单位：分
    total: int  # 原订单金额，单位：分
    reason: Optional[str] = "用户申请退款"


@router.route('/pay')
async def pay():
    # 以native下单为例，下单成功后即可获取到'code_url'，将'code_url'转换为二维码，并用微信扫码即可进行支付测试。
    out_trade_no = generate_mch_id()
    description = 'demo-description'
    amount = 100
    code, message = await wxpay.pay(
        description=description,
        out_trade_no=out_trade_no,
        amount={'total': amount},
        pay_type=WeChatPayType.NATIVE
    )
    return{'code': code, 'message': message}
@router.post("/api/v1/payment/jsapi")
async def create_jsapi_payment(payment: PaymentRequest):
    """创建 JSAPI 支付订单（公众号/小程序支付）"""
    # 生成随机订单号
    out_trade_no = generate_mch_id()
    if not payment.openid:
        raise HTTPException(status_code=400, detail="openid is required for JSAPI payment")
    
    try:
        code, result = await wxpay.pay(
            description=payment.description,
            out_trade_no=out_trade_no,
            amount={'total': payment.total*100, 'currency': 'CNY'},
            payer={'openid': payment.openid},
            pay_type=WeChatPayType.JSAPI
        )
        
        if code == 200:
            data = json.loads(result)
            prepay_id = data.get("prepay_id")
            print("prepay_id",prepay_id)
            # 生成 JSAPI 调起支付参数
            timestamp = str(int(datetime.now().timestamp()))
            nonce_str = out_trade_no  # 简单起见使用订单号作为随机字符串
            package = f"prepay_id={prepay_id}"
            
            # 签名
            sign_data = [payment.openid, timestamp, nonce_str, package]
            print("sign_data",sign_data)
            return sign_data
            # pay_sign = wxpay.sign(sign_data)
            
            # return {
            #     "code": 0,
            #     "message": "success",
            #     "data": {
            #         "appId": wxpay._appid,
            #         "timeStamp": timestamp,
            #         "nonceStr": nonce_str,
            #         "package": package,
            #         "signType": "RSA",
            #         "paySign": pay_sign
            #     }
            # }
        else:
            logger.error(f"Payment creation failed: {code} - {result}")
            raise HTTPException(status_code=code, detail=result)
            
    except Exception as e:
        logger.error(f"Payment error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/v1/payment/query/{out_trade_no}")
async def query_payment(out_trade_no: str):
    """查询支付订单状态"""
    try:
        code, result = await wxpay.query(out_trade_no=out_trade_no)
        
        if code == 200:
            data = json.loads(result)
            return {
                "code": 0,
                "message": "success",
                "data": {
                    "out_trade_no": data.get("out_trade_no"),
                    "transaction_id": data.get("transaction_id"),
                    "trade_state": data.get("trade_state"),
                    "trade_state_desc": data.get("trade_state_desc"),
                    "amount": data.get("amount"),
                    "payer": data.get("payer")
                }
            }
        else:
            logger.error(f"Query failed: {code} - {result}")
            raise HTTPException(status_code=code, detail=result)
            
    except Exception as e:
        logger.error(f"Query error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/v1/payment/refund")
async def create_refund(refund: RefundRequest):
    """申请退款"""
    try:
        code, result = await wxpay.refund(
            out_trade_no=refund.out_trade_no,
            out_refund_no=refund.out_refund_no,
            amount={
                'refund': refund.refund,
                'total': refund.total,
                'currency': 'CNY'
            },
            reason=refund.reason
        )
        
        if code == 200:
            data = json.loads(result)
            return {
                "code": 0,
                "message": "success",
                "data": {
                    "refund_id": data.get("refund_id"),
                    "out_refund_no": data.get("out_refund_no"),
                    "status": data.get("status"),
                    "amount": data.get("amount")
                }
            }
        else:
            logger.error(f"Refund failed: {code} - {result}")
            raise HTTPException(status_code=code, detail=result)
            
    except Exception as e:
        logger.error(f"Refund error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 健康检查端点
@router.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "service": "wechatpay-async"}
