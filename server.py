#!/usr/bin/env python3
"""
Cross-Border Seller MCP Server.

This MCP server provides tools for cross-border e-commerce sellers to manage
inventory between 1688 (China supplier platform) and Amazon Seller Central.

Tools:
    - get_inventory_1688: Get stock level for a SKU from 1688
    - get_orders_amazon: Fetch recent Amazon orders from the last N days
    - sync_inventory: Compare 1688 stock vs Amazon listing, flag mismatches
    - update_fulfillment_amazon: Update order fulfillment status on Amazon
    - get_low_stock_alerts: Return all SKUs where stock is below threshold
    - get_product_cost_1688: Get product cost from 1688 supplier
    - calculate_amazon_price: Calculate optimal Amazon price with profit margins
    - sync_price: Compare 1688 cost vs Amazon price, flag mismatches
    - update_amazon_price: Update Amazon listing price
    - get_competitor_prices: Research competitor prices on Amazon
    - get_product_reviews: Get product reviews from Amazon
    - get_negative_reviews: Get 1-2 star reviews needing attention
    - get_review_alerts: Get actionable alerts for bad reviews with suggested responses
"""

import json
import os
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional, Callable
from functools import wraps

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, field_validator

load_dotenv()

from mcp.server.fastmcp import FastMCP

from database import (
    save_product_profile,
    get_product_profile,
    get_all_product_profiles,
    delete_product_profile,
    get_stale_product_profiles,
    is_data_fresh,
)

from license_manager import (
    LicenseManager,
    get_license_manager,
    LicenseTier
)

mcp = FastMCP("crossborder_seller_mcp")

API_1688_BASE_URL = "https://api.1688.com/openapi"
AMAZON_BASE_URL = "https://sellingpartnerapi-na.amazon.com"

LOW_STOCK_THRESHOLD = int(os.getenv("LOW_STOCK_THRESHOLD", "10"))


def require_feature(feature_name: str):
    """
    功能权限检查装饰器
    Feature access check decorator
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            license_manager = get_license_manager()
            if not license_manager.is_feature_available(feature_name):
                tier = license_manager.get_tier_name()
                msg = license_manager.get_upgrade_message(feature_name)
                return f"⚠️  当前等级: {tier}\n{msg}\n请访问 https://yourwebsite.com 升级"
            return await func(*args, **kwargs)
        return wrapper
    return decorator


class ResponseFormat(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"


class SaveProductProfileInput(BaseModel):
    sku: str = Field(..., description="SKU identifier")
    product_name: Optional[str] = Field(None, description="Product name")
    cost_cny: Optional[float] = Field(None, description="Product cost in CNY")
    shipping_to_amazon_usd: Optional[float] = Field(None, description="Shipping cost to Amazon in USD")
    amazon_referral_fee_percent: Optional[float] = Field(None, description="Amazon referral fee percentage")
    fba_fee_usd: Optional[float] = Field(None, description="FBA fulfillment fee in USD")
    monthly_storage_fee_usd: Optional[float] = Field(None, description="Monthly storage fee in USD")
    advertising_acos_percent: Optional[float] = Field(None, description="Advertising ACoS percentage")
    payment_processing_fee_percent: Optional[float] = Field(None, description="Payment processing fee percentage")
    return_rate_percent: Optional[float] = Field(None, description="Return rate percentage")
    customs_duty_percent: Optional[float] = Field(None, description="Customs duty percentage")
    overhead_percent: Optional[float] = Field(None, description="Overhead percentage")
    notes: Optional[str] = Field(None, description="Additional notes")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output format")


class GetProductProfileInput(BaseModel):
    sku: str = Field(..., description="SKU identifier")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output format")


class GetStaleProductsInput(BaseModel):
    hours: int = Field(default=24, description="Hours to consider data stale", ge=1, le=720)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output format")


class GetInventory1688Input(BaseModel):
    sku: str = Field(
        ...,
        description="SKU identifier for the product (e.g., 'SKU-12345')",
        min_length=1,
        max_length=100,
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable",
    )


class GetOrdersAmazonInput(BaseModel):
    days: int = Field(
        default=7,
        description="Number of days to look back for orders (1-90)",
        ge=1,
        le=90,
    )
    status: Optional[str] = Field(
        default=None,
        description="Filter by order status (e.g., 'Pending', 'Shipped', 'Delivered')",
    )
    limit: int = Field(
        default=50,
        description="Maximum number of orders to return",
        ge=1,
        le=100,
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable",
    )

    @field_validator("days")
    @classmethod
    def validate_days(cls, v: int) -> int:
        if v < 1 or v > 90:
            raise ValueError("Days must be between 1 and 90")
        return v


class SyncInventoryInput(BaseModel):
    sku: str = Field(
        ...,
        description="SKU identifier to sync (e.g., 'SKU-12345')",
        min_length=1,
        max_length=100,
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable",
    )


class UpdateFulfillmentAmazonInput(BaseModel):
    order_id: str = Field(
        ...,
        description="Amazon order ID (e.g., '123-4567890-1234567')",
        min_length=1,
        max_length=50,
    )
    status: str = Field(
        ...,
        description="New fulfillment status: 'Pending', 'Processing', 'Shipped', 'Delivered', 'Cancelled'",
    )

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        valid_statuses = ["Pending", "Processing", "Shipped", "Delivered", "Cancelled"]
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of: {', '.join(valid_statuses)}")
        return v


class GetLowStockAlertsInput(BaseModel):
    threshold: Optional[int] = Field(
        default=None,
        description="Custom stock threshold (default from .env or 10)",
        ge=1,
        le=10000,
    )
    platform: Optional[str] = Field(
        default=None,
        description="Filter by platform: '1688', 'Amazon', or 'both' (default: both)",
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable",
    )


class GetProductCost1688Input(BaseModel):
    sku: str = Field(
        ...,
        description="SKU identifier for the product (e.g., 'SKU-12345')",
        min_length=1,
        max_length=100,
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable",
    )


class CalculateAmazonPriceInput(BaseModel):
    sku: str = Field(
        ...,
        description="SKU identifier for the product",
        min_length=1,
        max_length=100,
    )
    cost_cny: Optional[float] = Field(
        default=None,
        description="Product cost in CNY (if not provided, fetches from 1688)",
        ge=0,
    )
    target_margin_percent: float = Field(
        default=25.0,
        description="Target profit margin percentage (default: 25%)",
        ge=0,
        le=100,
    )
    shipping_cost_usd: float = Field(
        default=2.0,
        description="Shipping cost per unit in USD (default: $2.00)",
        ge=0,
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Output format: 'markdown' or 'json'",
    )


class SyncPriceInput(BaseModel):
    sku: str = Field(
        ...,
        description="SKU identifier to sync pricing",
        min_length=1,
        max_length=100,
    )
    target_margin_percent: float = Field(
        default=25.0,
        description="Target profit margin percentage (default: 25%)",
        ge=0,
        le=100,
    )
    shipping_cost_usd: float = Field(
        default=2.0,
        description="Shipping cost per unit in USD (default: $2.00)",
        ge=0,
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Output format: 'markdown' or 'json'",
    )


class UpdateAmazonPriceInput(BaseModel):
    sku: str = Field(
        ...,
        description="SKU identifier",
        min_length=1,
        max_length=100,
    )
    new_price: float = Field(
        ...,
        description="New price in USD",
        gt=0,
    )
    currency: str = Field(
        default="USD",
        description="Currency code (default: USD)",
    )


class GetCompetitorPricesInput(BaseModel):
    sku: str = Field(
        ...,
        description="SKU identifier or search term",
        min_length=1,
        max_length=200,
    )
    limit: int = Field(
        default=5,
        description="Maximum competitor prices to return",
        ge=1,
        le=20,
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Output format: 'markdown' or 'json'",
    )


class GetProductReviewsInput(BaseModel):
    sku: str = Field(
        ...,
        description="SKU or ASIN to fetch reviews for",
        min_length=1,
        max_length=100,
    )
    days: int = Field(
        default=30,
        description="Number of days to look back (1-90)",
        ge=1,
        le=90,
    )
    min_rating: Optional[int] = Field(
        default=None,
        description="Filter by minimum rating (1-5)",
        ge=1,
        le=5,
    )
    max_rating: Optional[int] = Field(
        default=None,
        description="Filter by maximum rating (1-5)",
        ge=1,
        le=5,
    )
    limit: int = Field(
        default=20,
        description="Maximum reviews to return",
        ge=1,
        le=100,
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Output format: 'markdown' or 'json'",
    )


class GetNegativeReviewsInput(BaseModel):
    sku: Optional[str] = Field(
        default=None,
        description="SKU to filter (optional, omit for all products)",
        max_length=100,
    )
    days: int = Field(
        default=7,
        description="Number of days to look back",
        ge=1,
        le=90,
    )
    severity: str = Field(
        default="all",
        description="Filter by severity: 'critical' (1 star), 'warning' (2 stars), or 'all'",
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'",
    )


class GetReviewAlertsInput(BaseModel):
    days: int = Field(
        default=7,
        description="Number of days to look back",
        ge=1,
        le=90,
    )
    include_supplier_flags: bool = Field(
        default=True,
        description="Flag reviews that indicate supplier quality issues",
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'",
    )


class CalculateTrueProfitInput(BaseModel):
    sku: str = Field(
        ...,
        description="SKU identifier for the product",
        min_length=1,
        max_length=100,
    )
    selling_price_usd: float = Field(
        ...,
        description="Current selling price on Amazon in USD",
        gt=0,
    )
    cost_cny: Optional[float] = Field(
        default=None,
        description="Product cost from 1688 in CNY (will fetch if not provided)",
        ge=0,
    )
    shipping_to_amazon_usd: float = Field(
        default=2.0,
        description="Shipping cost from supplier to Amazon warehouse in USD",
        ge=0,
    )
    amazon_referral_fee_percent: Optional[float] = Field(
        default=None,
        description="Amazon referral fee percentage (default from config)",
        ge=0,
        le=100,
    )
    fba_fee_usd: float = Field(
        default=3.5,
        description="FBA fulfillment fee per unit in USD",
        ge=0,
    )
    monthly_storage_fee_usd: float = Field(
        default=0.3,
        description="Monthly storage fee per unit in USD",
        ge=0,
    )
    advertising_acos_percent: float = Field(
        default=20.0,
        description="Advertising Cost of Sale percentage (default 20%)",
        ge=0,
        le=100,
    )
    payment_processing_fee_percent: float = Field(
        default=2.9,
        description="Payment processing fee percentage (default 2.9%)",
        ge=0,
        le=100,
    )
    return_rate_percent: float = Field(
        default=5.0,
        description="Return rate percentage (default 5%)",
        ge=0,
        le=100,
    )
    customs_duty_percent: float = Field(
        default=3.0,
        description="Customs duty percentage (default 3%)",
        ge=0,
        le=100,
    )
    overhead_percent: float = Field(
        default=8.0,
        description="Overhead percentage (default 8%)",
        ge=0,
        le=100,
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'",
    )


def _get_1688_headers() -> dict:
    return {
        "Authorization": f"Bearer {os.getenv('ALIBABA_API_KEY', '')}",
        "Content-Type": "application/json",
        "X-App-Key": os.getenv("ALIBABA_APP_KEY", ""),
        "X-App-Secret": os.getenv("ALIBABA_APP_SECRET", ""),
    }


def _get_amazon_headers() -> dict:
    access_token = os.getenv("AMAZON_ACCESS_TOKEN", "")
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "x-amz-access-token": access_token,
    }


def _handle_api_error(e: Exception, platform: str) -> str:
    """Format API errors with platform-specific context and actionable messages."""
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status == 401:
            return f"Error: {platform} authentication failed. Please check your API credentials in .env file."
        elif status == 403:
            return f"Error: {platform} access denied. Insufficient permissions for this operation."
        elif status == 404:
            return f"Error: {platform} resource not found. Please verify the SKU or order ID."
        elif status == 429:
            return f"Error: {platform} rate limit exceeded. Please wait before making more requests."
        elif status >= 500:
            return f"Error: {platform} server error ({status}). Please try again later."
        return f"Error: {platform} API request failed with status {status}"
    elif isinstance(e, httpx.TimeoutException):
        return f"Error: {platform} request timed out. Please check your network connection and try again."
    elif isinstance(e, httpx.ConnectError):
        return f"Error: Could not connect to {platform}. Please verify the API endpoint configuration."
    return f"Error: Unexpected error with {platform}: {type(e).__name__} - {str(e)}"


async def _fetch_1688_inventory(sku: str) -> dict:
    """Fetch inventory data from 1688 API for a given SKU."""
    headers = _get_1688_headers()
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{API_1688_BASE_URL}/offer/{sku}/inventory",
            headers=headers,
            params={"sku": sku},
        )
        response.raise_for_status()
        return response.json()


async def _fetch_1688_all_inventory() -> list:
    """Fetch all inventory items from 1688 API."""
    headers = _get_1688_headers()
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{API_1688_BASE_URL}/offer/list",
            headers=headers,
            params={"pageSize": 100},
        )
        response.raise_for_status()
        data = response.json()
        return data.get("result", {}).get("products", [])


async def _fetch_amazon_listings() -> list:
    """Fetch all listings from Amazon Seller Central."""
    headers = _get_amazon_headers()
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{AMAZON_BASE_URL}/catalog/2022-04-01/items",
            headers=headers,
            params={"marketplaceIds": os.getenv("AMAZON_MARKETPLACE_ID", "ATVPDKIKX0DER")},
        )
        response.raise_for_status()
        data = response.json()
        return data.get("items", [])


async def _fetch_amazon_listing(sku: str) -> dict:
    """Fetch specific listing from Amazon by SKU."""
    headers = _get_amazon_headers()
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{AMAZON_BASE_URL}/catalog/2022-04-01/items/{sku}",
            headers=headers,
            params={"marketplaceIds": os.getenv("AMAZON_MARKETPLACE_ID", "ATVPDKIKX0DER")},
        )
        response.raise_for_status()
        return response.json()


async def _fetch_amazon_orders(days: int, status: Optional[str] = None, limit: int = 50) -> dict:
    """Fetch orders from Amazon Seller Central API."""
    headers = _get_amazon_headers()
    created_after = (datetime.now() - timedelta(days=days)).isoformat()

    params: dict[str, Any] = {
        "MarketplaceIds": os.getenv("AMAZON_MARKETPLACE_ID", "ATVPDKIKX0DER"),
        "CreatedAfter": created_after,
        "MaxResultsPerPage": min(limit, 100),
    }
    if status:
        params["OrderStatus"] = status

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{AMAZON_BASE_URL}/orders/v0/orders",
            headers=headers,
            params=params,
        )
        response.raise_for_status()
        return response.json()


async def _fetch_1688_product_price(sku: str) -> dict:
    """Fetch product price from 1688 API for a given SKU."""
    headers = _get_1688_headers()
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{API_1688_BASE_URL}/offer/{sku}/price",
            headers=headers,
            params={"sku": sku},
        )
        response.raise_for_status()
        return response.json()


async def _fetch_1688_product_details(sku: str) -> dict:
    """Fetch full product details from 1688 API including price."""
    headers = _get_1688_headers()
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{API_1688_BASE_URL}/offer/{sku}/detail",
            headers=headers,
            params={"sku": sku},
        )
        response.raise_for_status()
        return response.json()


async def _fetch_amazon_product_price(sku: str) -> dict:
    """Fetch product pricing from Amazon by SKU."""
    headers = _get_amazon_headers()
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{AMAZON_BASE_URL}/catalog/2022-04-01/items/{sku}",
            headers=headers,
            params={
                "marketplaceIds": os.getenv("AMAZON_MARKETPLACE_ID", "ATVPDKIKX0DER"),
                "includedData": "summaries,pricing,availability",
            },
        )
        response.raise_for_status()
        return response.json()


async def _search_amazon_competitors(keyword: str) -> dict:
    """Search Amazon for competitor products by keyword."""
    headers = _get_amazon_headers()
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{AMAZON_BASE_URL}/catalog/2022-04-01/items",
            headers=headers,
            params={
                "marketplaceIds": os.getenv("AMAZON_MARKETPLACE_ID", "ATVPDKIKX0DER"),
                "keywords": keyword,
                "includedData": "summaries,pricing",
            },
        )
        response.raise_for_status()
        return response.json()


async def _fetch_amazon_reviews(sku: str, days: int = 30, limit: int = 50) -> dict:
    """Fetch product reviews from Amazon API."""
    headers = _get_amazon_headers()
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{AMAZON_BASE_URL}/reviews/v1/skus/{sku}",
            headers=headers,
            params={
                "marketplaceIds": os.getenv("AMAZON_MARKETPLACE_ID", "ATVPDKIKX0DER"),
                "reviewType": "all",
                "reviewState": "approved",
            },
        )
        response.raise_for_status()
        return response.json()


async def _fetch_amazon_product_summary(sku: str) -> dict:
    """Fetch product summary including rating info from Amazon."""
    headers = _get_amazon_headers()
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{AMAZON_BASE_URL}/catalog/2022-04-01/items/{sku}",
            headers=headers,
            params={
                "marketplaceIds": os.getenv("AMAZON_MARKETPLACE_ID", "ATVPDKIKX0DER"),
                "includedData": "summaries,attributes",
            },
        )
        response.raise_for_status()
        return response.json()


def _get_supplier_quality_keywords() -> dict:
    """Get keywords that flag supplier quality issues."""
    return {
        "defective": ["defective", "broken", "not working", "damaged", "malfunction"],
        "quality": ["cheap quality", "poor quality", "low quality", "flimsy", "feels cheap"],
        "packaging": ["missing parts", "no packaging", "arrived damaged", "packaging torn"],
        "inconsistent": ["different from description", "not as pictured", "color different", "size wrong"],
        "safety": ["safety issue", "stopped working", "overheating", "smells burning"],
    }


def _analyze_review_for_supplier_issues(review_text: str) -> list:
    """Analyze review text for supplier quality issues."""
    text_lower = review_text.lower()
    issues = []
    keywords = _get_supplier_quality_keywords()

    for category, words in keywords.items():
        for word in words:
            if word in text_lower:
                issues.append({
                    "category": category,
                    "keyword": word,
                    "severity": "high" if category in ["defective", "safety"] else "medium",
                })
                break

    return issues


def _get_rating_severity(rating: int) -> str:
    """Get severity level based on rating."""
    if rating == 1:
        return "critical"
    elif rating == 2:
        return "warning"
    elif rating == 3:
        return "info"
    return "positive"


def _parse_review_date(date_str: str) -> Optional[datetime]:
    """Parse review date string to datetime, handling various formats."""
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        return dt
    except (ValueError, AttributeError):
        try:
            return datetime.strptime(date_str[:19], "%Y-%m-%dT%H:%M:%S")
        except (ValueError, AttributeError):
            return None


def _format_review_date(date_str: str) -> str:
    """Format ISO date to readable format."""
    dt = _parse_review_date(date_str)
    if dt:
        return dt.strftime("%Y-%m-%d")
    return date_str[:10] if date_str else "Unknown"


def _get_currency_rate() -> float:
    """Get USD to CNY exchange rate from environment or use default."""
    rate_str = os.getenv("USD_CNY_EXCHANGE_RATE", "")
    if rate_str:
        try:
            return float(rate_str)
        except ValueError:
            pass
    return 7.2


def _get_amazon_fees() -> float:
    """Get Amazon referral fee percentage from environment or use default."""
    fee_str = os.getenv("AMAZON_REFERRAL_FEE_PERCENT", "")
    if fee_str:
        try:
            return float(fee_str)
        except ValueError:
            pass
    return 15.0


def _calculate_true_profit(
    selling_price_usd: float,
    cost_cny: float,
    exchange_rate: float,
    shipping_to_amazon_usd: float,
    amazon_referral_fee_percent: float,
    fba_fee_usd: float,
    monthly_storage_fee_usd: float,
    advertising_acos_percent: float,
    payment_processing_fee_percent: float,
    return_rate_percent: float,
    customs_duty_percent: float,
    overhead_percent: float,
) -> dict:
    """Calculate true profit including ALL cost factors for cross-border sales."""
    
    # Convert product cost to USD
    cost_usd = cost_cny / exchange_rate
    
    # Calculate all cost components
    amazon_referral_fee = selling_price_usd * (amazon_referral_fee_percent / 100)
    advertising_cost = selling_price_usd * (advertising_acos_percent / 100)
    payment_processing_fee = selling_price_usd * (payment_processing_fee_percent / 100)
    customs_duty = cost_usd * (customs_duty_percent / 100)
    overhead = selling_price_usd * (overhead_percent / 100)
    
    # Return-related costs (assume we lose product cost and shipping on returns)
    return_cost = (cost_usd + shipping_to_amazon_usd) * (return_rate_percent / 100)
    
    # Total costs
    total_cost = (
        cost_usd +
        shipping_to_amazon_usd +
        amazon_referral_fee +
        fba_fee_usd +
        monthly_storage_fee_usd +
        advertising_cost +
        payment_processing_fee +
        return_cost +
        customs_duty +
        overhead
    )
    
    # Profit calculations
    gross_profit = selling_price_usd - (cost_usd + shipping_to_amazon_usd)
    net_profit = selling_price_usd - total_cost
    profit_margin = (net_profit / selling_price_usd * 100) if selling_price_usd > 0 else 0
    break_even_price = total_cost
    
    # ROI calculations
    roi = (net_profit / cost_usd * 100) if cost_usd > 0 else 0
    
    return {
        "selling_price_usd": selling_price_usd,
        "cost_cny": cost_cny,
        "cost_usd": round(cost_usd, 2),
        "exchange_rate": exchange_rate,
        
        # Cost breakdown
        "cost_breakdown": {
            "product_cost_usd": round(cost_usd, 2),
            "shipping_to_amazon_usd": round(shipping_to_amazon_usd, 2),
            "amazon_referral_fee_usd": round(amazon_referral_fee, 2),
            "fba_fulfillment_fee_usd": round(fba_fee_usd, 2),
            "monthly_storage_fee_usd": round(monthly_storage_fee_usd, 2),
            "advertising_cost_usd": round(advertising_cost, 2),
            "payment_processing_fee_usd": round(payment_processing_fee, 2),
            "return_cost_usd": round(return_cost, 2),
            "customs_duty_usd": round(customs_duty, 2),
            "overhead_usd": round(overhead, 2),
        },
        
        # Total costs
        "total_cost_usd": round(total_cost, 2),
        
        # Profit metrics
        "gross_profit_usd": round(gross_profit, 2),
        "net_profit_usd": round(net_profit, 2),
        "profit_margin_percent": round(profit_margin, 2),
        "break_even_price_usd": round(break_even_price, 2),
        "roi_percent": round(roi, 2),
        
        # Recommendations
        "is_profitable": net_profit > 0,
        "recommended_price_adjustment": round(break_even_price * 1.2 - selling_price_usd, 2) if net_profit <= 0 else 0,
    }


def _calculate_recommended_price(
    cost_cny: float,
    exchange_rate: float,
    amazon_fee_percent: float,
    shipping_cost_usd: float,
    target_margin_percent: float,
) -> dict:
    """Calculate recommended Amazon price based on 1688 cost and parameters."""
    cost_usd = cost_cny / exchange_rate
    total_cost = cost_usd + shipping_cost_usd
    fee_amount = total_cost * (amazon_fee_percent / 100)
    cost_after_fees = total_cost + fee_amount
    recommended_price = cost_after_fees / (1 - (target_margin_percent / 100))
    profit = recommended_price - total_cost - fee_amount
    actual_margin = (profit / recommended_price * 100) if recommended_price > 0 else 0

    return {
        "cost_cny": cost_cny,
        "cost_usd": round(cost_usd, 2),
        "exchange_rate": exchange_rate,
        "shipping_cost_usd": shipping_cost_usd,
        "subtotal_usd": round(total_cost, 2),
        "amazon_fee_percent": amazon_fee_percent,
        "amazon_fee_amount": round(fee_amount, 2),
        "total_cost_usd": round(cost_after_fees, 2),
        "target_margin_percent": target_margin_percent,
        "recommended_price_usd": round(recommended_price, 2),
        "actual_profit_usd": round(profit, 2),
        "actual_margin_percent": round(actual_margin, 2),
    }


def _get_price_action(current: float, recommended: float, threshold: float = 0.05) -&gt; str:
    """Determine price action recommendation based on difference."""
    diff = recommended - current
    diff_percent = (diff / current * 100) if current &gt; 0 else 0

    if abs(diff_percent) &lt; threshold * 100:
        return "KEEP_CURRENT"
    elif diff &gt; 0:
        return "INCREASE_PRICE"
    else:
        return "DECREASE_PRICE"


@mcp.tool(
    name="save_product_profile",
    annotations={
        "title": "Save Product Profile",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def save_product_profile_tool(params: SaveProductProfileInput) -&gt; str:
    """
    Save or update product cost data to keep it up-to-date.
    保存或更新产品成本数据以保持最新。
    
    Use this tool to:
    - Save cost information for quick access later
    - Auto-fill data in other tools
    - Track when data was last updated
    
    Args:
        params: Product cost data
    """
    try:
        # Prepare data for saving
        save_data = {}
        for field in [
            "product_name", "cost_cny", "shipping_to_amazon_usd",
            "amazon_referral_fee_percent", "fba_fee_usd", "monthly_storage_fee_usd",
            "advertising_acos_percent", "payment_processing_fee_percent",
            "return_rate_percent", "customs_duty_percent", "overhead_percent", "notes"
        ]:
            value = getattr(params, field)
            if value is not None:
                save_data[field] = value
        
        save_product_profile(params.sku, **save_data)
        
        result = {
            "sku": params.sku,
            "saved": True,
            "saved_at": datetime.now().isoformat(),
            "fields_saved": list(save_data.keys())
        }
        
        if params.response_format == ResponseFormat.JSON:
            return json.dumps(result, indent=2, ensure_ascii=False)
        else:
            lines = [
                f"# ✅ Product Profile Saved: {params.sku}",
                "",
                f"**Saved at**: {result['saved_at']}",
                "",
                "Fields saved:",
            ]
            for field in result["fields_saved"]:
                lines.append(f"- {field}")
            return "\n".join(lines)
            
    except Exception as e:
        return _handle_api_error(e, "Save Product Profile")


@mcp.tool(
    name="get_product_profile",
    annotations={
        "title": "Get Product Profile",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@require_feature("get_product_profile")
async def get_product_profile_tool(params: GetProductProfileInput) -&gt; str:
    """
    Get saved product data. Returns warning if data is stale.
    获取已保存的产品数据。如果数据过期会显示警告。
    """
    try:
        profile = get_product_profile(params.sku)
        
        if not profile:
            if params.response_format == ResponseFormat.JSON:
                return json.dumps({"sku": params.sku, "found": False}, indent=2, ensure_ascii=False)
            else:
                return f"# ❌ Product Profile Not Found\n\nNo saved data for SKU: {params.sku}"
        
        is_fresh, age = is_data_fresh(params.sku)
        
        if params.response_format == ResponseFormat.JSON:
            return json.dumps({
                "sku": params.sku,
                "found": True,
                "is_fresh": is_fresh,
                "data_age_hours": age.total_seconds() / 3600 if age else None,
                **profile
            }, indent=2, ensure_ascii=False)
        else:
            freshness_warning = "" if is_fresh else f"\n\n⚠️  **Data is stale!** Last updated {age.total_seconds()/3600:.1f} hours ago."
            
            lines = [
                f"# 📦 Product Profile: {params.sku}",
                "",
            ]
            
            if profile["product_name"]:
                lines.append(f"**Product**: {profile['product_name']}")
            
            if profile["cost_cny"]:
                lines.append(f"**Cost**: ¥{profile['cost_cny']:.2f}")
            
            lines.extend([
                "",
                "## Cost Details",
            ])
            
            cost_fields = [
                ("shipping_to_amazon_usd", "Shipping to Amazon", "$"),
                ("fba_fee_usd", "FBA Fee", "$"),
                ("monthly_storage_fee_usd", "Storage Fee", "$"),
                ("amazon_referral_fee_percent", "Referral Fee", "%"),
                ("advertising_acos_percent", "ACoS", "%"),
                ("payment_processing_fee_percent", "Payment Fee", "%"),
                ("return_rate_percent", "Return Rate", "%"),
                ("customs_duty_percent", "Customs Duty", "%"),
                ("overhead_percent", "Overhead", "%"),
            ]
            
            for field, label, symbol in cost_fields:
                value = profile[field]
                if value:
                    lines.append(f"- **{label}**: {symbol}{value:.2f}")
            
            if profile["notes"]:
                lines.extend([
                    "",
                    "## Notes",
                    profile["notes"],
                ])
            
            lines.extend([
                "",
                f"**Last updated**: {profile['last_updated']}",
                freshness_warning
            ])
            
            return "\n".join(lines)
            
    except Exception as e:
        return _handle_api_error(e, "Get Product Profile")


@mcp.tool(
    name="list_all_products",
    annotations={
        "title": "List All Products",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@require_feature("list_all_products")
async def list_all_products(params: GetStaleProductsInput) -&gt; str:
    """List all saved product profiles. Shows freshness status."""
    try:
        all_profiles = get_all_product_profiles()
        
        if not all_profiles:
            if params.response_format == ResponseFormat.JSON:
                return json.dumps({"products": [], "count": 0}, indent=2, ensure_ascii=False)
            else:
                return "# 📦 No Products Saved\n\nYou haven't saved any product profiles yet."
        
        if params.response_format == ResponseFormat.JSON:
            result = {
                "products": all_profiles,
                "count": len(all_profiles),
                "stale_count": len(get_stale_product_profiles(params.hours))
            }
            return json.dumps(result, indent=2, ensure_ascii=False)
        else:
            stale_products = get_stale_product_profiles(params.hours)
            stale_skus = {p["sku"] for p in stale_products}
            
            lines = [
                f"# 📦 Product Profiles ({len(all_profiles)} total)",
                "",
            ]
            
            for profile in all_profiles:
                sku = profile["sku"]
                is_stale = sku in stale_skus
                status_icon = "🔴" if is_stale else "🟢"
                
                lines.append(f"## {status_icon} {sku}")
                
                if profile["product_name"]:
                    lines.append(f"**Product**: {profile['product_name']}")
                if profile["cost_cny"]:
                    lines.append(f"**Cost**: ¥{profile['cost_cny']:.2f}")
                lines.append(f"**Last updated**: {profile['last_updated']}")
                lines.append("")
            
            if stale_products:
                lines.extend([
                    "---",
                    f"## ⚠️ Stale Products (last updated &gt; {params.hours}h ago)",
                    "",
                ])
                for p in stale_products:
                    lines.append(f"- {p['sku']}")
            
            return "\n".join(lines)
            
    except Exception as e:
        return _handle_api_error(e, "List Products")


@mcp.tool(
    name="get_stale_products",
    annotations={
        "title": "Get Stale Products",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@require_feature("get_stale_products")
async def get_stale_products_tool(params: GetStaleProductsInput) -&gt; str:
    """Find products with data that needs updating."""
    try:
        stale = get_stale_product_profiles(params.hours)
        
        if params.response_format == ResponseFormat.JSON:
            return json.dumps({
                "stale_products": stale,
                "count": len(stale),
                "threshold_hours": params.hours
            }, indent=2, ensure_ascii=False)
        else:
            if not stale:
                return f"# ✅ All Products Fresh\n\nNo products need updating (threshold: {params.hours} hours)."
            
            lines = [
                f"# ⚠️ Stale Products ({len(stale)} found)",
                "",
                f"These products haven't been updated in more than {params.hours} hours:",
                "",
            ]
            
            for product in stale:
                lines.append(f"## 🔴 {product['sku']}")
                lines.append(f"**Last updated**: {product['last_updated']}")
                if product["product_name"]:
                    lines.append(f"**Product**: {product['product_name']}")
                lines.append("")
            
            lines.extend([
                "---",
                "## Recommendation",
                "",
                "- Update product costs from 1688",
                "- Review and update shipping/FBA fees",
                "- Check current ACoS and return rates",
            ])
            
            return "\n".join(lines)
            
    except Exception as e:
        return _handle_api_error(e, "Get Stale Products")


@mcp.tool(
    name="get_inventory_1688",
    annotations={
        "title": "Get 1688 Inventory",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def get_inventory_1688(params: GetInventory1688Input) -> str:
    """
    Get stock level for a SKU from 1688 supplier platform.

    This tool retrieves the current inventory quantity and product information
    from 1688.com (Alibaba's wholesale platform in China).

    Args:
        params (GetInventory1688Input): Validated input containing:
            - sku (str): Product SKU identifier (e.g., "SKU-12345")
            - response_format (ResponseFormat): Output format - 'markdown' or 'json'

    Returns:
        str: JSON or markdown formatted inventory data containing:
            - sku: Product SKU
            - product_name: Name of the product
            - stock_quantity: Current available stock
            - reserved_quantity: Stock reserved for pending orders
            - available_quantity: Stock available for new orders
            - last_updated: Timestamp of last inventory update
            - supplier_info: Supplier details (name, location)

    Error Handling:
        - Returns error message if API authentication fails (401)
        - Returns error message if SKU not found (404)
        - Returns error message if rate limited (429)
        - Returns error message on timeout or connection errors
    """
    try:
        data = await _fetch_1688_inventory(params.sku)

        inventory_data = {
            "sku": params.sku,
            "product_name": data.get("productName", "Unknown Product"),
            "stock_quantity": data.get("stockQuantity", 0),
            "reserved_quantity": data.get("reservedQuantity", 0),
            "available_quantity": data.get("availableQuantity", 0),
            "last_updated": data.get("lastUpdated", datetime.now().isoformat()),
            "supplier_info": {
                "name": data.get("supplierName", "N/A"),
                "location": data.get("supplierLocation", "N/A"),
            },
        }

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(inventory_data, indent=2, ensure_ascii=False)
        else:
            lines = [
                f"# 1688 Inventory: {params.sku}",
                "",
                f"**Product Name**: {inventory_data['product_name']}",
                f"**Total Stock**: {inventory_data['stock_quantity']}",
                f"**Reserved**: {inventory_data['reserved_quantity']}",
                f"**Available**: {inventory_data['available_quantity']}",
                f"**Last Updated**: {inventory_data['last_updated']}",
                "",
                "### Supplier Info",
                f"- **Name**: {inventory_data['supplier_info']['name']}",
                f"- **Location**: {inventory_data['supplier_info']['location']}",
            ]
            return "\n".join(lines)

    except Exception as e:
        return _handle_api_error(e, "1688")


@mcp.tool(
    name="get_orders_amazon",
    annotations={
        "title": "Get Amazon Orders",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def get_orders_amazon(params: GetOrdersAmazonInput) -> str:
    """
    Fetch recent Amazon orders from the Selling Partner API.

    This tool retrieves orders from Amazon Seller Central within the specified
    number of days, with optional filtering by order status.

    Args:
        params (GetOrdersAmazonInput): Validated input containing:
            - days (int): Number of days to look back (1-90, default: 7)
            - status (Optional[str]): Filter by order status (Pending, Shipped, etc.)
            - limit (int): Maximum orders to return (1-100, default: 50)
            - response_format (ResponseFormat): Output format - 'markdown' or 'json'

    Returns:
        str: JSON or markdown formatted order data containing:
            - total_orders: Number of orders found
            - orders: Array of order objects with:
                - order_id: Amazon order ID
                - purchase_date: When order was placed
                - status: Current order status
                - total_amount: Order total in USD
                - items: Array of items (sku, quantity, price)
                - shipping_address: Customer address (city, country)
                - fulfillment_channel: "MFN" (Merchant) or "AFN" (FBA)

    Error Handling:
        - Returns error message if API authentication fails (401)
        - Returns error message if access token expired (403)
        - Returns error message if rate limited (429)
        - Returns error message on timeout or connection errors
    """
    try:
        data = await _fetch_amazon_orders(params.days, params.status, params.limit)

        orders = data.get("orders", [])
        simplified_orders = []

        for order in orders:
            simplified_orders.append({
                "order_id": order.get("AmazonOrderId", "N/A"),
                "purchase_date": order.get("PurchaseDate", "N/A"),
                "last_update_date": order.get("LastUpdateDate", "N/A"),
                "status": order.get("OrderStatus", "Unknown"),
                "total_amount": order.get("OrderTotal", {}).get("Amount", "0.00"),
                "currency": order.get("OrderTotal", {}).get("CurrencyCode", "USD"),
                "fulfillment_channel": order.get("FulfillmentChannel", "Unknown"),
                "ship_service_level": order.get("ShipServiceLevel", "Standard"),
                "number_of_items": order.get("NumberOfItems", 0),
                "shipping_address": {
                    "name": order.get("ShippingAddress", {}).get("Name", "N/A"),
                    "city": order.get("ShippingAddress", {}).get("City", "N/A"),
                    "country": order.get("ShippingAddress", {}).get("CountryCode", "N/A"),
                },
            })

        if params.response_format == ResponseFormat.JSON:
            result = {
                "total_orders": len(simplified_orders),
                "days_queried": params.days,
                "status_filter": params.status,
                "orders": simplified_orders,
            }
            return json.dumps(result, indent=2, ensure_ascii=False)
        else:
            lines = [f"# Amazon Orders (Last {params.days} Days)", ""]

            if params.status:
                lines.append(f"**Status Filter**: {params.status}")
            lines.append(f"**Total Orders Found**: {len(simplified_orders)}")
            lines.append("")

            for i, order in enumerate(simplified_orders, 1):
                lines.append(f"## Order {i}: {order['order_id']}")
                lines.append(f"- **Status**: {order['status']}")
                lines.append(f"- **Date**: {order['purchase_date'][:10]}")
                lines.append(f"- **Total**: {order['currency']} {order['total_amount']}")
                lines.append(f"- **Fulfillment**: {order['fulfillment_channel']}")
                lines.append(f"- **Items**: {order['number_of_items']}")
                lines.append(f"- **Ship To**: {order['shipping_address']['city']}, {order['shipping_address']['country']}")
                lines.append("")

            return "\n".join(lines)

    except Exception as e:
        return _handle_api_error(e, "Amazon")


@mcp.tool(
    name="sync_inventory",
    annotations={
        "title": "Sync Inventory",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def sync_inventory(params: SyncInventoryInput) -> str:
    """
    Compare 1688 stock levels against Amazon listings and flag inventory mismatches.

    This tool retrieves stock information from both platforms and compares them
    to identify discrepancies that may require attention (overselling risk,
    stock excess, or data sync issues).

    Args:
        params (SyncInventoryInput): Validated input containing:
            - sku (str): Product SKU to synchronize
            - response_format (ResponseFormat): Output format - 'markdown' or 'json'

    Returns:
        str: JSON or markdown formatted sync report containing:
            - sku: Product SKU
            - source_platform: "1688"
            - source_stock: Stock level on 1688
            - target_platform: "Amazon"
            - target_stock: Stock level on Amazon
            - mismatch_detected: Boolean indicating if stocks differ
            - mismatch_type: "overstock", "understock", or "match"
            - discrepancy: Absolute difference in stock levels
            - discrepancy_percent: Percentage difference
            - recommendation: Suggested action to take
            - last_checked: Timestamp of comparison

    Error Handling:
        - Returns error message if either API fails authentication (401)
        - Returns error message if SKU not found on either platform (404)
        - Returns error message if rate limited (429)
        - Gracefully handles partial failures (one platform available)
    """
    try:
        source_1688 = await _fetch_1688_inventory(params.sku)
        source_1688_stock = source_1688.get("availableQuantity", 0)

        try:
            amazon_listing = await _fetch_amazon_listing(params.sku)
            amazon_stock = amazon_listing.get("availability", {}).get("quantity", 0)
            amazon_status = "available"
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                amazon_stock = 0
                amazon_status = "not_listed"
            else:
                raise
        except Exception:
            amazon_stock = 0
            amazon_status = "unavailable"

        stock_diff = source_1688_stock - amazon_stock
        percent_diff = ((stock_diff / source_1688_stock) * 100) if source_1688_stock > 0 else 0

        if amazon_status == "not_listed":
            mismatch_type = "not_listed"
            recommendation = "Create Amazon listing for this product. Stock: {stock}".format(
                stock=source_1688_stock
            )
        elif amazon_status == "unavailable":
            mismatch_type = "sync_error"
            recommendation = "Unable to fetch Amazon stock. Manual check required."
        elif stock_diff == 0:
            mismatch_type = "match"
            recommendation = "Inventory is synchronized. No action required."
        elif stock_diff > 0:
            mismatch_type = "overstock"
            recommendation = f"Amazon listing understocked by {stock_diff} units. Consider increasing Amazon quantity."
        else:
            mismatch_type = "understock"
            recommendation = f"OVERSELLING RISK: Amazon shows {abs(stock_diff)} more units than available on 1688. Update Amazon immediately!"

        sync_result = {
            "sku": params.sku,
            "source_platform": "1688",
            "source_stock": source_1688_stock,
            "source_product_name": source_1688.get("productName", "Unknown"),
            "target_platform": "Amazon",
            "target_stock": amazon_stock,
            "amazon_listing_status": amazon_status,
            "mismatch_detected": mismatch_type != "match",
            "mismatch_type": mismatch_type,
            "discrepancy": abs(stock_diff),
            "discrepancy_percent": round(abs(percent_diff), 2),
            "recommendation": recommendation,
            "last_checked": datetime.now().isoformat(),
        }

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(sync_result, indent=2, ensure_ascii=False)
        else:
            alert_indicator = "⚠️ MISMATCH" if sync_result["mismatch_detected"] else "✓ OK"
            lines = [
                f"# Inventory Sync Report: {params.sku} [{alert_indicator}]",
                "",
                "## Stock Comparison",
                f"| Platform | Stock Level |",
                f"|----------|-------------|",
                f"| 1688     | {sync_result['source_stock']}         |",
                f"| Amazon   | {sync_result['target_stock']}         |",
                "",
                f"**Discrepancy**: {sync_result['discrepancy']} units ({sync_result['discrepancy_percent']}%)",
                f"**Mismatch Type**: {sync_result['mismatch_type']}",
                "",
                f"## Recommendation",
                f"{sync_result['recommendation']}",
                "",
                f"_Last checked: {sync_result['last_checked']}_",
            ]
            return "\n".join(lines)

    except Exception as e:
        return _handle_api_error(e, "1688/Amazon sync")


@mcp.tool(
    name="update_fulfillment_amazon",
    annotations={
        "title": "Update Amazon Fulfillment",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def update_fulfillment_amazon(params: UpdateFulfillmentAmazonInput) -> str:
    """
    Update order fulfillment status on Amazon Seller Central.

    This tool updates the fulfillment status of an order in Amazon's system,
    which affects customer notifications and order tracking visibility.

    Args:
        params (UpdateFulfillmentAmazonInput): Validated input containing:
            - order_id (str): Amazon order ID (e.g., "123-4567890-1234567")
            - status (str): New fulfillment status - Pending, Processing, Shipped, Delivered, Cancelled

    Returns:
        str: JSON formatted confirmation containing:
            - success: Boolean indicating operation result
            - order_id: The updated order ID
            - previous_status: Status before update (if available)
            - new_status: The new fulfillment status
            - updated_at: Timestamp of the update
            - tracking_info: Shipping details (if status is Shipped)

    Error Handling:
        - Returns error message if API authentication fails (401)
        - Returns error message if order not found (404)
        - Returns error message if order already in target status
        - Returns error message if status transition invalid (400)
        - Returns error message if rate limited (429)

    Note:
        Some status transitions may not be allowed by Amazon (e.g., cannot go
        from Delivered back to Shipped). Always verify current order status first.
    """
    try:
        headers = _get_amazon_headers()
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.put(
                f"{AMAZON_BASE_URL}/orders/v0/orders/{params.order_id}/fulfillment",
                headers=headers,
                json={
                    "fulfillmentOrder": {
                        "orderId": params.order_id,
                        "fulfillmentAction": params.status,
                    }
                },
            )

            if response.status_code == 200:
                result = {
                    "success": True,
                    "order_id": params.order_id,
                    "new_status": params.status,
                    "updated_at": datetime.now().isoformat(),
                    "message": f"Order {params.order_id} fulfillment status updated to {params.status}",
                }
            else:
                result = {
                    "success": False,
                    "order_id": params.order_id,
                    "error_code": response.status_code,
                    "message": f"Failed to update order: {response.text}",
                }

            return json.dumps(result, indent=2, ensure_ascii=False)

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400:
            return json.dumps({
                "success": False,
                "order_id": params.order_id,
                "error": "Invalid status transition",
                "message": "Cannot transition to this status. Check order history.",
            }, indent=2)
        return _handle_api_error(e, "Amazon")
    except Exception as e:
        return _handle_api_error(e, "Amazon")


@mcp.tool(
    name="get_low_stock_alerts",
    annotations={
        "title": "Get Low Stock Alerts",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def get_low_stock_alerts(params: GetLowStockAlertsInput) -> str:
    """
    Return all SKUs where stock is below the configured threshold.

    This tool scans inventory across specified platforms (1688, Amazon, or both)
    and returns products that have stock levels below the threshold, helping
    prevent overselling and identify products that need restocking.

    Args:
        params (GetLowStockAlertsInput): Validated input containing:
            - threshold (Optional[int]): Custom stock threshold (default from .env or 10)
            - platform (Optional[str]): Filter by platform - '1688', 'Amazon', or 'both'
            - response_format (ResponseFormat): Output format - 'markdown' or 'json'

    Returns:
        str: JSON or markdown formatted alert report containing:
            - threshold_used: Stock threshold that triggered alerts
            - total_alerts: Number of products below threshold
            - alerts: Array of alert objects with:
                - sku: Product SKU
                - product_name: Name of the product
                - platform: Where the low stock was detected
                - current_stock: Current stock level
                - shortage: How many units below threshold
                - severity: "critical" (<5), "warning" (5-10), "low" (>10)
                - supplier: Supplier name (for 1688)
                - asin: Amazon ASIN (for Amazon listings)

    Error Handling:
        - Returns partial results if one platform API fails
        - Returns error message if no API credentials configured
        - Returns empty result if no products below threshold

    Note:
        For 1688, this uses the default product list endpoint. For Amazon,
        it checks both FBA and MFN inventory where accessible.
    """
    threshold = params.threshold or LOW_STOCK_THRESHOLD
    alerts = []

    platforms_to_check = []
    if params.platform in [None, "both", "1688"]:
        platforms_to_check.append("1688")
    if params.platform in [None, "both", "Amazon"]:
        platforms_to_check.append("Amazon")

    for platform in platforms_to_check:
        try:
            if platform == "1688":
                products = await _fetch_1688_all_inventory()
                for product in products:
                    stock = product.get("availableQuantity", 0)
                    if stock < threshold:
                        shortage = threshold - stock
                        if stock < 5:
                            severity = "critical"
                        elif stock < 10:
                            severity = "warning"
                        else:
                            severity = "low"

                        alerts.append({
                            "sku": product.get("sku", "Unknown"),
                            "product_name": product.get("productName", "Unknown"),
                            "platform": "1688",
                            "current_stock": stock,
                            "threshold": threshold,
                            "shortage": shortage,
                            "severity": severity,
                            "supplier": product.get("supplierName", "N/A"),
                            "asin": None,
                        })
            else:
                listings = await _fetch_amazon_listings()
                for item in listings:
                    stock = item.get("availability", {}).get("quantity", 0)
                    if stock < threshold:
                        shortage = threshold - stock
                        if stock < 5:
                            severity = "critical"
                        elif stock < 10:
                            severity = "warning"
                        else:
                            severity = "low"

                        alerts.append({
                            "sku": item.get("sku", "Unknown"),
                            "product_name": item.get("summaries", [{}])[0].get("itemName", "Unknown"),
                            "platform": "Amazon",
                            "current_stock": stock,
                            "threshold": threshold,
                            "shortage": shortage,
                            "severity": severity,
                            "supplier": None,
                            "asin": item.get("asin", "N/A"),
                        })
        except Exception as e:
            error_msg = f"Warning: Could not fetch {platform} inventory - {str(e)}"
            alerts.append({
                "error": error_msg,
                "platform": platform,
            })

    critical_count = sum(1 for a in alerts if a.get("severity") == "critical")
    warning_count = sum(1 for a in alerts if a.get("severity") == "warning")

    result = {
        "threshold_used": threshold,
        "total_alerts": len([a for a in alerts if "error" not in a]),
        "critical_count": critical_count,
        "warning_count": warning_count,
        "platforms_checked": platforms_to_check,
        "alerts": sorted(alerts, key=lambda x: x.get("severity", "error") != "error" and x.get("current_stock", 999)),
    }

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(result, indent=2, ensure_ascii=False)
    else:
        severity_icons = {"critical": "🔴", "warning": "🟡", "low": "🟢", "error": "⚠️"}
        lines = [
            f"# Low Stock Alerts (Threshold: {threshold})",
            "",
            f"**Total Alerts**: {result['total_alerts']}",
            f"- 🔴 Critical (<5): {critical_count}",
            f"- 🟡 Warning (5-10): {warning_count}",
            "",
            "## Alerts",
            "",
        ]

        for alert in alerts:
            if "error" in alert:
                lines.append(f"⚠️ **{alert['platform']}**: {alert['error']}")
                lines.append("")
            else:
                icon = severity_icons.get(alert["severity"], "•")
                lines.append(f"{icon} **{alert['sku']}** ({alert['platform']})")
                lines.append(f"   - Product: {alert['product_name']}")
                lines.append(f"   - Current Stock: {alert['current_stock']} (need {alert['shortage']} more)")
                lines.append(f"   - Severity: {alert['severity']}")
                if alert.get("supplier"):
                    lines.append(f"   - Supplier: {alert['supplier']}")
                if alert.get("asin"):
                    lines.append(f"   - ASIN: {alert['asin']}")
                lines.append("")

        return "\n".join(lines)


@mcp.tool(
    name="get_product_cost_1688",
    annotations={
        "title": "Get 1688 Product Cost",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@require_feature("get_product_cost_1688")
async def get_product_cost_1688(params: GetProductCost1688Input) -> str:
    """
    Get product cost and pricing information from 1688 supplier platform.

    This tool retrieves the current product price, MOQ (Minimum Order Quantity),
    and supplier pricing details from 1688.com.

    Args:
        params (GetProductCost1688Input): Validated input containing:
            - sku (str): Product SKU identifier (e.g., "SKU-12345")
            - response_format (ResponseFormat): Output format - 'markdown' or 'json'

    Returns:
        str: JSON or markdown formatted price data containing:
            - sku: Product SKU
            - product_name: Name of the product
            - price_cny: Price in Chinese Yuan (CNY)
            - price_usd: Estimated price in USD
            - moq: Minimum Order Quantity
            - supplier_info: Supplier details
            - last_updated: Timestamp of price update

    Error Handling:
        - Returns error message if API authentication fails (401)
        - Returns error message if SKU not found (404)
        - Returns error message if rate limited (429)
    """
    try:
        data = await _fetch_1688_product_details(params.sku)
        exchange_rate = _get_currency_rate()

        price_data = {
            "sku": params.sku,
            "product_name": data.get("productName", "Unknown Product"),
            "price_cny": data.get("price", 0),
            "price_usd": round(data.get("price", 0) / exchange_rate, 2),
            "moq": data.get("moq", 1),
            "supplier_info": {
                "name": data.get("supplierName", "N/A"),
                "location": data.get("supplierLocation", "N/A"),
            },
            "last_updated": data.get("lastUpdated", datetime.now().isoformat()),
        }

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(price_data, indent=2, ensure_ascii=False)
        else:
            lines = [
                f"# 1688 Product Cost: {params.sku}",
                "",
                f"**Product Name**: {price_data['product_name']}",
                f"**Price (CNY)**: ¥{price_data['price_cny']}",
                f"**Price (USD)**: ${price_data['price_usd']}",
                f"**MOQ**: {price_data['moq']} units",
                "",
                "### Supplier Info",
                f"- **Name**: {price_data['supplier_info']['name']}",
                f"- **Location**: {price_data['supplier_info']['location']}",
                "",
                f"_Last updated: {price_data['last_updated']}_",
            ]
            return "\n".join(lines)

    except Exception as e:
        return _handle_api_error(e, "1688")


@mcp.tool(
    name="calculate_amazon_price",
    annotations={
        "title": "Calculate Amazon Price",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@require_feature("calculate_amazon_price")
async def calculate_amazon_price(params: CalculateAmazonPriceInput) -> str:
    """
    Calculate recommended Amazon selling price based on 1688 cost.

    This tool calculates an optimal Amazon selling price by factoring in:
    - Product cost from 1688 (in CNY)
    - Currency exchange rate (CNY to USD)
    - Amazon referral fees (default 15%)
    - Shipping cost from China to warehouse
    - Target profit margin

    Args:
        params (CalculateAmazonPriceInput): Validated input containing:
            - sku (str): Product SKU identifier
            - cost_cny (Optional[float]): Product cost in CNY (fetches from 1688 if not provided)
            - target_margin_percent (float): Target profit margin (default: 25%)
            - shipping_cost_usd (float): Shipping cost per unit in USD (default: $2.00)
            - response_format (ResponseFormat): Output format - 'markdown' or 'json'

    Returns:
        str: JSON or markdown formatted calculation containing:
            - sku: Product SKU
            - cost_breakdown: All cost components
            - recommended_price_usd: Suggested selling price
            - actual_profit_usd: Expected profit per unit
            - actual_margin_percent: Actual margin achieved
            - price_tiers: Suggested pricing for different strategies

    Error Handling:
        - Returns error if cost cannot be determined
        - Handles API failures gracefully
    """
    try:
        cost_cny = params.cost_cny

        if cost_cny is None:
            product_data = await _fetch_1688_product_details(params.sku)
            cost_cny = product_data.get("price", 0)
            product_name = product_data.get("productName", params.sku)
        else:
            product_name = params.sku

        exchange_rate = _get_currency_rate()
        amazon_fee_percent = _get_amazon_fees()

        calculation = _calculate_recommended_price(
            cost_cny=cost_cny,
            exchange_rate=exchange_rate,
            amazon_fee_percent=amazon_fee_percent,
            shipping_cost_usd=params.shipping_cost_usd,
            target_margin_percent=params.target_margin_percent,
        )

        result = {
            "sku": params.sku,
            "product_name": product_name,
            "calculation": calculation,
            "price_tiers": {
                "budget": round(calculation["recommended_price_usd"] * 0.9, 2),
                "standard": calculation["recommended_price_usd"],
                "premium": round(calculation["recommended_price_usd"] * 1.15, 2),
            },
            "calculated_at": datetime.now().isoformat(),
        }

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(result, indent=2, ensure_ascii=False)
        else:
            lines = [
                f"# Amazon Price Calculator: {params.sku}",
                "",
                f"**Product Name**: {product_name}",
                "",
                "## Cost Breakdown",
                f"| Item | Amount |",
                f"|------|--------|",
                f"| 1688 Cost | ¥{calculation['cost_cny']} (${calculation['cost_usd']}) |",
                f"| Shipping | ${calculation['shipping_cost_usd']} |",
                f"| Subtotal | ${calculation['subtotal_usd']} |",
                f"| Amazon Fees ({calculation['amazon_fee_percent']}%) | ${calculation['amazon_fee_amount']} |",
                f"| **Total Cost** | **${calculation['total_cost_usd']}** |",
                "",
                "## Pricing Strategy",
                f"| Tier | Price |",
                f"|------|-------|",
                f"| Budget (-10%) | ${result['price_tiers']['budget']} |",
                f"| Standard | ${result['price_tiers']['standard']} |",
                f"| Premium (+15%) | ${result['price_tiers']['premium']} |",
                "",
                f"**Recommended Price**: ${calculation['recommended_price_usd']}",
                f"**Expected Profit**: ${calculation['actual_profit_usd']} ({calculation['actual_margin_percent']}% margin)",
                "",
                f"_Calculated at: {result['calculated_at']}_",
            ]
            return "\n".join(lines)

    except Exception as e:
        return _handle_api_error(e, "price calculation")


@mcp.tool(
    name="sync_price",
    annotations={
        "title": "Sync Price",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@require_feature("sync_price")
async def sync_price(params: SyncPriceInput) -> str:
    """
    Compare 1688 cost-based pricing against current Amazon prices and flag mismatches.

    This tool retrieves product costs from 1688, calculates the recommended Amazon
    price based on your margin targets, and compares it against the current Amazon
    listing price to identify pricing opportunities or risks.

    Args:
        params (SyncPriceInput): Validated input containing:
            - sku (str): Product SKU to sync pricing
            - target_margin_percent (float): Target profit margin (default: 25%)
            - shipping_cost_usd (float): Shipping cost per unit in USD (default: $2.00)
            - response_format (ResponseFormat): Output format - 'markdown' or 'json'

    Returns:
        str: JSON or markdown formatted sync report containing:
            - sku: Product SKU
            - source_platform: "1688"
            - source_price_cny: 1688 cost in CNY
            - source_price_usd: 1688 cost converted to USD
            - target_platform: "Amazon"
            - target_current_price: Current Amazon listing price
            - recommended_price: Suggested Amazon price
            - price_difference: Absolute difference
            - price_difference_percent: Percentage difference
            - action: "KEEP_CURRENT", "INCREASE_PRICE", or "DECREASE_PRICE"
            - profit_impact: Potential profit change
            - last_checked: Timestamp of comparison

    Error Handling:
        - Returns error message if 1688 cost cannot be fetched
        - Gracefully handles missing Amazon listing
        - Returns partial results if one platform fails
    """
    try:
        product_data = await _fetch_1688_product_details(params.sku)
        cost_cny = product_data.get("price", 0)
        product_name = product_data.get("productName", params.sku)

        exchange_rate = _get_currency_rate()
        amazon_fee_percent = _get_amazon_fees()

        calculation = _calculate_recommended_price(
            cost_cny=cost_cny,
            exchange_rate=exchange_rate,
            amazon_fee_percent=amazon_fee_percent,
            shipping_cost_usd=params.shipping_cost_usd,
            target_margin_percent=params.target_margin_percent,
        )

        try:
            amazon_data = await _fetch_amazon_product_price(params.sku)
            pricing = amazon_data.get("pricing", {})
            if isinstance(pricing, list) and len(pricing) > 0:
                current_price = pricing[0].get("landedPrice", {}).get("amount", 0)
            else:
                current_price = amazon_data.get("pricing", {}).get("landedPrice", {}).get("amount", 0)
            amazon_status = "available"
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                current_price = 0
                amazon_status = "not_listed"
            else:
                raise
        except Exception:
            current_price = 0
            amazon_status = "unavailable"

        if amazon_status == "not_listed":
            action = "CREATE_LISTING"
            recommendation = f"Create Amazon listing with price ${calculation['recommended_price_usd']}"
        elif amazon_status == "unavailable":
            action = "CHECK_AMAZON"
            recommendation = "Unable to fetch Amazon price. Manual check required."
        else:
            action = _get_price_action(current_price, calculation["recommended_price_usd"])
            diff = calculation["recommended_price_usd"] - current_price
            diff_percent = (diff / current_price * 100) if current_price > 0 else 0

            if action == "KEEP_CURRENT":
                recommendation = "Current price is optimal. No changes needed."
            elif action == "INCREASE_PRICE":
                recommendation = f"Increase price by ${abs(diff):.2f} ({abs(diff_percent):.1f}%) to maximize profit."
            else:
                recommendation = f"DECREASE price by ${abs(diff):.2f} ({abs(diff_percent):.1f}%) to maintain target margin."

        sync_result = {
            "sku": params.sku,
            "product_name": product_name,
            "source_platform": "1688",
            "source_price_cny": cost_cny,
            "source_price_usd": calculation["cost_usd"],
            "target_platform": "Amazon",
            "target_current_price": current_price,
            "amazon_listing_status": amazon_status,
            "recommended_price_usd": calculation["recommended_price_usd"],
            "price_difference": round(abs(calculation["recommended_price_usd"] - current_price), 2) if current_price > 0 else calculation["recommended_price_usd"],
            "action": action,
            "recommendation": recommendation,
            "profit_analysis": {
                "current_profit": round(current_price - calculation["total_cost_usd"], 2) if current_price > 0 else 0,
                "recommended_profit": calculation["actual_profit_usd"],
                "profit_change": round(calculation["actual_profit_usd"] - (current_price - calculation["total_cost_usd"]), 2) if current_price > 0 else calculation["actual_profit_usd"],
            },
            "last_checked": datetime.now().isoformat(),
        }

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(sync_result, indent=2, ensure_ascii=False)
        else:
            action_icons = {
                "KEEP_CURRENT": "✓",
                "INCREASE_PRICE": "↑",
                "DECREASE_PRICE": "↓",
                "CREATE_LISTING": "✚",
                "CHECK_AMAZON": "⚠️",
            }
            icon = action_icons.get(sync_result["action"], "•")
            lines = [
                f"# Price Sync Report: {params.sku} [{icon}]",
                "",
                f"**Product**: {product_name}",
                "",
                "## Pricing Comparison",
                f"| Source | Price (USD) |",
                f"|---------|-------------|",
                f"| 1688 Cost | ${calculation['cost_usd']} |",
                f"| Current Amazon | ${current_price if current_price > 0 else 'N/A'} |",
                f"| **Recommended** | **${calculation['recommended_price_usd']}** |",
                "",
                f"**Action**: {icon} {sync_result['action']}",
                "",
                f"## Recommendation",
                f"{sync_result['recommendation']}",
                "",
                "## Profit Analysis",
                f"- Current Profit: ${sync_result['profit_analysis']['current_profit']}",
                f"- Recommended Profit: ${sync_result['profit_analysis']['recommended_profit']}",
                f"- Change: ${sync_result['profit_analysis']['profit_change']}",
                "",
                f"_Last checked: {sync_result['last_checked']}_",
            ]
            return "\n".join(lines)

    except Exception as e:
        return _handle_api_error(e, "1688/Amazon price sync")


@mcp.tool(
    name="update_amazon_price",
    annotations={
        "title": "Update Amazon Price",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@require_feature("update_amazon_price")
async def update_amazon_price(params: UpdateAmazonPriceInput) -> str:
    """
    Update the listing price on Amazon Seller Central.

    This tool updates the pricing for a specific SKU on Amazon, allowing
    you to adjust prices based on sync_price recommendations or market conditions.

    Args:
        params (UpdateAmazonPriceInput): Validated input containing:
            - sku (str): Product SKU identifier
            - new_price (float): New price in USD (must be > 0)
            - currency (str): Currency code (default: USD)

    Returns:
        str: JSON formatted confirmation containing:
            - success: Boolean indicating operation result
            - sku: The updated SKU
            - previous_price: Price before update (if available)
            - new_price: The new price
            - updated_at: Timestamp of the update
            - message: Confirmation message

    Error Handling:
        - Returns error message if API authentication fails (401)
        - Returns error message if SKU not found (404)
        - Returns error message if price validation fails (400)
        - Returns error message if rate limited (429)

    Note:
        Amazon may take some time to reflect price changes on the frontend.
        Check the listing after a few minutes to confirm the update.
    """
    try:
        headers = _get_amazon_headers()
        async with httpx.AsyncClient(timeout=30.0) as client:
            get_response = await client.get(
                f"{AMAZON_BASE_URL}/catalog/2022-04-01/items/{params.sku}",
                headers=headers,
                params={"marketplaceIds": os.getenv("AMAZON_MARKETPLACE_ID", "ATVPDKIKX0DER")},
            )
            previous_price = 0
            if get_response.status_code == 200:
                amazon_data = get_response.json()
                pricing = amazon_data.get("pricing", {})
                if isinstance(pricing, list) and len(pricing) > 0:
                    previous_price = pricing[0].get("landedPrice", {}).get("amount", 0)
                else:
                    previous_price = pricing.get("landedPrice", {}).get("amount", 0)

            put_response = await client.put(
                f"{AMAZON_BASE_URL}/listings/2022-04-01/items/{params.sku}",
                headers=headers,
                json={
                    "sku": params.sku,
                    "pricing": {
                        "landedPrice": {
                            "amount": params.new_price,
                            "currencyCode": params.currency,
                        }
                    },
                },
            )

            if put_response.status_code in [200, 201]:
                result = {
                    "success": True,
                    "sku": params.sku,
                    "previous_price": previous_price if previous_price > 0 else None,
                    "new_price": params.new_price,
                    "currency": params.currency,
                    "updated_at": datetime.now().isoformat(),
                    "message": f"Price updated from ${previous_price} to ${params.new_price}",
                }
            else:
                result = {
                    "success": False,
                    "sku": params.sku,
                    "error_code": put_response.status_code,
                    "message": f"Failed to update price: {put_response.text}",
                }

            return json.dumps(result, indent=2, ensure_ascii=False)

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400:
            return json.dumps({
                "success": False,
                "sku": params.sku,
                "error": "Invalid price value",
                "message": "Price must be a positive number. Check the value and try again.",
            }, indent=2)
        return _handle_api_error(e, "Amazon")
    except Exception as e:
        return _handle_api_error(e, "Amazon")


@mcp.tool(
    name="get_competitor_prices",
    annotations={
        "title": "Get Competitor Prices",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@require_feature("get_competitor_prices")
async def get_competitor_prices(params: GetCompetitorPricesInput) -> str:
    """
    Search Amazon for competitor product prices.

    This tool searches Amazon's catalog for similar products to help you
    understand the competitive landscape and adjust your pricing strategy
    accordingly.

    Args:
        params (GetCompetitorPricesInput): Validated input containing:
            - sku (str): SKU or search keyword to find competitors
            - limit (int): Maximum number of competitors to return (1-20)
            - response_format (ResponseFormat): Output format - 'markdown' or 'json'

    Returns:
        str: JSON or markdown formatted competitor data containing:
            - search_term: The search keyword used
            - total_found: Number of competitors found
            - competitors: Array of competitor products with:
                - asin: Amazon ASIN
                - title: Product title
                - price: Current price
                - category: Product category
                - rating: Customer rating (if available)
                - review_count: Number of reviews
            - price_range: Low, average, and high prices
            - recommendation: Suggested pricing strategy

    Error Handling:
        - Returns empty result if no competitors found
        - Returns error message if search fails
        - Handles rate limiting gracefully
    """
    try:
        competitors = []
        search_results = await _search_amazon_competitors(params.sku)

        items = search_results.get("items", [])
        for item in items[:params.limit]:
            summaries = item.get("summaries", [{}])
            summary = summaries[0] if summaries else {}

            pricing = item.get("pricing", {})
            if isinstance(pricing, list) and len(pricing) > 0:
                price = pricing[0].get("landedPrice", {}).get("amount", 0)
            else:
                price = pricing.get("landedPrice", {}).get("amount", 0)

            competitors.append({
                "asin": item.get("asin", "N/A"),
                "title": summary.get("itemName", "Unknown Product"),
                "price": price if price > 0 else None,
                "category": summary.get("productCategory", {}).get("displayName", "N/A"),
                "rating": item.get("attributes", {}).get("customer_review_average", None),
                "review_count": item.get("attributes", {}).get("customer_review_count", 0),
            })

        prices = [c["price"] for c in competitors if c["price"] is not None]

        result = {
            "search_term": params.sku,
            "total_found": len(competitors),
            "competitors": competitors,
            "price_range": {
                "lowest": min(prices) if prices else None,
                "average": round(sum(prices) / len(prices), 2) if prices else None,
                "highest": max(prices) if prices else None,
            },
            "analyzed_at": datetime.now().isoformat(),
        }

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(result, indent=2, ensure_ascii=False)
        else:
            lines = [
                f"# Competitor Analysis: {params.sku}",
                "",
                f"**Competitors Found**: {len(competitors)}",
                "",
                "## Price Range",
                f"- **Lowest**: ${result['price_range']['lowest']}" if result['price_range']['lowest'] else "- **Lowest**: N/A",
                f"- **Average**: ${result['price_range']['average']}" if result['price_range']['average'] else "- **Average**: N/A",
                f"- **Highest**: ${result['price_range']['highest']}" if result['price_range']['highest'] else "- **Highest**: N/A",
                "",
                "## Competitors",
                "",
            ]

            for i, comp in enumerate(competitors, 1):
                lines.append(f"### {i}. {comp['title'][:60]}...")
                lines.append(f"- **ASIN**: {comp['asin']}")
                if comp['price']:
                    lines.append(f"- **Price**: ${comp['price']}")
                else:
                    lines.append(f"- **Price**: N/A")
                if comp['rating']:
                    lines.append(f"- **Rating**: {comp['rating']}/5 ({comp['review_count']} reviews)")
                lines.append("")

            return "\n".join(lines)

    except Exception as e:
        return _handle_api_error(e, "Amazon competitor search")


@mcp.tool(
    name="get_product_reviews",
    annotations={
        "title": "Get Product Reviews",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@require_feature("get_product_reviews")
async def get_product_reviews(params: GetProductReviewsInput) -> str:
    """
    Get product reviews from Amazon for a specific SKU or ASIN.

    This tool retrieves reviews including ratings, text, dates, and reviewer info.
    Supports filtering by rating level and date range.

    Args:
        params (GetProductReviewsInput): Validated input containing:
            - sku (str): SKU or ASIN to fetch reviews for
            - days (int): Number of days to look back (default: 30)
            - min_rating (Optional[int]): Filter by minimum rating (1-5)
            - max_rating (Optional[int]): Filter by maximum rating (1-5)
            - limit (int): Maximum reviews to return (default: 20)
            - response_format (ResponseFormat): Output format - 'markdown' or 'json'

    Returns:
        str: JSON or markdown formatted review data containing:
            - sku: Product SKU/ASIN
            - total_reviews: Number of reviews retrieved
            - average_rating: Calculated average rating
            - reviews: Array of review objects with:
                - review_id: Unique review identifier
                - rating: Star rating (1-5)
                - title: Review headline
                - text: Full review text
                - reviewer: Reviewer name/identifier
                - date: Review date
                - verified: Whether purchase was verified
                - helpful_votes: Number of helpful votes

    Error Handling:
        - Returns empty result if no reviews found
        - Returns error message if API fails
        - Handles rate limiting gracefully
    """
    try:
        reviews_data = await _fetch_amazon_reviews(params.sku, params.days, params.limit)

        all_reviews = reviews_data.get("reviews", [])
        filtered_reviews = []

        cutoff_date = datetime.now() - timedelta(days=params.days)

        for review in all_reviews:
            review_date = _parse_review_date(review.get("date", ""))
            if review_date and review_date < cutoff_date:
                continue

            rating = review.get("rating", 0)

            if params.min_rating and rating < params.min_rating:
                continue
            if params.max_rating and rating > params.max_rating:
                continue

            severity = _get_rating_severity(rating)

            filtered_reviews.append({
                "review_id": review.get("reviewId", "N/A"),
                "rating": rating,
                "rating_severity": severity,
                "title": review.get("title", "No title"),
                "text": review.get("text", ""),
                "reviewer": review.get("reviewerName", "Anonymous"),
                "date": _format_review_date(review.get("date", "")),
                "verified": review.get("verifiedPurchase", False),
                "helpful_votes": review.get("helpfulVotes", 0),
            })

        filtered_reviews.sort(key=lambda x: x["date"], reverse=True)
        filtered_reviews = filtered_reviews[:params.limit]

        ratings = [r["rating"] for r in filtered_reviews]
        avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else 0

        result = {
            "sku": params.sku,
            "total_reviews": len(filtered_reviews),
            "average_rating": avg_rating,
            "reviews": filtered_reviews,
            "queried_at": datetime.now().isoformat(),
        }

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(result, indent=2, ensure_ascii=False)
        else:
            lines = [
                f"# Product Reviews: {params.sku}",
                "",
                f"**Total Reviews**: {len(filtered_reviews)}",
                f"**Average Rating**: {avg_rating}/5",
                "",
                "## Reviews",
                "",
            ]

            for i, review in enumerate(filtered_reviews, 1):
                stars = "⭐" * review["rating"]
                lines.append(f"### {i}. {stars} ({review['rating']}/5) - {review['date']}")
                lines.append(f"**{review['title']}**")
                lines.append(f"By: {review['reviewer']} {'✓ Verified' if review['verified'] else ''}")
                lines.append(f"Helpful: {review['helpful_votes']} votes")
                lines.append(f"{review['text'][:200]}..." if len(review['text']) > 200 else review['text'])
                lines.append("")

            return "\n".join(lines)

    except Exception as e:
        return _handle_api_error(e, "Amazon reviews")


@mcp.tool(
    name="get_negative_reviews",
    annotations={
        "title": "Get Negative Reviews",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@require_feature("get_negative_reviews")
async def get_negative_reviews(params: GetNegativeReviewsInput) -> str:
    """
    Get 1-2 star reviews that need attention and response.

    This tool retrieves negative reviews (1-2 stars) that require seller attention,
    including analysis of potential supplier quality issues.

    Args:
        params (GetNegativeReviewsInput): Validated input containing:
            - sku (Optional[str]): Filter by specific SKU (omit for all products)
            - days (int): Number of days to look back (default: 7)
            - severity (str): Filter by severity - 'critical' (1 star), 'warning' (2 stars), or 'all'
            - response_format (ResponseFormat): Output format - 'markdown' or 'json'

    Returns:
        str: JSON or markdown formatted negative review data containing:
            - total_negative: Total number of negative reviews
            - critical_count: Number of 1-star reviews
            - warning_count: Number of 2-star reviews
            - reviews: Array of negative reviews with:
                - review details (rating, title, text, date)
                - severity: 'critical' or 'warning'
                - supplier_issues: Array of detected supplier quality issues
                - action_required: Suggested action to take

    Error Handling:
        - Returns empty result if no negative reviews found
        - Returns partial results if some APIs fail
    """
    try:
        reviews_data = await _fetch_amazon_reviews(params.sku or "", params.days)

        all_reviews = reviews_data.get("reviews", [])
        negative_reviews = []

        cutoff_date = datetime.now() - timedelta(days=params.days)

        for review in all_reviews:
            review_date = _parse_review_date(review.get("date", ""))
            if review_date and review_date < cutoff_date:
                continue

            rating = review.get("rating", 0)
            severity = _get_rating_severity(rating)

            if severity not in ["critical", "warning"]:
                continue

            if params.severity == "critical" and severity != "critical":
                continue
            if params.severity == "warning" and severity != "warning":
                continue

            review_text = review.get("text", "") + " " + review.get("title", "")
            supplier_issues = _analyze_review_for_supplier_issues(review_text)

            negative_reviews.append({
                "review_id": review.get("reviewId", "N/A"),
                "sku": review.get("sku", params.sku or "Unknown"),
                "rating": rating,
                "severity": severity,
                "title": review.get("title", "No title"),
                "text": review.get("text", ""),
                "reviewer": review.get("reviewerName", "Anonymous"),
                "date": _format_review_date(review.get("date", "")),
                "verified": review.get("verifiedPurchase", False),
                "supplier_issues": supplier_issues,
                "has_supplier_issues": len(supplier_issues) > 0,
            })

        negative_reviews.sort(key=lambda x: (0 if x["severity"] == "critical" else 1, x["date"]), reverse=True)

        critical_count = sum(1 for r in negative_reviews if r["severity"] == "critical")
        warning_count = sum(1 for r in negative_reviews if r["severity"] == "warning")

        result = {
            "total_negative": len(negative_reviews),
            "critical_count": critical_count,
            "warning_count": warning_count,
            "days_queried": params.days,
            "reviews": negative_reviews,
            "queried_at": datetime.now().isoformat(),
        }

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(result, indent=2, ensure_ascii=False)
        else:
            severity_icons = {"critical": "🔴", "warning": "🟡"}
            lines = [
                f"# Negative Reviews (Last {params.days} Days)",
                "",
                f"**Total Negative Reviews**: {len(negative_reviews)}",
                f"- 🔴 Critical (1-star): {critical_count}",
                f"- 🟡 Warning (2-star): {warning_count}",
                "",
                "## Reviews",
                "",
            ]

            for i, review in enumerate(negative_reviews, 1):
                icon = severity_icons.get(review["severity"], "•")
                lines.append(f"### {i}. {icon} {review['severity'].upper()} - {review['date']}")
                lines.append(f"**Rating**: {review['rating']}/5 stars")
                lines.append(f"**{review['title']}**")
                lines.append(f"By: {review['reviewer']} {'✓ Verified' if review['verified'] else ''}")
                lines.append(f"{review['text'][:300]}..." if len(review['text']) > 300 else review['text'])

                if review["has_supplier_issues"]:
                    lines.append("")
                    lines.append("⚠️ **Potential Supplier Issues Detected:**")
                    for issue in review["supplier_issues"]:
                        lines.append(f"  - [{issue['severity'].upper()}] {issue['category']}: \"{issue['keyword']}\"")

                lines.append("")

            return "\n".join(lines)

    except Exception as e:
        return _handle_api_error(e, "Amazon negative reviews")


@mcp.tool(
    name="get_review_alerts",
    annotations={
        "title": "Get Review Alerts",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@require_feature("get_review_alerts")
async def get_review_alerts(params: GetReviewAlertsInput) -> str:
    """
    Get actionable alerts for reviews that need immediate attention.

    This tool analyzes recent reviews and generates prioritized alerts with
    specific action recommendations. It flags both critical customer issues
    and potential supplier quality problems.

    Args:
        params (GetReviewAlertsInput): Validated input containing:
            - days (int): Number of days to look back (default: 7)
            - include_supplier_flags (bool): Enable supplier quality issue detection (default: True)
            - response_format (ResponseFormat): Output format - 'markdown' or 'json'

    Returns:
        str: JSON or markdown formatted alert report containing:
            - total_alerts: Total number of actionable alerts
            - priority_breakdown: Count by priority (critical, high, medium)
            - alerts: Array of actionable alerts with:
                - alert_type: Type of alert (critical_review, supplier_issue, response_needed, etc.)
                - priority: 'critical', 'high', 'medium'
                - sku: Related SKU
                - review_summary: Brief description of the review
                - action_required: Specific action to take
                - response_template: Suggested response for customer

    Alert Types:
        - critical_review: 1-star review requiring immediate response
        - supplier_issue: Review mentioning quality/defect issues
        - response_needed: Any negative review not yet responded to
        - safety_concern: Review mentioning safety issues

    Error Handling:
        - Returns empty result if no alerts
        - Returns partial results if some APIs fail
    """
    try:
        reviews_data = await _fetch_amazon_reviews("", params.days)

        all_reviews = reviews_data.get("reviews", [])
        alerts = []

        cutoff_date = datetime.now() - timedelta(days=params.days)

        for review in all_reviews:
            review_date = _parse_review_date(review.get("date", ""))
            if review_date and review_date < cutoff_date:
                continue

            rating = review.get("rating", 0)
            severity = _get_rating_severity(rating)
            review_text = review.get("text", "") + " " + review.get("title", "")
            sku = review.get("sku", "Unknown")

            if params.include_supplier_flags:
                supplier_issues = _analyze_review_for_supplier_issues(review_text)

                if supplier_issues:
                    for issue in supplier_issues:
                        alert_type = "supplier_issue"
                        priority = "critical" if issue["severity"] == "high" else "high"

                        response_templates = {
                            "defective": f"Dear Customer, we're sorry your {sku} arrived defective. We're investigating with our supplier and would like to send a replacement or full refund. Please contact us directly.",
                            "quality": f"Dear Customer, thank you for your feedback on {sku}. We're sorry the quality didn't meet expectations. We're reviewing our supplier quality control and would like to make this right - please contact us.",
                            "packaging": f"Dear Customer, we apologize that {sku} arrived with packaging issues. We'll address this with our supplier immediately. Please reach out for a replacement or refund.",
                            "inconsistent": f"Dear Customer, we're sorry {sku} didn't match expectations. We understand the importance of accurate listings. Please contact us to resolve this.",
                            "safety": f"URGENT: Dear Customer, we've received your safety concern about {sku}. Your safety is our priority. Please stop using immediately and contact us for a full refund and to discuss this further.",
                        }

                        alerts.append({
                            "alert_type": alert_type,
                            "priority": priority,
                            "sku": sku,
                            "rating": rating,
                            "review_date": _format_review_date(review.get("date", "")),
                            "issue_category": issue["category"],
                            "issue_keyword": issue["keyword"],
                            "review_summary": review.get("title", "No title")[:100],
                            "action_required": f"Contact supplier about {issue['category']} issue. Consider quality audit.",
                            "response_template": response_templates.get(issue["category"], "Please contact us to resolve this issue."),
                            "urgency": "immediate" if issue["severity"] == "high" else "soon",
                        })

            if severity in ["critical", "warning"]:
                alert_type = "critical_review" if severity == "critical" else "response_needed"

                alerts.append({
                    "alert_type": alert_type,
                    "priority": severity,
                    "sku": sku,
                    "rating": rating,
                    "review_date": _format_review_date(review.get("date", "")),
                    "review_summary": review.get("title", "No title")[:100],
                    "review_text": review.get("text", "")[:200],
                    "action_required": "Respond to customer within 24 hours" if severity == "critical" else "Consider responding",
                    "response_template": f"Dear {review.get('reviewerName', 'Customer')}, we apologize for your experience with {sku}. We'd like to make this right. Please contact us directly so we can resolve this issue.",
                    "urgency": "immediate" if severity == "critical" else "soon",
                })

        alerts.sort(key=lambda x: (0 if x["priority"] == "critical" else 1 if x["priority"] == "high" else 2, x["urgency"] == "soon"))
        alerts = alerts[:50]

        critical_count = sum(1 for a in alerts if a["priority"] == "critical")
        high_count = sum(1 for a in alerts if a["priority"] == "high")
        medium_count = sum(1 for a in alerts if a["priority"] in ["info", "positive"])

        result = {
            "total_alerts": len(alerts),
            "priority_breakdown": {
                "critical": critical_count,
                "high": high_count,
                "medium": medium_count,
            },
            "days_queried": params.days,
            "alerts": alerts,
            "generated_at": datetime.now().isoformat(),
        }

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(result, indent=2, ensure_ascii=False)
        else:
            priority_icons = {"critical": "🔴 CRITICAL", "high": "🟡 HIGH", "medium": "🟢 MEDIUM"}
            lines = [
                f"# Review Alerts (Last {params.days} Days)",
                "",
                f"**Total Alerts**: {len(alerts)}",
                f"- 🔴 Critical: {critical_count}",
                f"- 🟡 High: {high_count}",
                f"- 🟢 Medium: {medium_count}",
                "",
                "## Actionable Alerts",
                "",
            ]

            for i, alert in enumerate(alerts, 1):
                icon = priority_icons.get(alert["priority"], "•")
                lines.append(f"### {i}. {icon} | {alert['alert_type'].upper().replace('_', ' ')}")

                if alert.get("sku"):
                    lines.append(f"**SKU**: {alert['sku']}")
                if alert.get("rating"):
                    lines.append(f"**Rating**: {alert['rating']} stars")
                if alert.get("review_date"):
                    lines.append(f"**Date**: {alert['review_date']}")

                if alert.get("issue_category"):
                    lines.append(f"**Issue Type**: {alert['issue_category']}")

                if alert.get("review_summary"):
                    lines.append(f"**Summary**: {alert['review_summary']}")

                lines.append("")
                lines.append(f"⚡ **Action Required**: {alert['action_required']}")
                lines.append("")
                lines.append(f"📝 **Suggested Response**:\n> {alert['response_template']}")
                lines.append("")

            return "\n".join(lines)

    except Exception as e:
        return _handle_api_error(e, "Amazon review alerts")


@mcp.tool(
    name="calculate_true_profit",
    annotations={
        "title": "Calculate True Profit",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@require_feature("calculate_true_profit")
async def calculate_true_profit(params: CalculateTrueProfitInput) -> str:
    """
    Calculate TRUE profit for a product including ALL cross-border cost factors.
    
    This comprehensive calculator includes:
    - Product cost from 1688
    - Shipping to Amazon
    - Amazon referral fees
    - FBA fulfillment fees
    - Storage fees
    - Advertising costs (ACoS)
    - Payment processing fees
    - Return costs
    - Customs duties
    - Overhead expenses
    
    Args:
        params (CalculateTrueProfitInput): Validated input containing all cost parameters
        
    Returns:
        str: Detailed profit analysis in JSON or markdown format
    """
    try:
        # Get product cost if not provided
        cost_cny = params.cost_cny
        product_name = params.sku
        
        if cost_cny is None:
            product_data = await _fetch_1688_product_details(params.sku)
            cost_cny = product_data.get("price", 0)
            product_name = product_data.get("productName", params.sku)
        
        # Get exchange rate and referral fee
        exchange_rate = _get_currency_rate()
        referral_fee = params.amazon_referral_fee_percent or _get_amazon_fees()
        
        # Calculate true profit
        calculation = _calculate_true_profit(
            selling_price_usd=params.selling_price_usd,
            cost_cny=cost_cny,
            exchange_rate=exchange_rate,
            shipping_to_amazon_usd=params.shipping_to_amazon_usd,
            amazon_referral_fee_percent=referral_fee,
            fba_fee_usd=params.fba_fee_usd,
            monthly_storage_fee_usd=params.monthly_storage_fee_usd,
            advertising_acos_percent=params.advertising_acos_percent,
            payment_processing_fee_percent=params.payment_processing_fee_percent,
            return_rate_percent=params.return_rate_percent,
            customs_duty_percent=params.customs_duty_percent,
            overhead_percent=params.overhead_percent,
        )
        
        result = {
            "sku": params.sku,
            "product_name": product_name,
            "calculated_at": datetime.now().isoformat(),
            **calculation
        }
        
        if params.response_format == ResponseFormat.JSON:
            return json.dumps(result, indent=2, ensure_ascii=False)
        else:
            # Determine status icon
            status_icon = "🟢 PROFITABLE" if result["is_profitable"] else "🔴 NOT PROFITABLE"
            
            lines = [
                f"# True Profit Analysis: {params.sku} [{status_icon}]",
                "",
                f"**Product**: {product_name}",
                f"**Selling Price**: ${result['selling_price_usd']:.2f}",
                "",
                "## Summary",
                f"- **Net Profit**: ${result['net_profit_usd']:.2f}",
                f"- **Gross Profit**: ${result['gross_profit_usd']:.2f}",
                f"- **Profit Margin**: {result['profit_margin_percent']:.1f}%",
                f"- **ROI**: {result['roi_percent']:.1f}%",
                f"- **Break-Even Price**: ${result['break_even_price_usd']:.2f}",
                "",
                "## Detailed Cost Breakdown",
                f"| Cost Category | Amount (USD) | Percentage of Price |",
                f"|---------------|--------------|---------------------|",
            ]
            
            cost_breakdown = result["cost_breakdown"]
            for category, amount in cost_breakdown.items():
                percentage = (amount / result["selling_price_usd"] * 100) if result["selling_price_usd"] > 0 else 0
                category_name = category.replace("_usd", "").replace("_", " ").title()
                lines.append(f"| {category_name} | ${amount:.2f} | {percentage:.1f}% |")
            
            lines.extend([
                "",
                f"**Total Cost**: ${result['total_cost_usd']:.2f}",
                "",
            ])
            
            if not result["is_profitable"]:
                lines.extend([
                    "## ⚠️ Recommendations",
                    f"- Consider increasing price by ${result['recommended_price_adjustment']:.2f}",
                    f"- Target price: ${result['selling_price_usd'] + result['recommended_price_adjustment']:.2f}",
                    "- Review advertising costs (ACoS)",
                    "- Optimize shipping and FBA fees",
                    "",
                ])
            else:
                lines.extend([
                    "## ✅ Recommendations",
                    "- Current pricing is profitable",
                    "- Monitor ACoS and return rates regularly",
                    "- Consider scaling advertising if ROI remains strong",
                    "",
                ])
            
            lines.append(f"_Calculated at: {result['calculated_at']}_")
            
            return "\n".join(lines)
    
    except Exception as e:
        return _handle_api_error(e, "True Profit Calculator")


@mcp.tool(
    name="get_license_info",
    annotations={
        "title": "Get License Information",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
async def get_license_info() -> str:
    """
    获取当前许可证信息
    Get current license tier and features.

    Returns:
        str: License information in markdown format.
    """
    license_manager = get_license_manager()
    license = license_manager.get_current_license()
    tier_name = license_manager.get_tier_name(license.tier)

    # 功能列表
    from license_manager import get_features_for_tier, TIER_FEATURES
    all_tiers = list(TIER_FEATURES.keys())
    tier_features = {
        license_manager.get_tier_name(t): get_features_for_tier(t)
        for t in all_tiers
    }

    lines = [
        f"# 许可证信息 / License Information",
        "",
        f"## 当前等级: {tier_name}",
        "",
        "### 当前可用功能:",
        "",
    ]

    for feature in license.features:
        lines.append(f"- ✅ {feature}")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 升级选项 / Upgrade Options")
    lines.append("")

    for tier_name, features in tier_features.items():
        tier = [t for t, name in tier_features.items() if name == tier_name]
        if tier:
            tier = tier[0]
            lines.append(f"### {tier_name}")
            for f in features:
                status = "✅" if f in license.features else "🔒"
                lines.append(f"- {status} {f}")
            lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
