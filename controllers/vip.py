import hashlib
import json
import logging
import os
import random
import string
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Request
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.response import response
from core.virtual_pay import (
    VirtualPayConfig,
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
from services.wechat_session_service import get_session_key

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/vip", tags=["VIP"])

PERIOD_DAYS = {"month": 30, "quarter": 90, "year": 365}
POINT_RECHARGE_PACKAGES = [
    {"id": "points_100", "title": "100积分", "points": 100, "price": 10.0, "desc": "适合轻度解锁资源"},
    {"id": "points_300", "title": "300积分", "points": 300, "price": 30.0, "desc": "适合持续找资源"},
    {"id": "points_680", "title": "680积分", "points": 680, "price": 68.0, "desc": "适合高频资源需求"},
]
POINT_RECHARGE_TEST_PACKAGE = {
    "id": "points_1",
    "title": "测试单",
    "points": 1,
    "price": 0.01,
    "desc": "仅用于支付链路测试，测试完成后关闭",
}


@router.get("/packages", summary="get vip packages")
async def get_packages(session: AsyncSession = Depends(get_session)):
    return response(data=await ConfigService.get_vip_packages(session))


@router.get("/status", summary="get vip status")
async def get_status(
    openid: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).where(User.openid == openid))
    user = result.scalar_one_or_none()
    if not user:
        return response([], 404, "user not found")

    days_remaining = 0
    if user.is_vip and user.vip_expire_at:
        delta = user.vip_expire_at - datetime.utcnow()
        days_remaining = max(0, delta.days)

    return response(
        data=VipStatusResponse(
            is_vip=user.is_vip,
            vip_expire_at=user.vip_expire_at,
            days_remaining=days_remaining,
        ).model_dump(mode="json")
    )


@router.get("/points-packages", summary="get points recharge packages")
async def get_points_packages():
    return response(data={"packages": _get_point_recharge_packages()})


@router.post("/points-order", summary="create points virtual payment order")
async def create_points_order(
    req: CreateOrderRequest,
    request: Request,
    claims: dict = Depends(get_current_claims),
    session: AsyncSession = Depends(get_session),
):
    user = await _get_user_by_claims(session, claims)
    if not user:
        return response([], 404, "user not found")

    package = next((item for item in _get_point_recharge_packages() if item.get("id") == req.package_id), None)
    if not package:
        return response([], 400, "package not found")

    config = await ConfigService.get_vip_packages(session)
    virtual_config, config_error = _resolve_virtual_pay_config(config)
    if config_error:
        return config_error
    session_key = await get_session_key(request, user.openid)
    if not session_key:
        return response([], 401, "登录状态已过期，请重新登录后再试")

    price = float(package["price"])
    points = int(package["points"])
    if price < 0.01:
        return response([], 400, "测试金额不能低于0.01元")
    out_trade_no = _generate_out_trade_no()
    order = Order(
        user_id=user.id,
        amount=price,
        period=str(package["id"]),
        duration_days=0,
        description=f"充值积分 {points}分",
        out_trade_no=out_trade_no,
        status="pending",
    )
    session.add(order)
    await session.flush()

    pay_params = _build_virtual_pay_params(
        virtual_config,
        session_key=session_key,
        order=order,
        package_id=str(package["id"]),
        product_id=str(package.get("product_id") or package["id"]),
        price=price,
        buy_quantity=points,
    )
    return response(
        data={
            "order_id": str(order.id),
            "out_trade_no": out_trade_no,
            "status": order.status,
            "points": points,
            "pay_params": pay_params,
        },
        msg="order created",
    )


def _get_point_recharge_packages() -> list[dict]:
    packages = [dict(item) for item in POINT_RECHARGE_PACKAGES]
    if os.getenv("POINTS_RECHARGE_TEST_PACKAGE_ENABLED", "false").lower() == "true":
        packages.insert(0, dict(POINT_RECHARGE_TEST_PACKAGE))
    return packages


@router.get("/orders/{out_trade_no}", summary="get virtual payment order status")
async def get_order_status(
    out_trade_no: str,
    claims: dict = Depends(get_current_claims),
    session: AsyncSession = Depends(get_session),
):
    user = await _get_user_by_claims(session, claims)
    if not user:
        return response([], 404, "user not found")

    result = await session.execute(
        select(Order).where(Order.out_trade_no == out_trade_no, Order.user_id == user.id)
    )
    order = result.scalar_one_or_none()
    if not order:
        return response([], 404, "order not found")

    return response(
        data={
            "order_id": str(order.id),
            "out_trade_no": order.out_trade_no,
            "status": order.status,
            "amount": float(order.amount),
            "description": order.description,
            "period": order.period,
            "paid_at": order.paid_at.isoformat() if order.paid_at else None,
        }
    )


@router.post("/order", summary="create vip virtual payment order")
async def create_order(
    req: CreateOrderRequest,
    request: Request,
    claims: dict = Depends(get_current_claims),
    session: AsyncSession = Depends(get_session),
):
    user = await _get_user_by_claims(session, claims)
    if not user:
        return response([], 404, "user not found")

    config = await ConfigService.get_vip_packages(session)
    packages = config.get("packages", [])
    package = next((item for item in packages if item.get("id") == req.package_id), None)
    if not package:
        return response([], 400, "package not found")

    virtual_config, config_error = _resolve_virtual_pay_config(config)
    if config_error:
        return config_error
    session_key = await get_session_key(request, user.openid)
    if not session_key:
        return response([], 401, "登录状态已过期，请重新登录后再试")

    price = float(package["price"])
    period = str(package["id"])
    duration_days = int(package.get("duration_days") or PERIOD_DAYS.get(period, 30))
    description = str(package.get("name") or "VIP")
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

    product_id = package.get("product_id") or package.get("productId") or period
    pay_params = _build_virtual_pay_params(
        virtual_config,
        session_key=session_key,
        order=order,
        package_id=period,
        product_id=str(product_id),
        price=price,
    )
    return response(
        data={"order_id": str(order.id), "out_trade_no": out_trade_no, "pay_params": pay_params},
        msg="order created",
    )


@router.post("/virtual-pay/notify", summary="virtual payment notify")
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
    transaction_id = wechat_pay_info.get("TransactionId") or data.get("TransactionId") or out_trade_no
    paid_time = wechat_pay_info.get("PaidTime") or data.get("PaidTime")
    total_fee = goods_info.get("ActualPrice") or goods_info.get("OrigPrice") or data.get("ActualPrice") or data.get("TotalFee") or 0

    try:
        async with get_session_ctx() as session:
            ok = await PaymentService.handle_payment_success(
                session,
                out_trade_no=out_trade_no,
                transaction_id=str(transaction_id),
                total_fee_in_fen=int(total_fee or 0),
                paid_at=_format_paid_at(paid_time),
            )
        return _xml_reply(0 if ok else 50001, "success" if ok else "order update failed")
    except Exception as exc:
        logger.error("[VIP] notify failed: %s", exc, exc_info=True)
        return _xml_reply(50000, "server error")


def _generate_out_trade_no() -> str:
    return f"{int(time.time())}{''.join(random.choices(string.digits, k=8))}"


async def _get_user_by_claims(session: AsyncSession, claims: dict) -> User | None:
    openid = claims["openid"]
    result = await session.execute(select(User).where(User.openid == openid))
    return result.scalar_one_or_none()


def _resolve_virtual_pay_config(config: dict):
    env_virtual_config = get_virtual_pay_config()
    virtual_config = _build_runtime_virtual_config(config, env_virtual_config)
    notify_token = _get_virtual_pay_notify_token()

    if not virtual_config.app_id or not virtual_config.offer_id:
        return None, response([], 503, "充值支付暂未开通，请稍后再试")
    if not virtual_config.app_key:
        return None, response([], 503, "充值支付暂未开通，请稍后再试")
    if not notify_token:
        return None, response([], 503, "充值支付暂未开通，请稍后再试")
    return virtual_config, None


def _build_virtual_pay_params(
    virtual_config: VirtualPayConfig,
    *,
    session_key: str,
    order: Order,
    package_id: str,
    product_id: str,
    price: float,
    buy_quantity: int = 1,
) -> dict:
    attach = json.dumps(
        {"order_id": str(order.id), "user_id": str(order.user_id), "package_id": package_id},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    goods_price = int(Decimal(str(price)) * 100)
    sign_data = build_sign_data(
        virtual_config,
        out_trade_no=order.out_trade_no,
        attach=attach,
        buy_quantity=buy_quantity,
        product_id=product_id,
        goods_price=goods_price,
    )
    sign_data_json = dumps_sign_data(sign_data)
    return {
        "mode": virtual_config.mode,
        "signData": sign_data_json,
        "paySig": create_pay_sig(sign_data_json, virtual_config.app_key),
        "signature": create_user_signature(
            sign_data_json,
            session_key,
            virtual_config.app_key,
        ),
        "out_trade_no": order.out_trade_no,
        "attach": attach,
    }


def _verify_notify_signature(sig: str, timestamp: str, nonce: str, body: str) -> bool:
    token = _get_virtual_pay_notify_token()
    if not token or not sig:
        return False
    expected = hashlib.sha1("".join(sorted([token, timestamp, nonce, body])).encode("utf-8")).hexdigest()
    return expected == sig


def _build_runtime_virtual_config(config: dict, env_config: VirtualPayConfig) -> VirtualPayConfig:
    runtime_cfg = config.get("virtual_pay", {}) if isinstance(config, dict) else {}
    runtime_app_id = str(runtime_cfg.get("appid") or "").strip()
    runtime_offer_id = str(runtime_cfg.get("offer_id") or "").strip()
    use_runtime_pay_cfg = bool(runtime_app_id or runtime_offer_id)
    return VirtualPayConfig(
        app_id=runtime_app_id or env_config.app_id,
        offer_id=runtime_offer_id or env_config.offer_id,
        app_key=env_config.app_key,
        env=int(runtime_cfg.get("env", env_config.env)) if use_runtime_pay_cfg else env_config.env,
        mode=str(runtime_cfg.get("mode") or env_config.mode or "short_series_coin").strip()
        if use_runtime_pay_cfg
        else env_config.mode,
        currency_type=env_config.currency_type,
    )


def _get_virtual_pay_notify_token() -> str:
    import os

    return (os.getenv("VIRTUAL_PAY_NOTIFY_TOKEN") or os.getenv("PAY_NOTIFY_TOKEN") or "").strip()


def _parse_xml(xml_text: str) -> dict:
    root = ET.fromstring(xml_text)

    def node_to_value(node: ET.Element):
        children = list(node)
        if not children:
            return (node.text or "").strip()
        return {child.tag: node_to_value(child) for child in children}

    return {child.tag: node_to_value(child) for child in root}


def _xml_reply(retcode: int, retmsg: str) -> str:
    return f"<xml><return_code>{retcode}</return_code><return_msg>{retmsg}</return_msg></xml>"


def _format_paid_at(paid_time: str | None) -> str:
    if not paid_time:
        return datetime.utcnow().isoformat()
    return str(paid_time)
