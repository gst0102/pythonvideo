"""System configuration service."""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List

from dotenv import load_dotenv
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from models.config import SystemConfig

load_dotenv()
logger = logging.getLogger(__name__)

VIP_TEST_MODE = os.getenv("VIP_TEST_MODE", "false").lower() == "true"
VIP_MONTHLY_PRICE = float(os.getenv("VIP_MONTHLY_PRICE", "9.90"))
VIP_QUARTERLY_PRICE = float(os.getenv("VIP_QUARTERLY_PRICE", "26.90"))
VIP_YEARLY_PRICE = float(os.getenv("VIP_YEARLY_PRICE", "88.80"))
VIP_PACKAGE_GIFT_POINTS = {"month": 199, "quarter": 599, "year": 1299}
VIP_PACKAGE_DAILY_LIMITS = {"month": 100, "quarter": 200, "year": 300}
VIP_PACKAGE_WITHDRAW_MIN_AMOUNT = 1.00

DEFAULT_CONFIGS: Dict[str, Dict[str, Any]] = {
    "vip_settings": {
        "enabled": True,
        "page_title": "开通会员",
        "page_subtitle": "享受更多专属权益",
        "order_title": "VIP 会员",
        "virtual_pay": {
            "appid": os.getenv("VIRTUAL_PAY_APPID", os.getenv("APPID", "")),
            "offer_id": os.getenv("VIRTUAL_PAY_OFFER_ID", ""),
            "env": int(os.getenv("VIRTUAL_PAY_ENV", "0")),
            "mode": os.getenv("VIRTUAL_PAY_MODE", "short_series_coin"),
            "notify_url": os.getenv("VIRTUAL_PAY_NOTIFY_URL", ""),
        },
        "packages": [
            {
                "id": "month",
                "name": "月度会员",
                "period_label": "月度会员",
                "price": VIP_MONTHLY_PRICE if VIP_TEST_MODE else 9.90,
                "original_price": 0.50 if VIP_TEST_MODE else 19.90,
                "duration_days": 30,
                "gift_points": VIP_PACKAGE_GIFT_POINTS["month"],
                "daily_game_task_limit": VIP_PACKAGE_DAILY_LIMITS["month"],
                "withdraw_min_amount": VIP_PACKAGE_WITHDRAW_MIN_AMOUNT,
                "benefits": ["免广告", "专属客服", "高清画质"],
            },
            {
                "id": "quarter",
                "name": "季度会员",
                "period_label": "季度会员",
                "price": VIP_QUARTERLY_PRICE if VIP_TEST_MODE else 26.90,
                "original_price": 1.00 if VIP_TEST_MODE else 59.70,
                "duration_days": 90,
                "gift_points": VIP_PACKAGE_GIFT_POINTS["quarter"],
                "daily_game_task_limit": VIP_PACKAGE_DAILY_LIMITS["quarter"],
                "withdraw_min_amount": VIP_PACKAGE_WITHDRAW_MIN_AMOUNT,
                "benefits": ["免广告", "专属客服", "高清画质", "优先处理"],
            },
            {
                "id": "year",
                "name": "年度会员",
                "period_label": "年度会员",
                "price": VIP_YEARLY_PRICE if VIP_TEST_MODE else 88.80,
                "original_price": 2.00 if VIP_TEST_MODE else 238.80,
                "duration_days": 365,
                "gift_points": VIP_PACKAGE_GIFT_POINTS["year"],
                "daily_game_task_limit": VIP_PACKAGE_DAILY_LIMITS["year"],
                "withdraw_min_amount": VIP_PACKAGE_WITHDRAW_MIN_AMOUNT,
                "benefits": ["全部权益", "年度优惠", "专属客服", "专属标识"],
            },
        ],
    },
    "withdrawal_config": {
        "enabled": True,
        "min_amount": 0.10,
        "withdraw_min_first": 1.00,
        "withdraw_min_normal": 5.00,
        "withdraw_min_member": 1.00,
        "max_amount": 200.00,
        "daily_limit": 100.00,
        "tips": "提现申请提交后，实际到账以微信回调结果为准。",
    },
    "commission_settings": {
        "level1_rate": 50.0,
        "level2_rate": 5.0,
        "settlement_days": 7,
        "rules": "邀请好友购买 VIP 后，返利积分先进入冻结账户，期满后可解冻。",
    },
    "service_settings": {
        "auto_reply": False,
        "welcome_msg": "您好，请问有什么可以帮您？",
        "offline_msg": "客服暂时不在线，请留言。",
        "quick_replies": [
            "您好，请问有什么可以帮您？",
            "会员问题可以先查看会员权益说明。",
            "提现一般会在微信回调后完成。",
        ],
    },
    "platform_settings": {
        "platform_name": "视频平台",
        "logo_url": "",
        "contact_info": "",
    },
    "banner_settings": {
        "enabled": True,
        "autoplay": True,
        "interval": 3000,
        "banners": [],
    },
    "ad_revenue_settings": {
        "default_ecpm": 30.0,
        "items": [],
    },
    "ad_reward_settings": {
        "points_per_reward": 5.0,
        "cash_per_reward": 0.05,
    },
    "stage2_points_config": {
        "display_unit": "积分",
        "exchange_rate": 100,
        "checkin_base_points_normal": 1,
        "checkin_base_points_member": 2,
        "checkin_ad_bonus_min": 1,
        "checkin_ad_bonus_max": 3,
        "checkin_ad_bonus_points": 3,
        "game_base_points_min": -2,
        "game_base_points_max": 4,
        "game_rps_win_points": 4,
        "game_rps_lose_points": -2,
        "game_ad_multiplier": 2,
    },
    "stage2_task_config": {
        "daily_game_task_limit_normal": 10,
        "daily_game_task_limit_member_month": 100,
        "daily_game_task_limit_member_quarter": 150,
        "daily_game_task_limit_member_year": 200,
    },
    "stage2_game_bonus_ad_config": {
        "scene": "game_bonus",
        "instances": [
            {
                "ad_code": "reward_game_01",
                "ad_unit_id": os.getenv("WX_REWARDED_AD_GAME_BONUS_1", "adunit-e66ca7039925b740"),
                "status": "active",
                "weight": 100,
                "daily_user_show_limit": 5,
                "daily_user_complete_limit": 5,
            }
        ],
    },
    "netdisk_audit_config": {
        "upload_reward_points": 5,
        "repair_reward_points": 5,
        "report_hide_threshold": 3,
        "quality_high_report_threshold": 3,
        "quality_high_unlock_threshold": 5,
        "quality_burst_report_threshold": 1,
        "quality_burst_unlock_threshold": 3,
        "quality_auto_review_pool": True,
        "quality_auto_hide_high_report": True,
        "quality_auto_hide_burst": False,
        "invalid_penalty_multiplier": 1,
        "auto_hide_on_report": True,
    },
}


class ConfigService:
    @staticmethod
    async def get(session: AsyncSession, config_type: str) -> Dict[str, Any]:
        result = await session.execute(select(SystemConfig).where(SystemConfig.type == config_type))
        config = result.scalar_one_or_none()
        if config and config.config_data:
            defaults = DEFAULT_CONFIGS.get(config_type)
            if isinstance(defaults, dict):
                return {**defaults, **config.config_data}
            return config.config_data
        return DEFAULT_CONFIGS.get(config_type, {})

    @staticmethod
    async def set(session: AsyncSession, config_type: str, config_data: Dict[str, Any]) -> SystemConfig:
        result = await session.execute(select(SystemConfig).where(SystemConfig.type == config_type))
        config = result.scalar_one_or_none()

        if config:
            config.config_data = config_data
            config.updated_at = datetime.utcnow()
        else:
            config = SystemConfig(type=config_type, config_data=config_data)
            session.add(config)

        await session.flush()
        logger.info("[Config] saved %s", config_type)
        return config

    @staticmethod
    async def get_vip_packages(session: AsyncSession) -> Dict[str, Any]:
        config = _normalize_vip_settings(await ConfigService.get(session, "vip_settings"))
        if VIP_TEST_MODE and "packages" in config:
            for pkg in config["packages"]:
                if pkg.get("id") == "month":
                    pkg["price"] = VIP_MONTHLY_PRICE
                    pkg["original_price"] = 0.50
                elif pkg.get("id") == "quarter":
                    pkg["price"] = VIP_QUARTERLY_PRICE
                    pkg["original_price"] = 1.00
                elif pkg.get("id") == "year":
                    pkg["price"] = VIP_YEARLY_PRICE
                    pkg["original_price"] = 2.00
        return config

    @staticmethod
    async def get_withdrawal_config(session: AsyncSession) -> Dict[str, Any]:
        return await ConfigService.get(session, "withdrawal_config")

    @staticmethod
    async def get_all_config_types(session: AsyncSession) -> List[SystemConfig]:
        result = await session.execute(select(SystemConfig).order_by(SystemConfig.type))
        return list(result.scalars().all())


def _normalize_vip_settings(config: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(config or {})
    if normalized.get("packages"):
        normalized["enabled"] = normalized.get("enabled", True)
        normalized["page_title"] = normalized.get("page_title", DEFAULT_CONFIGS["vip_settings"].get("page_title"))
        normalized["page_subtitle"] = normalized.get(
            "page_subtitle",
            DEFAULT_CONFIGS["vip_settings"].get("page_subtitle"),
        )
        normalized["order_title"] = normalized.get("order_title", DEFAULT_CONFIGS["vip_settings"].get("order_title"))
        normalized["packages"] = [_enrich_vip_package(pkg) for pkg in normalized["packages"]]
        return normalized

    month_price = float(normalized.get("month_price", VIP_MONTHLY_PRICE))
    quarter_price = float(normalized.get("quarter_price", VIP_QUARTERLY_PRICE))
    year_price = float(normalized.get("year_price", VIP_YEARLY_PRICE))

    normalized["enabled"] = normalized.get("enabled", True)
    normalized["page_title"] = normalized.get("page_title", "开通会员")
    normalized["page_subtitle"] = normalized.get("page_subtitle", "享受更多专属权益")
    normalized["order_title"] = normalized.get("order_title", "VIP 会员")
    normalized["virtual_pay"] = {
        "appid": normalized.get("virtual_pay_appid") or os.getenv("VIRTUAL_PAY_APPID", os.getenv("APPID", "")),
        "offer_id": normalized.get("virtual_pay_offer_id") or os.getenv("VIRTUAL_PAY_OFFER_ID", ""),
        "env": int(normalized.get("virtual_pay_env", os.getenv("VIRTUAL_PAY_ENV", "0"))),
        "mode": normalized.get("virtual_pay_mode") or os.getenv("VIRTUAL_PAY_MODE", "short_series_coin"),
        "notify_url": normalized.get("virtual_pay_notify_url") or os.getenv("VIRTUAL_PAY_NOTIFY_URL", ""),
    }
    normalized["packages"] = [
        {
            "id": "month",
            "name": "月度会员",
            "period_label": "月度会员",
            "price": month_price,
            "original_price": float(normalized.get("month_original_price", month_price)),
            "duration_days": 30,
            "gift_points": VIP_PACKAGE_GIFT_POINTS["month"],
            "daily_game_task_limit": VIP_PACKAGE_DAILY_LIMITS["month"],
            "withdraw_min_amount": VIP_PACKAGE_WITHDRAW_MIN_AMOUNT,
            "benefits": ["免广告", "专属客服", "高清画质"],
        },
        {
            "id": "quarter",
            "name": "季度会员",
            "period_label": "季度会员",
            "price": quarter_price,
            "original_price": float(normalized.get("quarter_original_price", quarter_price)),
            "duration_days": 90,
            "gift_points": VIP_PACKAGE_GIFT_POINTS["quarter"],
            "daily_game_task_limit": VIP_PACKAGE_DAILY_LIMITS["quarter"],
            "withdraw_min_amount": VIP_PACKAGE_WITHDRAW_MIN_AMOUNT,
            "benefits": ["免广告", "专属客服", "高清画质", "优先处理"],
        },
        {
            "id": "year",
            "name": "年度会员",
            "period_label": "年度会员",
            "price": year_price,
            "original_price": float(normalized.get("year_original_price", year_price)),
            "duration_days": 365,
            "gift_points": VIP_PACKAGE_GIFT_POINTS["year"],
            "daily_game_task_limit": VIP_PACKAGE_DAILY_LIMITS["year"],
            "withdraw_min_amount": VIP_PACKAGE_WITHDRAW_MIN_AMOUNT,
            "benefits": ["全部权益", "年度优惠", "专属客服", "专属标识"],
        },
    ]
    return normalized


def _enrich_vip_package(package: Dict[str, Any]) -> Dict[str, Any]:
    enriched = dict(package or {})
    package_id = str(enriched.get("id") or "month").strip().lower()
    if package_id not in VIP_PACKAGE_GIFT_POINTS:
        package_id = "month"

    enriched["gift_points"] = int(enriched.get("gift_points") or VIP_PACKAGE_GIFT_POINTS[package_id])
    enriched["daily_game_task_limit"] = int(
        enriched.get("daily_game_task_limit") or VIP_PACKAGE_DAILY_LIMITS[package_id]
    )
    enriched["withdraw_min_amount"] = round(
        float(enriched.get("withdraw_min_amount") or VIP_PACKAGE_WITHDRAW_MIN_AMOUNT),
        2,
    )
    return enriched
