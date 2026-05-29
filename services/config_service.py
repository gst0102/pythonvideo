"""
配置服务 — config_service

MVC 架构中的 Service 层，处理系统配置读写。

迁移来源:
  - 云函数 cloudfunctions/admin-api/index.js (getConfig/updateConfig)
  - 前端 src/services/config.ts

使用 JSONB 存储灵活配置，避免为每种配置类型建表。
所有可变的配置项通过 .env 统一管理，避免硬编码。
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from models.config import SystemConfig

load_dotenv()
logger = logging.getLogger(__name__)

# ── 从 .env 读取测试配置 ──
VIP_TEST_MODE = os.getenv("VIP_TEST_MODE", "false").lower() == "true"
VIP_MONTHLY_PRICE = float(os.getenv("VIP_MONTHLY_PRICE", "9.90"))
VIP_QUARTERLY_PRICE = float(os.getenv("VIP_QUARTERLY_PRICE", "26.90"))
VIP_YEARLY_PRICE = float(os.getenv("VIP_YEARLY_PRICE", "88.80"))

# 默认配置（当数据库无记录时使用）
DEFAULT_CONFIGS = {
    "vip_settings": {
        "enabled": True,
        "packages": [
            {
                "id": "month", "name": "月度会员",
                "price": VIP_MONTHLY_PRICE if VIP_TEST_MODE else 9.90,
                "original_price": 0.50 if VIP_TEST_MODE else 19.90,
                "duration_days": 30,
                "benefits": ["免广告", "专属客服", "高清画质"],
            },
            {
                "id": "quarter", "name": "季度会员",
                "price": VIP_QUARTERLY_PRICE if VIP_TEST_MODE else 26.90,
                "original_price": 1.00 if VIP_TEST_MODE else 59.70,
                "duration_days": 90,
                "benefits": ["免广告", "专属客服", "高清画质", "优先处理"],
            },
            {
                "id": "year", "name": "年度会员",
                "price": VIP_YEARLY_PRICE if VIP_TEST_MODE else 88.80,
                "original_price": 2.00 if VIP_TEST_MODE else 238.80,
                "duration_days": 365,
                "benefits": ["全部权益", "年度特惠", "7×24专属客服", "生日特权"],
            },
        ],
    },
    "withdrawal_config": {
        "min_amount": 0.10,
        "max_amount": 200.00,
        "tips": "1. 提现将在1-3个工作日内到账\n2. 单次提现最低0.1元\n3. 如有问题请联系客服",
    },
    "commission_settings": {
        "level1_rate": 10.00,
        "level2_rate": 5.00,
        "rules": "1. 邀请好友购买VIP即可获得佣金\n2. 佣金将在订单完成后自动到账\n3. 二级代理可获得额外奖励",
    },
    "service_settings": {
        "auto_reply": False,
        "welcome_msg": "您好！我是客服小助手，有什么可以帮助您的吗？",
        "offline_msg": "抱歉，客服暂时不在线，请留言，我们会尽快回复您。",
        "quick_replies": [
            "您好，请问有什么可以帮您的？",
            "关于会员问题，您可以查看会员权益说明。",
            "提现问题一般1-3个工作日到账，如有异常请联系我们。",
            "感谢您的反馈，我们会尽快处理！",
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
}


class ConfigService:
    """系统配置服务"""

    @staticmethod
    async def get(session: AsyncSession, config_type: str) -> Dict[str, Any]:
        """
        获取指定类型的配置。
        先从数据库读取，不存在则返回默认值。
        """
        stmt = select(SystemConfig).where(SystemConfig.type == config_type)
        result = await session.execute(stmt)
        config = result.scalar_one_or_none()

        if config and config.config_data:
            logger.debug(f"[Config] 命中数据库: {config_type}")
            return config.config_data

        # 返回默认值
        default = DEFAULT_CONFIGS.get(config_type, {})
        logger.debug(f"[Config] 返回默认配置: {config_type}")
        return default

    @staticmethod
    async def set(
        session: AsyncSession,
        config_type: str,
        config_data: Dict[str, Any],
    ) -> SystemConfig:
        """创建或更新配置"""
        stmt = select(SystemConfig).where(SystemConfig.type == config_type)
        result = await session.execute(stmt)
        config = result.scalar_one_or_none()

        if config:
            config.config_data = config_data
            config.updated_at = datetime.utcnow()
        else:
            config = SystemConfig(
                type=config_type,
                config_data=config_data,
            )
            session.add(config)

        await session.flush()
        logger.info(f"[Config] 配置已保存: {config_type}")
        return config

    @staticmethod
    async def get_vip_packages(session: AsyncSession) -> Dict[str, Any]:
        """便捷方法：获取 VIP 套餐。测试模式下强制用 .env 价格"""
        config = await ConfigService.get(session, "vip_settings")
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
        """便捷方法：获取提现配置"""
        return await ConfigService.get(session, "withdrawal_config")

    @staticmethod
    async def get_all_config_types(session: AsyncSession) -> List[SystemConfig]:
        """获取所有配置（管理端用）"""
        stmt = select(SystemConfig).order_by(SystemConfig.type)
        result = await session.execute(stmt)
        return list(result.scalars().all())
