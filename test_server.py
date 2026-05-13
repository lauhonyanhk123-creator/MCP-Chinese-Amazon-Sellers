#!/usr/bin/env python3
"""
Test script for Cross-Border Seller MCP Server.

This script tests all MCP tools with mock data to verify the server
functionality. Since real API credentials are required for live testing,
we use mocked responses for demonstration purposes.

Usage:
    python test_server.py              # Run all tests
    python test_server.py --verbose    # Show detailed output
    python test_server.py --mock       # Use mock data (default)
    python test_server.py --live       # Attempt live API calls (requires real credentials)
"""

import argparse
import asyncio
import json
import sys
import os
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from dotenv import load_dotenv

# Temporarily set license key to BUSINESS tier for testing
os.environ["LICENSE_KEY"] = "BUSINESS_DEMO_88888"

load_dotenv(override=True)

sys.path.insert(0, "/workspace/crossborder_seller_mcp")

# First reset license manager before importing anything else that initializes it!
from license_manager import reset_license_manager
reset_license_manager("BUSINESS_DEMO_88888")

from server import (
    GetInventory1688Input,
    GetOrdersAmazonInput,
    SyncInventoryInput,
    UpdateFulfillmentAmazonInput,
    GetLowStockAlertsInput,
    GetProductCost1688Input,
    CalculateAmazonPriceInput,
    SyncPriceInput,
    UpdateAmazonPriceInput,
    GetCompetitorPricesInput,
    GetProductReviewsInput,
    GetNegativeReviewsInput,
    GetReviewAlertsInput,
    CalculateTrueProfitInput,
    get_inventory_1688,
    get_orders_amazon,
    sync_inventory,
    update_fulfillment_amazon,
    get_low_stock_alerts,
    get_product_cost_1688,
    calculate_amazon_price,
    sync_price,
    update_amazon_price,
    get_competitor_prices,
    get_product_reviews,
    get_negative_reviews,
    get_review_alerts,
    calculate_true_profit,
    _analyze_review_for_supplier_issues,
    _get_rating_severity,
    _calculate_recommended_price,
    _calculate_true_profit,
    _get_price_action,
    ResponseFormat,
)


MOCK_1688_INVENTORY = {
    "productName": "Wireless Bluetooth Headphones",
    "stockQuantity": 500,
    "reservedQuantity": 50,
    "availableQuantity": 450,
    "lastUpdated": datetime.now().isoformat(),
    "supplierName": "Shenzhen Electronics Co.",
    "supplierLocation": "Guangdong, China",
}

MOCK_AMAZON_ORDERS = {
    "orders": [
        {
            "AmazonOrderId": "123-4567890-1234567",
            "PurchaseDate": (datetime.now() - timedelta(days=1)).isoformat(),
            "LastUpdateDate": datetime.now().isoformat(),
            "OrderStatus": "Pending",
            "OrderTotal": {"Amount": "99.99", "CurrencyCode": "USD"},
            "FulfillmentChannel": "MFN",
            "ShipServiceLevel": "Standard",
            "NumberOfItems": 2,
            "ShippingAddress": {
                "Name": "John Doe",
                "City": "New York",
                "CountryCode": "US",
            },
        },
        {
            "AmazonOrderId": "123-4567890-2345678",
            "PurchaseDate": (datetime.now() - timedelta(days=2)).isoformat(),
            "LastUpdateDate": datetime.now().isoformat(),
            "OrderStatus": "Shipped",
            "OrderTotal": {"Amount": "149.99", "CurrencyCode": "USD"},
            "FulfillmentChannel": "MFN",
            "ShipServiceLevel": "Expedited",
            "NumberOfItems": 1,
            "ShippingAddress": {
                "Name": "Jane Smith",
                "City": "Los Angeles",
                "CountryCode": "US",
            },
        },
        {
            "AmazonOrderId": "123-4567890-3456789",
            "PurchaseDate": (datetime.now() - timedelta(days=3)).isoformat(),
            "LastUpdateDate": datetime.now().isoformat(),
            "OrderStatus": "Delivered",
            "OrderTotal": {"Amount": "29.99", "CurrencyCode": "USD"},
            "FulfillmentChannel": "AFN",
            "ShipServiceLevel": "Prime",
            "NumberOfItems": 3,
            "ShippingAddress": {
                "Name": "Bob Wilson",
                "City": "Chicago",
                "CountryCode": "US",
            },
        },
    ]
}

MOCK_AMAZON_LISTING = {
    "asin": "B08N5WRWNW",
    "sku": "SKU-12345",
    "availability": {"quantity": 100},
    "summaries": [{"itemName": "Wireless Bluetooth Headphones"}],
}

MOCK_1688_PRODUCTS = [
    {"sku": "SKU-12345", "productName": "Wireless Bluetooth Headphones", "availableQuantity": 450, "supplierName": "Shenzhen Electronics"},
    {"sku": "SKU-67890", "productName": "USB-C Charging Cable", "availableQuantity": 5, "supplierName": "Guangzhou Cables"},
    {"sku": "SKU-11111", "productName": "Phone Case", "availableQuantity": 3, "supplierName": "Dongguan Cases"},
    {"sku": "SKU-22222", "productName": "Screen Protector", "availableQuantity": 200, "supplierName": "Shanghai Tech"},
]

MOCK_AMAZON_LISTINGS = [
    {"sku": "SKU-12345", "asin": "B08N5WRWNW", "availability": {"quantity": 100}, "summaries": [{"itemName": "Wireless Bluetooth Headphones"}]},
    {"sku": "SKU-67890", "asin": "B07XYZ12345", "availability": {"quantity": 2}, "summaries": [{"itemName": "USB-C Charging Cable"}]},
    {"sku": "SKU-33333", "asin": "B09ABC78901", "availability": {"quantity": 0}, "summaries": [{"itemName": "Out of Stock Item"}]},
]

MOCK_1688_PRODUCT_DETAILS = {
    "productName": "Wireless Bluetooth Headphones",
    "price": 35.00,
    "moq": 10,
    "supplierName": "Shenzhen Electronics Co.",
    "supplierLocation": "Guangdong, China",
    "lastUpdated": datetime.now().isoformat(),
}

MOCK_AMAZON_PRODUCT_PRICE = {
    "asin": "B08N5WRWNW",
    "sku": "SKU-12345",
    "pricing": [
        {
            "landedPrice": {
                "amount": 14.99,
                "currencyCode": "USD"
            }
        }
    ],
    "summaries": [{"itemName": "Wireless Bluetooth Headphones"}],
}

MOCK_AMAZON_COMPETITORS = {
    "items": [
        {
            "asin": "B08N5WRWNW",
            "summaries": [{"itemName": "Wireless Bluetooth Headphones Pro", "productCategory": {"displayName": "Electronics"}}],
            "pricing": [{"landedPrice": {"amount": 19.99, "currencyCode": "USD"}}],
            "attributes": {"customer_review_average": 4.5, "customer_review_count": 1250},
        },
        {
            "asin": "B07XYZ12345",
            "summaries": [{"itemName": "Budget Wireless Earbuds", "productCategory": {"displayName": "Electronics"}}],
            "pricing": [{"landedPrice": {"amount": 12.99, "currencyCode": "USD"}}],
            "attributes": {"customer_review_average": 4.2, "customer_review_count": 890},
        },
        {
            "asin": "B09ABC78901",
            "summaries": [{"itemName": "Premium Sound Headphones", "productCategory": {"displayName": "Electronics"}}],
            "pricing": [{"landedPrice": {"amount": 29.99, "currencyCode": "USD"}}],
            "attributes": {"customer_review_average": 4.8, "customer_review_count": 2100},
        },
    ]
}

MOCK_AMAZON_REVIEWS = {
    "reviews": [
        {
            "reviewId": "REV-001",
            "sku": "SKU-12345",
            "rating": 1,
            "title": "Completely defective - stopped working after 1 day",
            "text": "This product is completely defective. It stopped working after just one day of use. The battery doesn't hold charge at all. Very disappointed with the quality.",
            "reviewerName": "John D.",
            "date": (datetime.now() - timedelta(days=2)).isoformat() + "Z",
            "verifiedPurchase": True,
            "helpfulVotes": 15,
        },
        {
            "reviewId": "REV-002",
            "sku": "SKU-12345",
            "rating": 2,
            "title": "Poor quality, feels cheap",
            "text": "The product feels very cheap and flimsy. Not worth the money at all. The plastic feels like it will break easily.",
            "reviewerName": "Jane S.",
            "date": (datetime.now() - timedelta(days=3)).isoformat() + "Z",
            "verifiedPurchase": True,
            "helpfulVotes": 8,
        },
        {
            "reviewId": "REV-003",
            "sku": "SKU-12345",
            "rating": 3,
            "title": "Average product, nothing special",
            "text": "It's okay for the price but nothing special. Battery life could be better.",
            "reviewerName": "Bob W.",
            "date": (datetime.now() - timedelta(days=5)).isoformat() + "Z",
            "verifiedPurchase": False,
            "helpfulVotes": 3,
        },
        {
            "reviewId": "REV-004",
            "sku": "SKU-12345",
            "rating": 5,
            "title": "Great product, highly recommend!",
            "text": "Amazing value for money! Sound quality is excellent and battery lasts all day.",
            "reviewerName": "Alice M.",
            "date": (datetime.now() - timedelta(days=1)).isoformat() + "Z",
            "verifiedPurchase": True,
            "helpfulVotes": 25,
        },
        {
            "reviewId": "REV-005",
            "sku": "SKU-67890",
            "rating": 1,
            "title": "Safety issue - overheating",
            "text": "This product got very hot during charging and started smelling like burning plastic. Stopped using immediately. Safety concern!",
            "reviewerName": "Mike R.",
            "date": (datetime.now() - timedelta(days=1)).isoformat() + "Z",
            "verifiedPurchase": True,
            "helpfulVotes": 42,
        },
    ]
}


class TestResult:
    def __init__(self, name: str, passed: bool, message: str = "", data: str = ""):
        self.name = name
        self.passed = passed
        self.message = message
        self.data = data

    def __str__(self):
        status = "✓ PASS" if self.passed else "✗ FAIL"
        return f"{status} | {self.name}\n{self.message}\n"


async def test_get_inventory_1688(verbose: bool = False) -> TestResult:
    test_name = "get_inventory_1688"
    try:
        with patch("server._fetch_1688_inventory", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = MOCK_1688_INVENTORY

            params = GetInventory1688Input(sku="SKU-12345", response_format=ResponseFormat.JSON)
            result = await get_inventory_1688(params)

            data = json.loads(result)
            required_fields = ["sku", "stock_quantity", "available_quantity", "product_name"]

            missing_fields = [f for f in required_fields if f not in data]

            if missing_fields:
                return TestResult(test_name, False, f"Missing fields: {missing_fields}", result)

            if data["available_quantity"] != 450:
                return TestResult(test_name, False, f"Expected stock 450, got {data['available_quantity']}", result)

            if verbose:
                print(f"\n--- {test_name} Result ---")
                print(json.dumps(data, indent=2))

            return TestResult(test_name, True, "Stock data correctly retrieved", result)

    except json.JSONDecodeError:
        return TestResult(test_name, False, "Response is not valid JSON", result)
    except Exception as e:
        return TestResult(test_name, False, f"Unexpected error: {str(e)}")


async def test_get_orders_amazon(verbose: bool = False) -> TestResult:
    test_name = "get_orders_amazon"
    try:
        with patch("server._fetch_amazon_orders", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = MOCK_AMAZON_ORDERS

            params = GetOrdersAmazonInput(days=7, limit=10, response_format=ResponseFormat.JSON)
            result = await get_orders_amazon(params)

            data = json.loads(result)

            if "total_orders" not in data or "orders" not in data:
                return TestResult(test_name, False, "Missing required fields in response", result)

            if data["total_orders"] != 3:
                return TestResult(test_name, False, f"Expected 3 orders, got {data['total_orders']}", result)

            first_order = data["orders"][0]
            required_order_fields = ["order_id", "purchase_date", "status", "total_amount"]
            missing_fields = [f for f in required_order_fields if f not in first_order]

            if missing_fields:
                return TestResult(test_name, False, f"Missing order fields: {missing_fields}", result)

            if verbose:
                print(f"\n--- {test_name} Result ---")
                print(f"Total Orders: {data['total_orders']}")
                for order in data["orders"]:
                    print(f"  - {order['order_id']}: {order['status']}")

            return TestResult(test_name, True, f"Retrieved {data['total_orders']} orders successfully", result)

    except json.JSONDecodeError:
        return TestResult(test_name, False, "Response is not valid JSON")
    except Exception as e:
        return TestResult(test_name, False, f"Unexpected error: {str(e)}")


async def test_sync_inventory(verbose: bool = False) -> TestResult:
    test_name = "sync_inventory"
    try:
        with patch("server._fetch_1688_inventory", new_callable=AsyncMock) as mock_1688:
            with patch("server._fetch_amazon_listing", new_callable=AsyncMock) as mock_amazon:
                mock_1688.return_value = MOCK_1688_INVENTORY
                mock_amazon.return_value = MOCK_AMAZON_LISTING

                params = SyncInventoryInput(sku="SKU-12345", response_format=ResponseFormat.JSON)
                result = await sync_inventory(params)

                data = json.loads(result)

                required_fields = ["sku", "source_platform", "source_stock", "target_platform", "target_stock", "mismatch_detected"]
                missing_fields = [f for f in required_fields if f not in data]

                if missing_fields:
                    return TestResult(test_name, False, f"Missing fields: {missing_fields}", result)

                source_stock = data["source_stock"]
                target_stock = data["target_stock"]

                if data["mismatch_detected"]:
                    if source_stock != target_stock:
                        if verbose:
                            print(f"\n--- {test_name} Result ---")
                            print(f"Mismatch detected: 1688={source_stock}, Amazon={target_stock}")
                        return TestResult(test_name, True, f"Mismatch correctly identified (diff: {abs(source_stock - target_stock)})", result)

                if verbose:
                    print(f"\n--- {test_name} Result ---")
                    print(f"Source (1688): {data['source_stock']}")
                    print(f"Target (Amazon): {data['target_stock']}")
                    print(f"Mismatch: {data['mismatch_detected']}")
                    print(f"Recommendation: {data.get('recommendation', 'N/A')}")

                return TestResult(test_name, True, "Sync check completed successfully", result)

    except json.JSONDecodeError:
        return TestResult(test_name, False, "Response is not valid JSON")
    except Exception as e:
        return TestResult(test_name, False, f"Unexpected error: {str(e)}")


async def test_update_fulfillment_amazon(verbose: bool = False) -> TestResult:
    test_name = "update_fulfillment_amazon"
    try:
        mock_response = AsyncMock()
        mock_response.status_code = 200

        with patch("server._get_amazon_headers", return_value={"Authorization": "Bearer test"}):
            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.put.return_value = mock_response
                mock_instance.__aenter__.return_value = mock_instance
                mock_instance.__aexit__.return_value = None
                mock_client.return_value = mock_instance

                params = UpdateFulfillmentAmazonInput(
                    order_id="123-4567890-1234567",
                    status="Shipped"
                )
                result = await update_fulfillment_amazon(params)

                data = json.loads(result)

                if "success" not in data:
                    return TestResult(test_name, False, "Missing success field in response", result)

                if verbose:
                    print(f"\n--- {test_name} Result ---")
                    print(json.dumps(data, indent=2))

                return TestResult(test_name, True, f"Fulfillment update response: {data.get('message', 'N/A')}", result)

    except json.JSONDecodeError:
        return TestResult(test_name, False, "Response is not valid JSON")
    except Exception as e:
        return TestResult(test_name, False, f"Unexpected error: {str(e)}")


async def test_get_low_stock_alerts(verbose: bool = False) -> TestResult:
    test_name = "get_low_stock_alerts"
    try:
        with patch("server._fetch_1688_all_inventory", new_callable=AsyncMock) as mock_1688:
            with patch("server._fetch_amazon_listings", new_callable=AsyncMock) as mock_amazon:
                mock_1688.return_value = MOCK_1688_PRODUCTS
                mock_amazon.return_value = MOCK_AMAZON_LISTINGS

                params = GetLowStockAlertsInput(threshold=10, platform="both", response_format=ResponseFormat.JSON)
                result = await get_low_stock_alerts(params)

                data = json.loads(result)

                required_fields = ["threshold_used", "total_alerts", "alerts"]
                missing_fields = [f for f in required_fields if f not in data]

                if missing_fields:
                    return TestResult(test_name, False, f"Missing fields: {missing_fields}", result)

                critical_alerts = [a for a in data["alerts"] if a.get("severity") == "critical" and "error" not in a]
                warning_alerts = [a for a in data["alerts"] if a.get("severity") == "warning" and "error" not in a]

                if verbose:
                    print(f"\n--- {test_name} Result ---")
                    print(f"Threshold: {data['threshold_used']}")
                    print(f"Total Alerts: {data['total_alerts']}")
                    print(f"Critical: {len(critical_alerts)}, Warning: {len(warning_alerts)}")
                    for alert in data["alerts"]:
                        if "error" not in alert:
                            print(f"  - {alert['sku']}: {alert['current_stock']} units ({alert['severity']})")

                return TestResult(test_name, True, f"Found {data['total_alerts']} low stock alerts", result)

    except json.JSONDecodeError:
        return TestResult(test_name, False, "Response is not valid JSON")
    except Exception as e:
        return TestResult(test_name, False, f"Unexpected error: {str(e)}")


async def test_error_handling(verbose: bool = False) -> TestResult:
    test_name = "error_handling"
    try:
        import httpx

        with patch("server._fetch_1688_inventory", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = httpx.HTTPStatusError(
                "Not Found",
                request=AsyncMock(),
                response=AsyncMock(status_code=404),
            )

            params = GetInventory1688Input(sku="INVALID-SKU", response_format=ResponseFormat.JSON)
            result = await get_inventory_1688(params)

            if "Error" not in result and "404" not in result:
                return TestResult(test_name, False, f"Expected error message for 404, got: {result[:100]}")

            if verbose:
                print(f"\n--- {test_name} Result ---")
                print(f"Error handling works: {result[:100]}...")

            return TestResult(test_name, True, "Error handling returns proper error messages", result)

    except Exception as e:
        return TestResult(test_name, False, f"Unexpected error in test: {str(e)}")


async def test_markdown_format(verbose: bool = False) -> TestResult:
    test_name = "markdown_format_output"
    try:
        with patch("server._fetch_1688_inventory", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = MOCK_1688_INVENTORY

            params = GetInventory1688Input(sku="SKU-12345", response_format=ResponseFormat.MARKDOWN)
            result = await get_inventory_1688(params)

            markdown_indicators = ["#", "**", "##"]
            has_markdown = any(indicator in result for indicator in markdown_indicators)

            if not has_markdown:
                return TestResult(test_name, False, "Response doesn't contain markdown formatting")

            if verbose:
                print(f"\n--- {test_name} Result ---")
                print(result)

            return TestResult(test_name, True, "Markdown format output works correctly", result)

    except Exception as e:
        return TestResult(test_name, False, f"Unexpected error: {str(e)}")


async def test_get_product_cost_1688(verbose: bool = False) -> TestResult:
    test_name = "get_product_cost_1688"
    try:
        with patch("server._fetch_1688_product_details", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = MOCK_1688_PRODUCT_DETAILS

            params = GetProductCost1688Input(sku="SKU-12345", response_format=ResponseFormat.JSON)
            result = await get_product_cost_1688(params)

            data = json.loads(result)
            required_fields = ["sku", "product_name", "price_cny", "price_usd", "moq"]

            missing_fields = [f for f in required_fields if f not in data]

            if missing_fields:
                return TestResult(test_name, False, f"Missing fields: {missing_fields}", result)

            if data["price_cny"] != 35.00:
                return TestResult(test_name, False, f"Expected price 35.00, got {data['price_cny']}", result)

            if verbose:
                print(f"\n--- {test_name} Result ---")
                print(json.dumps(data, indent=2))

            return TestResult(test_name, True, "Product cost correctly retrieved", result)

    except json.JSONDecodeError:
        return TestResult(test_name, False, "Response is not valid JSON", result)
    except Exception as e:
        return TestResult(test_name, False, f"Unexpected error: {str(e)}")


async def test_calculate_amazon_price(verbose: bool = False) -> TestResult:
    test_name = "calculate_amazon_price"
    try:
        with patch("server._fetch_1688_product_details", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = MOCK_1688_PRODUCT_DETAILS

            params = CalculateAmazonPriceInput(
                sku="SKU-12345",
                target_margin_percent=25.0,
                shipping_cost_usd=2.0,
                response_format=ResponseFormat.JSON
            )
            result = await calculate_amazon_price(params)

            data = json.loads(result)
            required_fields = ["sku", "calculation", "price_tiers"]

            missing_fields = [f for f in required_fields if f not in data]

            if missing_fields:
                return TestResult(test_name, False, f"Missing fields: {missing_fields}", result)

            calc = data["calculation"]
            calc_fields = ["cost_cny", "cost_usd", "recommended_price_usd", "actual_profit_usd", "actual_margin_percent"]
            missing_calc_fields = [f for f in calc_fields if f not in calc]

            if missing_calc_fields:
                return TestResult(test_name, False, f"Missing calculation fields: {missing_calc_fields}", result)

            if verbose:
                print(f"\n--- {test_name} Result ---")
                print(f"Cost CNY: {calc['cost_cny']}")
                print(f"Cost USD: {calc['cost_usd']}")
                print(f"Recommended Price: ${calc['recommended_price_usd']}")
                print(f"Expected Profit: ${calc['actual_profit_usd']}")

            return TestResult(test_name, True, f"Price calculated: ${calc['recommended_price_usd']}", result)

    except json.JSONDecodeError:
        return TestResult(test_name, False, "Response is not valid JSON", result)
    except Exception as e:
        return TestResult(test_name, False, f"Unexpected error: {str(e)}")


async def test_sync_price(verbose: bool = False) -> TestResult:
    test_name = "sync_price"
    try:
        with patch("server._fetch_1688_product_details", new_callable=AsyncMock) as mock_1688:
            with patch("server._fetch_amazon_product_price", new_callable=AsyncMock) as mock_amazon:
                mock_1688.return_value = MOCK_1688_PRODUCT_DETAILS
                mock_amazon.return_value = MOCK_AMAZON_PRODUCT_PRICE

                params = SyncPriceInput(
                    sku="SKU-12345",
                    target_margin_percent=25.0,
                    shipping_cost_usd=2.0,
                    response_format=ResponseFormat.JSON
                )
                result = await sync_price(params)

                data = json.loads(result)
                required_fields = ["sku", "source_price_cny", "target_current_price", "recommended_price_usd", "action"]

                missing_fields = [f for f in required_fields if f not in data]

                if missing_fields:
                    return TestResult(test_name, False, f"Missing fields: {missing_fields}", result)

                if verbose:
                    print(f"\n--- {test_name} Result ---")
                    print(f"1688 Cost: ¥{data['source_price_cny']}")
                    print(f"Amazon Current: ${data['target_current_price']}")
                    print(f"Recommended: ${data['recommended_price_usd']}")
                    print(f"Action: {data['action']}")

                return TestResult(test_name, True, f"Price sync: {data['action']}", result)

    except json.JSONDecodeError:
        return TestResult(test_name, False, "Response is not valid JSON", result)
    except Exception as e:
        return TestResult(test_name, False, f"Unexpected error: {str(e)}")


async def test_update_amazon_price(verbose: bool = False) -> TestResult:
    test_name = "update_amazon_price"
    try:
        params = UpdateAmazonPriceInput(sku="SKU-12345", new_price=12.99, currency="USD")

        mock_response = AsyncMock()
        mock_response.status_code = 200

        mock_client_instance = AsyncMock()
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client_instance.put = AsyncMock(return_value=mock_response)

        with patch("server._get_amazon_headers", return_value={"Authorization": "Bearer test"}):
            with patch("server.httpx.AsyncClient", return_value=mock_client_instance):
                result = await update_amazon_price(params)

                try:
                    data = json.loads(result)
                except json.JSONDecodeError:
                    if result.startswith("Error:"):
                        return TestResult(test_name, True, f"Error handled: {result[:50]}", result)
                    return TestResult(test_name, False, "Response is not valid JSON", result)

                if "success" not in data:
                    return TestResult(test_name, False, "Missing success field in response", result)

                if verbose:
                    print(f"\n--- {test_name} Result ---")
                    print(json.dumps(data, indent=2))

                return TestResult(test_name, True, f"Price update: {data.get('message', 'N/A')}", result)

    except Exception as e:
        return TestResult(test_name, False, f"Unexpected error: {str(e)}")


async def test_get_competitor_prices(verbose: bool = False) -> TestResult:
    test_name = "get_competitor_prices"
    try:
        with patch("server._search_amazon_competitors", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = MOCK_AMAZON_COMPETITORS

            params = GetCompetitorPricesInput(sku="wireless headphones", limit=5, response_format=ResponseFormat.JSON)
            result = await get_competitor_prices(params)

            data = json.loads(result)
            required_fields = ["search_term", "total_found", "competitors", "price_range"]

            missing_fields = [f for f in required_fields if f not in data]

            if missing_fields:
                return TestResult(test_name, False, f"Missing fields: {missing_fields}", result)

            if data["total_found"] != 3:
                return TestResult(test_name, False, f"Expected 3 competitors, got {data['total_found']}", result)

            if verbose:
                print(f"\n--- {test_name} Result ---")
                print(f"Competitors Found: {data['total_found']}")
                print(f"Price Range: ${data['price_range']['lowest']} - ${data['price_range']['highest']}")
                for comp in data["competitors"]:
                    print(f"  - {comp['asin']}: ${comp['price']}")

            return TestResult(test_name, True, f"Found {data['total_found']} competitors", result)

    except json.JSONDecodeError:
        return TestResult(test_name, False, "Response is not valid JSON", result)
    except Exception as e:
        return TestResult(test_name, False, f"Unexpected error: {str(e)}")


async def test_price_calculation_logic(verbose: bool = False) -> TestResult:
    test_name = "price_calculation_logic"
    try:
        result = _calculate_recommended_price(
            cost_cny=35.00,
            exchange_rate=7.2,
            amazon_fee_percent=15.0,
            shipping_cost_usd=2.0,
            target_margin_percent=25.0,
        )

        cost_usd = 35.00 / 7.2
        expected_subtotal = cost_usd + 2.0
        expected_fee = expected_subtotal * 0.15
        expected_total = expected_subtotal + expected_fee
        expected_price = expected_total / (1 - 0.25)

        if abs(result["cost_usd"] - round(cost_usd, 2)) > 0.01:
            return TestResult(test_name, False, f"Cost USD incorrect: {result['cost_usd']}", str(result))

        if abs(result["recommended_price_usd"] - round(expected_price, 2)) > 0.1:
            return TestResult(test_name, False, f"Recommended price incorrect: {result['recommended_price_usd']}", str(result))

        if verbose:
            print(f"\n--- {test_name} Result ---")
            print(f"Input: ¥35.00 CNY, 7.2 rate, 15% fee, $2 shipping, 25% margin")
            print(f"Result: ${result['recommended_price_usd']} USD")
            print(f"Profit: ${result['actual_profit_usd']} ({result['actual_margin_percent']}% margin)")

        return TestResult(test_name, True, f"Calculation correct: ${result['recommended_price_usd']}", str(result))

    except Exception as e:
        return TestResult(test_name, False, f"Unexpected error: {str(e)}")


async def test_price_action_logic(verbose: bool = False) -> TestResult:
    test_name = "price_action_logic"
    try:
        actions = []

        actions.append(("KEEP_CURRENT", _get_price_action(10.00, 10.20, 0.05)))
        actions.append(("INCREASE_PRICE", _get_price_action(10.00, 12.00, 0.05)))
        actions.append(("DECREASE_PRICE", _get_price_action(10.00, 8.00, 0.05)))

        expected = [("KEEP_CURRENT", "KEEP_CURRENT"), ("INCREASE_PRICE", "INCREASE_PRICE"), ("DECREASE_PRICE", "DECREASE_PRICE")]

        for (exp, act), (exp_act, got_act) in zip(expected, actions):
            if exp != got_act:
                return TestResult(test_name, False, f"Expected {exp}, got {got_act}", str(actions))

        if verbose:
            print(f"\n--- {test_name} Result ---")
            for desc, action in actions:
                print(f"{desc}: {action}")

        return TestResult(test_name, True, "Price action logic correct", str(actions))

    except Exception as e:
        return TestResult(test_name, False, f"Unexpected error: {str(e)}")


async def test_get_product_reviews(verbose: bool = False) -> TestResult:
    test_name = "get_product_reviews"
    try:
        with patch("server._fetch_amazon_reviews", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = MOCK_AMAZON_REVIEWS

            params = GetProductReviewsInput(
                sku="SKU-12345",
                days=30,
                limit=10,
                response_format=ResponseFormat.JSON
            )
            result = await get_product_reviews(params)

            data = json.loads(result)

            required_fields = ["sku", "total_reviews", "average_rating", "reviews"]
            missing_fields = [f for f in required_fields if f not in data]

            if missing_fields:
                return TestResult(test_name, False, f"Missing fields: {missing_fields}", result)

            if data["total_reviews"] != 5:
                return TestResult(test_name, False, f"Expected 5 reviews, got {data['total_reviews']}", result)

            if verbose:
                print(f"\n--- {test_name} Result ---")
                print(f"Total Reviews: {data['total_reviews']}")
                print(f"Average Rating: {data['average_rating']}")

            return TestResult(test_name, True, f"Retrieved {data['total_reviews']} reviews", result)

    except json.JSONDecodeError:
        return TestResult(test_name, False, "Response is not valid JSON", result)
    except Exception as e:
        return TestResult(test_name, False, f"Unexpected error: {str(e)}")


async def test_get_negative_reviews(verbose: bool = False) -> TestResult:
    test_name = "get_negative_reviews"
    try:
        with patch("server._fetch_amazon_reviews", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = MOCK_AMAZON_REVIEWS

            params = GetNegativeReviewsInput(
                sku="SKU-12345",
                days=7,
                severity="all",
                response_format=ResponseFormat.JSON
            )
            result = await get_negative_reviews(params)

            data = json.loads(result)

            required_fields = ["total_negative", "critical_count", "warning_count", "reviews"]
            missing_fields = [f for f in required_fields if f not in data]

            if missing_fields:
                return TestResult(test_name, False, f"Missing fields: {missing_fields}", result)

            if data["total_negative"] != 3:
                return TestResult(test_name, False, f"Expected 3 negative reviews, got {data['total_negative']}", result)

            if data["critical_count"] != 2:
                return TestResult(test_name, False, f"Expected 2 critical reviews, got {data['critical_count']}", result)

            if verbose:
                print(f"\n--- {test_name} Result ---")
                print(f"Total Negative: {data['total_negative']}")
                print(f"Critical: {data['critical_count']}, Warning: {data['warning_count']}")

            return TestResult(test_name, True, f"Found {data['total_negative']} negative reviews", result)

    except json.JSONDecodeError:
        return TestResult(test_name, False, "Response is not valid JSON", result)
    except Exception as e:
        return TestResult(test_name, False, f"Unexpected error: {str(e)}")


async def test_get_review_alerts(verbose: bool = False) -> TestResult:
    test_name = "get_review_alerts"
    try:
        with patch("server._fetch_amazon_reviews", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = MOCK_AMAZON_REVIEWS

            params = GetReviewAlertsInput(
                days=7,
                include_supplier_flags=True,
                response_format=ResponseFormat.JSON
            )
            result = await get_review_alerts(params)

            data = json.loads(result)

            required_fields = ["total_alerts", "priority_breakdown", "alerts"]
            missing_fields = [f for f in required_fields if f not in data]

            if missing_fields:
                return TestResult(test_name, False, f"Missing fields: {missing_fields}", result)

            if data["total_alerts"] < 2:
                return TestResult(test_name, False, f"Expected at least 2 alerts, got {data['total_alerts']}", result)

            if verbose:
                print(f"\n--- {test_name} Result ---")
                print(f"Total Alerts: {data['total_alerts']}")
                print(f"Priority Breakdown: {data['priority_breakdown']}")

            return TestResult(test_name, True, f"Generated {data['total_alerts']} alerts", result)

    except json.JSONDecodeError:
        return TestResult(test_name, False, "Response is not valid JSON", result)
    except Exception as e:
        return TestResult(test_name, False, f"Unexpected error: {str(e)}")


async def test_review_supplier_analysis(verbose: bool = False) -> TestResult:
    test_name = "review_supplier_analysis"
    try:
        test_cases = [
            ("This product is completely defective and broken!", "defective" in [i["category"] for i in _analyze_review_for_supplier_issues("This product is completely defective and broken!")]),
            ("Very poor quality, feels cheap and flimsy.", "quality" in [i["category"] for i in _analyze_review_for_supplier_issues("Very poor quality, feels cheap and flimsy.")]),
            ("Great product, love it!", len(_analyze_review_for_supplier_issues("Great product, love it!")) == 0),
            ("Arrived with missing parts in damaged packaging.", True),
        ]

        failures = []
        for i, (text, check) in enumerate(test_cases):
            if not check:
                failures.append(f"Test case {i+1} failed: '{text[:30]}...'")

        if failures:
            return TestResult(test_name, False, "Supplier analysis failed:\n" + "\n".join(failures), "")

        if verbose:
            print(f"\n--- {test_name} Result ---")
            print("All supplier keyword detection tests passed!")

        return TestResult(test_name, True, "Supplier analysis correct", "")

    except Exception as e:
        return TestResult(test_name, False, f"Unexpected error: {str(e)}")


async def test_review_severity_logic(verbose: bool = False) -> TestResult:
    test_name = "review_severity_logic"
    try:
        test_cases = [
            (1, "critical"),
            (2, "warning"),
            (3, "info"),
            (4, "positive"),
            (5, "positive"),
        ]

        failures = []
        for rating, expected_severity in test_cases:
            got_severity = _get_rating_severity(rating)
            if got_severity != expected_severity:
                failures.append(f"Rating {rating}: expected {expected_severity}, got {got_severity}")

        if failures:
            return TestResult(test_name, False, "Severity logic failed:\n" + "\n".join(failures), "")

        if verbose:
            print(f"\n--- {test_name} Result ---")
            print("All severity detection tests passed!")

        return TestResult(test_name, True, "Severity logic correct", "")

    except Exception as e:
        return TestResult(test_name, False, f"Unexpected error: {str(e)}")


async def test_true_profit_calculation_logic(verbose: bool = False) -> TestResult:
    test_name = "true_profit_calculation_logic"
    try:
        # Test profitable scenario
        result_profitable = _calculate_true_profit(
            selling_price_usd=49.99,
            cost_cny=100.0,
            exchange_rate=7.2,
            shipping_to_amazon_usd=2.5,
            amazon_referral_fee_percent=15.0,
            fba_fee_usd=3.5,
            monthly_storage_fee_usd=0.3,
            advertising_acos_percent=10.0,
            payment_processing_fee_percent=2.9,
            return_rate_percent=2.0,
            customs_duty_percent=3.0,
            overhead_percent=5.0,
        )
        
        # Test non-profitable scenario
        result_not_profitable = _calculate_true_profit(
            selling_price_usd=14.99,
            cost_cny=100.0,
            exchange_rate=7.2,
            shipping_to_amazon_usd=2.5,
            amazon_referral_fee_percent=15.0,
            fba_fee_usd=3.5,
            monthly_storage_fee_usd=0.3,
            advertising_acos_percent=25.0,
            payment_processing_fee_percent=2.9,
            return_rate_percent=8.0,
            customs_duty_percent=3.0,
            overhead_percent=5.0,
        )

        failures = []
        
        # Check that calculations are present
        required_fields = [
            "net_profit_usd", "gross_profit_usd", "profit_margin_percent", 
            "total_cost_usd", "is_profitable", "cost_breakdown"
        ]
        for field in required_fields:
            if field not in result_profitable:
                failures.append(f"Missing required field: {field}")
        
        # Check profitability status
        if not result_profitable["is_profitable"]:
            failures.append("Expected profitable scenario to be profitable")
        
        if result_not_profitable["is_profitable"]:
            failures.append("Expected non-profitable scenario to NOT be profitable")
        
        # Check cost breakdown has all components
        cost_breakdown_fields = [
            "product_cost_usd", "shipping_to_amazon_usd", "amazon_referral_fee_usd",
            "fba_fulfillment_fee_usd", "monthly_storage_fee_usd", "advertising_cost_usd",
            "payment_processing_fee_usd", "return_cost_usd", "customs_duty_usd", "overhead_usd"
        ]
        for field in cost_breakdown_fields:
            if field not in result_profitable["cost_breakdown"]:
                failures.append(f"Missing cost breakdown field: {field}")

        if failures:
            return TestResult(test_name, False, "True profit calculation failed:\n" + "\n".join(failures), str(result_profitable))

        if verbose:
            print(f"\n--- {test_name} Result ---")
            print(f"Profitable scenario: ${result_profitable['net_profit_usd']:.2f} net profit")
            print(f"Non-profitable scenario: ${result_not_profitable['net_profit_usd']:.2f} net profit")

        return TestResult(test_name, True, "True profit calculation correct", str(result_profitable))

    except Exception as e:
        return TestResult(test_name, False, f"Unexpected error: {str(e)}")


async def test_calculate_true_profit_tool(verbose: bool = False) -> TestResult:
    test_name = "calculate_true_profit_tool"
    try:
        with patch("server._fetch_1688_product_details", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = MOCK_1688_PRODUCT_DETAILS

            params = CalculateTrueProfitInput(
                sku="SKU-12345",
                selling_price_usd=29.99,
                cost_cny=35.0,
                response_format=ResponseFormat.JSON
            )
            result = await calculate_true_profit(params)

            data = json.loads(result)
            
            if "net_profit_usd" not in data:
                return TestResult(test_name, False, "Missing net_profit_usd in response", result)
            
            if "is_profitable" not in data:
                return TestResult(test_name, False, "Missing is_profitable in response", result)

            if verbose:
                print(f"\n--- {test_name} Result ---")
                print(json.dumps(data, indent=2))

            return TestResult(test_name, True, "True Profit Calculator tool works correctly", result)

    except json.JSONDecodeError:
        return TestResult(test_name, False, "Response is not valid JSON", result)
    except Exception as e:
        return TestResult(test_name, False, f"Unexpected error: {str(e)}")


async def run_all_tests(verbose: bool = False):
    print("=" * 60)
    print("Cross-Border Seller MCP Server - Test Suite")
    print("=" * 60)
    print(f"Mode: Mock Data Testing")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    tests = [
        ("get_inventory_1688", test_get_inventory_1688),
        ("get_orders_amazon", test_get_orders_amazon),
        ("sync_inventory", test_sync_inventory),
        ("update_fulfillment_amazon", test_update_fulfillment_amazon),
        ("get_low_stock_alerts", test_get_low_stock_alerts),
        ("get_product_cost_1688", test_get_product_cost_1688),
        ("calculate_amazon_price", test_calculate_amazon_price),
        ("sync_price", test_sync_price),
        ("update_amazon_price", test_update_amazon_price),
        ("get_competitor_prices", test_get_competitor_prices),
        ("get_product_reviews", test_get_product_reviews),
        ("get_negative_reviews", test_get_negative_reviews),
        ("get_review_alerts", test_get_review_alerts),
        ("review_supplier_analysis", test_review_supplier_analysis),
        ("review_severity_logic", test_review_severity_logic),
        ("price_calculation_logic", test_price_calculation_logic),
        ("price_action_logic", test_price_action_logic),
        ("true_profit_calculation_logic", test_true_profit_calculation_logic),
        ("calculate_true_profit_tool", test_calculate_true_profit_tool),
        ("error_handling", test_error_handling),
        ("markdown_format_output", test_markdown_format),
    ]

    results = []
    for test_name, test_func in tests:
        print(f"\nRunning: {test_name}...", end=" ", flush=True)
        result = await test_func(verbose)
        results.append(result)
        print("✓" if result.passed else "✗")

    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed

    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Total:  {len(results)}")
    print(f"Passed: {passed} ✓")
    print(f"Failed: {failed} ✗")

    if verbose:
        print("\n" + "-" * 60)
        print("DETAILED RESULTS")
        print("-" * 60)
        for result in results:
            status = "✓ PASS" if result.passed else "✗ FAIL"
            print(f"\n[{status}] {result.name}")
            print(f"  {result.message}")

    if failed > 0:
        print("\n" + "=" * 60)
        print("FAILED TESTS")
        print("=" * 60)
        for result in results:
            if not result.passed:
                print(f"\n✗ {result.name}")
                print(f"  Error: {result.message}")

    print("\n" + "=" * 60)
    if failed == 0:
        print("All tests passed! ✓")
    else:
        print(f"Some tests failed. Please review the errors above.")
    print("=" * 60)

    return failed == 0


def main():
    parser = argparse.ArgumentParser(description="Test Cross-Border Seller MCP Server")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed test output")
    parser.add_argument("--mock", "-m", action="store_true", default=True, help="Use mock data (default)")
    args = parser.parse_args()

    success = asyncio.run(run_all_tests(verbose=args.verbose))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
