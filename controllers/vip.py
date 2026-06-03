import json
import logging
import random
import hashlib
import string
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.response import response
from core.virtual_pay import (
    build_sign_data,
    create_pay_sig,
    create_user_signature,
    dumps_sign_data,
    get_virtual_pay_config,
)
from jwt_create import get_current_claims, get_current_user
from models.base import get_session, get_session_ctx
from models.order import Order
from models.user import User
from schemas.user import CreateOrderRequest, VipStatusResponse
from services.config_service import ConfigService
from services.payment_service import PaymentService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/vip", tags=["VIP member"])

PERIOD_DAYS = {"month": 30, "quarter": 90, "year": 365}


@router.get("/packages", summary="Get VIP packages")
async def get_packages(session: AsyncSession = Depends(get_session)):
    config = await ConfigService.get_vip_packages(session)
    return response(data=config)


@router.get("/status", summary="Get VIP status")
async def get_status(
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).where(User.openid == openid))
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


@router.post("/order", summary="Create VIP virtual payment order")
async def create_order(
    req: CreateOrderRequest,
    claims: dict = Depends(get_current_claims),
    session: AsyncSession = Depends(get_session),
):
    openid = claims["openid"]
    result = await session.execute(select(User).where(User.openid == openid))
    user = result.scalar_one_or_none()
    if not user:
        return response([], 404, "用户不存在")

    config = await ConfigService.get_vip_packages(session)
    packages = config.get("packages", [])
    package = next((p for p in packages if p.get("id") == req.package_id), None)
    if not package:
        return response([], 400, "无效的会员套餐")

    price = float(package["price"])
    period = package["id"]
    duration_days = int(package.get("duration_days") or PERIOD_DAYS.get(period, 30))
    description = package.get("name", "VIP会员")
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

    try:
        virtual_config = get_virtual_pay_config()
        if not virtual_config.offer_id:
            return response([], 500, "虚拟支付 OfferId 未配置")

        attach = json.dumps({
            "order_id": str(order.id),
            "user_id": str(user.id),
            "package_id": period,
        }, ensure_ascii=False, separators=(",", ":"))

        goods_price = int(Decimal(str(price)) * 100)
        product_id = package.get("product_id") or package.get("productId") or period
        sign_data = build_sign_data(
            virtual_config,
            out_trade_no=out_trade_no,
            attach=attach,
            buy_quantity=1,
            product_id=product_id,
            goods_price=goods_price,
        )
        sign_data_json = dumps_sign_data(sign_data)
        pay_params = {
            "mode": virtual_config.mode,
            "signData": sign_data_json,
            "paySig": create_pay_sig(sign_data_json, virtual_config.app_key),
            "signature": create_user_signature(
                sign_data_json,
                str(claims.get("session_key") or ""),
                virtual_config.app_key,
            ),
            "out_trade_no": out_trade_no,
            "attach": attach,
        }

        return response(data={
            "order_id": str(order.id),
            "out_trade_no": out_trade_no,
            "pay_params": pay_params,
        }, msg="订单创建成功")
    except Exception as exc:
        logger.error("[VIP] virtual payment order failed: %s", exc, exc_info=True)
        return response([], 500, f"虚拟支付下单失败: {exc}")


def _generate_out_trade_no() -> str:
    timestamp = str(int(time.time()))
    random_suffix = "".join(random.choices(string.digits, k=8))
    return f"{timestamp}{random_suffix}"


@router.post("/virtual-pay/notify", summary="Virtual payment delivery notify")
async def virtual_pay_notify(
    request: Request,
    signature: str = Query("", alias="signature"),
    msg_signature: str = Query("", alias="msg_signature"),
    timestamp: str = Query("", alias="timestamp"),
    nonce: str = Query("", alias="nonce"),
):
    body = (await request.body()).decode("utf-8")
    if not _verify_notify_signature(signature or msg_signature, timestamp, nonce, body):
        return _xml_reply(40001, "invalid signature")

    data = _parse_xml(body)
    event = data.get("Event", "")
    if event not in {"xpay_goods_deliver_notify", "xpay_subscribe_pay_notify"}:
        return _xml_reply(0, "success")

    out_trade_no = data.get("OutTradeNo", "")
    if not out_trade_no:
        return _xml_reply(40002, "missing OutTradeNo")

    wechat_pay_info = data.get("WeChatPayInfo", {})
    goods_info = data.get("GoodsInfo", {})
    transaction_id = (
        wechat_pay_info.get("TransactionId")
        or data.get("TransactionId")
        or out_trade_no
    )
    paid_time = wechat_pay_info.get("PaidTime") or data.get("PaidTime")
    paid_at = _format_paid_at(paid_time)
    total_fee = (
        goods_info.get("ActualPrice")
        or goods_info.get("OrigPrice")
        or data.get("ActualPrice")
        or data.get("TotalFee")
        or 0
    )

    try:
        async with get_session_ctx() as session:
            ok = await PaymentService.handle_payment_success(
                session,
                out_trade_no=out_trade_no,
                transaction_id=str(transaction_id),
                total_fee_in_fen=int(total_fee or 0),
                paid_at=paid_at,
            )
        return _xml_reply(0 if ok else 50001, "success" if ok else "order update failed")
    except Exception as exc:
        logger.error("[VIP] virtual pay notify failed: %s", exc, exc_info=True)
        return _xml_reply(50000, "server error")


def _verify_notify_signature(sig: str, timestamp: str, nonce: str, body: str) -> bool:
    token = (
        __import__("os").getenv("VIRTUAL_PAY_NOTIFY_TOKEN")
        or __import__("os").getenv("PAY_NOTIFY_TOKEN")
        or ""
    ).strip()
    if not token:
        logger.warning("[VIP] VIRTUAL_PAY_NOTIFY_TOKEN is not configured; notify signature skipped")
        return True
    items = sorted([token, timestamp, nonce, body])
    expected = hashlib.sha1("".join(items).encode("utf-8")).hexdigest()
    return bool(sig) and expected == sig


def _parse_xml(xml_text: str) -> dict:
    root = ET.fromstring(xml_text)

    def node_to_value(node: ET.Element):
        children = list(node)
        if not children:
            return node.text or ""
        return {child.tag: node_to_value(child) for child in children}

    return {child.tag: node_to_value(child) for child in list(root)}


def _format_paid_at(value) -> str:
    if not value:
        return datetime.utcnow().isoformat()
    try:
        ts = int(value)
        return datetime.utcfromtimestamp(ts).isoformat()
    except (TypeError, ValueError):
        return str(value)


def _xml_reply(err_code: int, err_msg: str) -> str:
    return Response(
        content=f"<xml><ErrCode>{err_code}</ErrCode><ErrMsg>{err_msg}</ErrMsg></xml>",
        media_type="application/xml",
    )
