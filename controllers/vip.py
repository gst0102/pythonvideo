"""
VIP 接口 — /vip

MVC 架构中的 Controller 层。
"""

import logging
import random
import string
import time
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.response import response
from core.wepay import WeChatPayV3
from models.base import get_session
from models.user import User
from models.order import Order
from schemas.user import CreateOrderRequest, VipStatusResponse
from services.config_service import ConfigService
from jwt_create import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/vip", tags=["VIP 会员"])

# 套餐天数映射
PERIOD_DAYS = {"month": 30, "quarter": 90, "year": 365}


@router.get("/packages", summary="获取 VIP 套餐列表")
async def get_packages(session: AsyncSession = Depends(get_session)):
    """获取所有 VIP 套餐"""
    config = await ConfigService.get_vip_packages(session)
    return response(data=config)


@router.get("/status", summary="查询 VIP 状态")
async def get_status(
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """查询当前用户的 VIP 状态"""
    stmt = select(User).where(User.openid == openid)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        return response([], 404, "用户不存在")

    days_remaining = 0
    if user.is_vip and user.vip_expire_at:
        delta = user.vip_expire_at - datetime.utcnow()
        days_remaining = max(0, delta.days)

    return response(data=VipStatusResponse(
        is_vip=user.is_vip,
        vip_expire_at=user.vip_expire_at,
        days_remaining=days_remaining,
    ).model_dump(mode="json"))


@router.post("/order", summary="创建 VIP 订单（调起微信支付）")
async def create_order(
    req: CreateOrderRequest,
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """创建 VIP 订单并返回微信支付参数"""
    # 1. 查找用户
    stmt = select(User).where(User.openid == openid)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        return response([], 404, "用户不存在")

    # 2. 获取套餐配置
    config = await ConfigService.get_vip_packages(session)
    packages = config.get("packages", [])
    match = next((p for p in packages if p.get("id") == req.package_id), None)

    if not match:
        return response([], 400, "无效的套餐")

    price = float(match["price"])
    period = match["id"]
    duration_days = match.get("duration_days", PERIOD_DAYS.get(period, 30))
    description = match.get("name", "VIP会员")

    # 3. 生成订单
    out_trade_no = _generate_out_trade_no()

    order = Order(
        user_id=user.id,
        amount=price,
        period=period,
        duration_days=duration_days,
        description=description,
        out_trade_no=out_trade_no,
        status="pending",
    )
    session.add(order)
    await session.flush()

    # 4. 调用微信支付统一下单
    import os
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_pay = {
        "mch_id": os.getenv("mchid"),
        "app_id": os.getenv("APPID"),
        "api_v3_key": os.getenv("APIv3"),
        "private_key_path": os.path.join(BASE_DIR, "certs", "apiclient_key.pem"),
        "serial_no": os.getenv("serial_no"),
        "notify_url": os.getenv("NOTIFY_URL", ""),
    }
    wx_pay = WeChatPayV3(**config_pay)

    try:
        price_in_fen = int(Decimal(str(price)) * 100)
        prepay_id = wx_pay.create_jsapi_order(
            description=description,
            out_trade_no=out_trade_no,
            total=price_in_fen,
            openid=openid,
            notify_url=config_pay["notify_url"],
        )
        pay_params = wx_pay.get_jsapi_params(prepay_id)

        return response(data={
            "order_id": str(order.id),
            "pay_params": pay_params,
        }, msg="订单创建成功")

    except Exception as e:
        logger.error(f"[VIP] 创建订单失败: {e}")
        return response([], 500, f"支付下单失败: {str(e)}")


def _generate_out_trade_no() -> str:
    """生成唯一商户订单号"""
    timestamp = str(int(time.time()))
    random_suffix = "".join(random.choices(string.digits, k=6))
    return f"{timestamp}{random_suffix}"
