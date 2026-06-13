import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional


VIRTUAL_PAY_METHOD = "requestMidasPaymentGameItem"


@dataclass(frozen=True)
class VirtualPayConfig:
    app_id: str
    offer_id: str
    app_key: str
    env: int = 0
    mode: str = "short_series_coin"
    currency_type: str = "CNY"


def get_virtual_pay_config() -> VirtualPayConfig:
    app_key = (
        os.getenv("VIRTUAL_PAY_APP_KEY")
        or os.getenv("VIRTUAL_PAY_PROD_APP_KEY")
        or os.getenv("WECHAT_VIRTUAL_PAY_APP_KEY")
        or ""
    ).strip()

    return VirtualPayConfig(
        app_id=(os.getenv("APPID") or os.getenv("VIRTUAL_PAY_APPID") or "").strip(),
        offer_id=(os.getenv("VIRTUAL_PAY_OFFER_ID") or "").strip(),
        app_key=app_key,
        env=int(os.getenv("VIRTUAL_PAY_ENV", "0")),
        mode=os.getenv("VIRTUAL_PAY_MODE", "short_series_coin").strip() or "short_series_coin",
        currency_type=os.getenv("VIRTUAL_PAY_CURRENCY", "CNY").strip() or "CNY",
    )


def build_sign_data(
    config: VirtualPayConfig,
    out_trade_no: str,
    attach: str,
    buy_quantity: int = 1,
    product_id: Optional[str] = None,
    goods_price: Optional[int] = None,
) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "offerId": config.offer_id,
        "buyQuantity": buy_quantity,
        "env": config.env,
        "currencyType": config.currency_type,
        "outTradeNo": out_trade_no,
        "attach": attach,
    }
    if config.mode == "short_series_goods":
        if not product_id or goods_price is None:
            raise ValueError("short_series_goods requires product_id and goods_price")
        data["productId"] = product_id
        data["goodsPrice"] = goods_price
    return data


def dumps_sign_data(sign_data: Dict[str, Any]) -> str:
    return json.dumps(sign_data, ensure_ascii=False, separators=(",", ":"))


def create_pay_sig(sign_data_json: str, app_key: str) -> str:
    if not app_key:
        raise ValueError("VIRTUAL_PAY_APP_KEY is not configured")
    return _hmac_sha256(app_key, f"{VIRTUAL_PAY_METHOD}&{sign_data_json}")


def create_user_signature(sign_data_json: str, session_key: str, app_key: str) -> str:
    # WeChat verifies this as a user-state signature. Prefer the user's current
    # session_key; fall back to app_key only for older clients that have not
    # refreshed login after this upgrade.
    key = session_key or app_key
    if not key:
        raise ValueError("session_key or VIRTUAL_PAY_APP_KEY is required")
    return _hmac_sha256(key, sign_data_json)


def _hmac_sha256(key: str, message: str) -> str:
    return hmac.new(
        key.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
