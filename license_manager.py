#!/usr/bin/env python3
"""
跨境卖家 MCP 服务器 - 许可证管理器
Cross-Border Seller MCP Server - License Manager
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime
import os


class LicenseTier(Enum):
    """许可证等级"""
    FREE = "free"
    PRO = "pro"
    BUSINESS = "business"


@dataclass
class License:
    """许可证数据类"""
    key: str
    tier: LicenseTier
    activated_at: datetime
    expires_at: Optional[datetime] = None
    features: List[str] = None

    def __post_init__(self):
        if self.features is None:
            self.features = get_features_for_tier(self.tier)


# 各等级包含的功能
TIER_FEATURES = {
    LicenseTier.FREE: [
        "get_inventory_1688",
        "get_orders_amazon",
        "sync_inventory",
        "update_fulfillment_amazon",
        "get_low_stock_alerts",
        "save_product_profile",
    ],
    LicenseTier.PRO: [
        "get_inventory_1688",
        "get_orders_amazon",
        "sync_inventory",
        "update_fulfillment_amazon",
        "get_low_stock_alerts",
        "get_product_cost_1688",
        "calculate_amazon_price",
        "sync_price",
        "update_amazon_price",
        "get_competitor_prices",
        "get_product_reviews",
        "calculate_true_profit",
        "save_product_profile",
        "get_product_profile",
        "list_all_products",
        "get_stale_products",
    ],
    LicenseTier.BUSINESS: [
        "get_inventory_1688",
        "get_orders_amazon",
        "sync_inventory",
        "update_fulfillment_amazon",
        "get_low_stock_alerts",
        "get_product_cost_1688",
        "calculate_amazon_price",
        "sync_price",
        "update_amazon_price",
        "get_competitor_prices",
        "get_product_reviews",
        "get_negative_reviews",
        "get_review_alerts",
        "calculate_true_profit",
        "save_product_profile",
        "get_product_profile",
        "list_all_products",
        "get_stale_products",
    ]
}


def get_features_for_tier(tier: LicenseTier) -> List[str]:
    """获取指定等级的功能列表"""
    return TIER_FEATURES.get(tier, TIER_FEATURES[LicenseTier.FREE])


# 演示用的许可证密钥（生产环境应使用安全存储）
DEMO_LICENSES = {
    "FREE_DEMO_12345": LicenseTier.FREE,
    "PRO_DEMO_99999": LicenseTier.PRO,
    "BUSINESS_DEMO_88888": LicenseTier.BUSINESS,
}


class LicenseManager:
    """许可证管理器"""

    def __init__(self, license_key: Optional[str] = None):
        self._license_key_override = license_key

    def _get_license_key(self) -> str:
        """获取当前许可证密钥（优先覆盖值，然后环境变量）"""
        if self._license_key_override is not None:
            return self._license_key_override
        return os.getenv("LICENSE_KEY", "")

    def _validate_license(self) -> License:
        """验证许可证密钥"""
        license_key = self._get_license_key()

        if not license_key:
            return License(
                key="free",
                tier=LicenseTier.FREE,
                activated_at=datetime.now()
            )

        # 检查演示许可证
        if license_key in DEMO_LICENSES:
            return License(
                key=license_key,
                tier=DEMO_LICENSES[license_key],
                activated_at=datetime.now()
            )

        # 生产环境应该连接到在线验证服务
        # 这里默认返回免费版
        return License(
            key=license_key,
            tier=LicenseTier.FREE,
            activated_at=datetime.now()
        )

    def get_current_license(self) -> License:
        """获取当前许可证"""
        return self._validate_license()

    def is_feature_available(self, feature_name: str) -> bool:
        """检查功能是否可用"""
        license = self.get_current_license()
        return feature_name in license.features

    def reset(self, license_key: Optional[str] = None):
        """重置许可证管理器"""
        self._license_key_override = license_key

    def get_tier_name(self, tier: Optional[LicenseTier] = None) -> str:
        """获取等级名称（中文）"""
        tier = tier or self.get_current_license().tier
        names = {
            LicenseTier.FREE: "免费版",
            LicenseTier.PRO: "专业版",
            LicenseTier.BUSINESS: "商业版",
        }
        return names.get(tier, "未知等级")

    def get_upgrade_message(self, missing_feature: str) -> str:
        """获取升级提示信息（中文）"""
        messages = {
            "get_product_cost_1688": "升级到专业版可使用1688产品成本查询功能",
            "calculate_amazon_price": "升级到专业版可使用亚马逊价格计算功能",
            "sync_price": "升级到专业版可使用价格同步功能",
            "update_amazon_price": "升级到专业版可使用亚马逊价格更新功能",
            "get_competitor_prices": "升级到专业版可使用竞品价格查询功能",
            "get_product_reviews": "升级到专业版可使用产品评论查询功能",
            "calculate_true_profit": "升级到专业版可使用真实利润计算器功能",
            "get_negative_reviews": "升级到商业版可使用负面评论监控功能",
            "get_review_alerts": "升级到商业版可使用评论警报功能",
            "get_product_profile": "升级到专业版可使用产品档案查询功能",
            "list_all_products": "升级到专业版可使用产品列表功能",
            "get_stale_products": "升级到专业版可使用过期产品检测功能",
        }
        return messages.get(missing_feature, "此功能需要升级到专业版或商业版")


# 单例实例
_license_manager: Optional[LicenseManager] = None


def get_license_manager() -> LicenseManager:
    """获取许可证管理器单例"""
    global _license_manager
    if _license_manager is None:
        _license_manager = LicenseManager()
    return _license_manager


def reset_license_manager(license_key: Optional[str] = None):
    """重置许可证管理器（用于测试）"""
    global _license_manager
    _license_manager = LicenseManager(license_key=license_key)
    return _license_manager
