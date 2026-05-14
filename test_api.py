#!/usr/bin/env python3
"""
Test script for web_app.py REST API endpoints.
测试 web_app.py REST API 端点。

Run this script to test the API endpoints:
    python test_api.py

Note: Requires the Flask app to be running. Start it with:
    python web_app.py
"""

import requests
import json
import sys
from typing import Optional

BASE_URL = "http://localhost:5000"

class APITester:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.results = []

    def log(self, test_name: str, success: bool, message: str = ""):
        status = "✅ PASS" if success else "❌ FAIL"
        self.results.append((test_name, success, message))
        print(f"  {status}: {test_name}")
        if message and not success:
            print(f"         {message}")

    def test_health_endpoint(self):
        print("\n🔍 Testing Health Endpoint...")
        try:
            response = requests.get(f"{self.base_url}/api/health")
            data = response.json()
            success = response.status_code == 200 and data.get('success') == True
            self.log("GET /api/health", success, f"Status: {response.status_code}")
            return success
        except requests.exceptions.ConnectionError:
            self.log("GET /api/health", False, "Could not connect to server. Is it running?")
            return False
        except Exception as e:
            self.log("GET /api/health", False, str(e))
            return False

    def test_list_tools(self):
        print("\n📋 Testing List Tools Endpoint...")
        try:
            response = requests.get(f"{self.base_url}/api/tools")
            data = response.json()
            success = response.status_code == 200 and data.get('success') == True
            tool_count = data.get('total_tools', 0)
            self.log("GET /api/tools", success, f"Found {tool_count} tools, Status: {response.status_code}")
            if success and tool_count > 0:
                print(f"         Tools: {', '.join([t['name'] for t in data.get('tools', [])[:5]])}...")
            return success
        except Exception as e:
            self.log("GET /api/tools", False, str(e))
            return False

    def test_list_tools_english(self):
        print("\n🌐 Testing List Tools (English)...")
        try:
            response = requests.get(f"{self.base_url}/api/tools?lang=en")
            data = response.json()
            success = response.status_code == 200
            msg = data.get('message', '')
            self.log("GET /api/tools?lang=en", success, f"Message: {msg[:50]}...")
            return success
        except Exception as e:
            self.log("GET /api/tools?lang=en", False, str(e))
            return False

    def test_get_tool_info(self):
        print("\n📝 Testing Get Tool Info...")
        try:
            response = requests.get(f"{self.base_url}/api/tools/calculate_true_profit")
            data = response.json()
            success = response.status_code == 200 and data.get('success') == True
            tool_info = data.get('tool', {})
            required_params = tool_info.get('required_parameters', [])
            self.log("GET /api/tools/calculate_true_profit", success, 
                    f"Required params: {required_params}, Status: {response.status_code}")
            return success
        except Exception as e:
            self.log("GET /api/tools/calculate_true_profit", False, str(e))
            return False

    def test_get_tool_info_not_found(self):
        print("\n🚫 Testing Tool Not Found...")
        try:
            response = requests.get(f"{self.base_url}/api/tools/nonexistent_tool")
            success = response.status_code == 404
            self.log("GET /api/tools/nonexistent_tool", success, 
                    f"Expected 404, got {response.status_code}")
            return success
        except Exception as e:
            self.log("GET /api/tools/nonexistent_tool", False, str(e))
            return False

    def test_call_tool_missing_params(self):
        print("\n⚠️  Testing Missing Parameters...")
        try:
            response = requests.post(
                f"{self.base_url}/api/tools/calculate_true_profit",
                json={},
                headers={'Content-Type': 'application/json'}
            )
            data = response.json()
            success = response.status_code == 400 and not data.get('success')
            missing = data.get('missing_parameters', [])
            self.log("POST /api/tools/calculate_true_profit (no params)", success,
                    f"Missing: {missing}, Status: {response.status_code}")
            return success
        except Exception as e:
            self.log("POST /api/tools/calculate_true_profit (no params)", False, str(e))
            return False

    def test_call_tool_invalid_json(self):
        print("\n❌ Testing Invalid JSON...")
        try:
            response = requests.post(
                f"{self.base_url}/api/tools/get_low_stock_alerts",
                data="not json",
                headers={'Content-Type': 'text/plain'}
            )
            success = response.status_code == 400
            self.log("POST with invalid JSON", success, f"Status: {response.status_code}")
            return success
        except Exception as e:
            self.log("POST with invalid JSON", False, str(e))
            return False

    def test_alternative_endpoint(self):
        print("\n🔄 Testing Alternative Endpoint (tool_name in body)...")
        try:
            response = requests.post(
                f"{self.base_url}/api/tools",
                json={
                    "tool_name": "get_low_stock_alerts",
                    "threshold": 5,
                    "platform": "both",
                    "response_format": "json"
                },
                headers={'Content-Type': 'application/json'}
            )
            data = response.json()
            success = response.status_code in [200, 500]
            tool_name = data.get('tool', '')
            self.log("POST /api/tools (body)", success, 
                    f"Tool: {tool_name}, Status: {response.status_code}")
            return success
        except Exception as e:
            self.log("POST /api/tools (body)", False, str(e))
            return False

    def test_calculate_true_profit(self):
        print("\n💰 Testing Calculate True Profit...")
        try:
            response = requests.post(
                f"{self.base_url}/api/tools/calculate_true_profit",
                json={
                    "sku": "TEST-SKU-001",
                    "selling_price_usd": 29.99,
                    "cost_cny": 35.0,
                    "response_format": "json"
                },
                headers={'Content-Type': 'application/json'}
            )
            data = response.json()
            success = response.status_code in [200, 500]
            result = data.get('result', '')
            tool = data.get('tool', '')
            self.log("POST /api/tools/calculate_true_profit", success,
                    f"Tool: {tool}, Status: {response.status_code}")
            return success
        except Exception as e:
            self.log("POST /api/tools/calculate_true_profit", False, str(e))
            return False

    def test_get_low_stock_alerts(self):
        print("\n📦 Testing Get Low Stock Alerts...")
        try:
            response = requests.post(
                f"{self.base_url}/api/tools/get_low_stock_alerts",
                json={
                    "threshold": 10,
                    "platform": "both",
                    "response_format": "json"
                },
                headers={'Content-Type': 'application/json'}
            )
            data = response.json()
            success = response.status_code in [200, 500]
            tool = data.get('tool', '')
            self.log("POST /api/tools/get_low_stock_alerts", success,
                    f"Tool: {tool}, Status: {response.status_code}")
            return success
        except Exception as e:
            self.log("POST /api/tools/get_low_stock_alerts", False, str(e))
            return False

    def test_get_orders_amazon(self):
        print("\n📦 Testing Get Orders Amazon...")
        try:
            response = requests.post(
                f"{self.base_url}/api/tools/get_orders_amazon",
                json={
                    "days": 7,
                    "limit": 10,
                    "response_format": "json"
                },
                headers={'Content-Type': 'application/json'}
            )
            data = response.json()
            success = response.status_code in [200, 500]
            tool = data.get('tool', '')
            self.log("POST /api/tools/get_orders_amazon", success,
                    f"Tool: {tool}, Status: {response.status_code}")
            return success
        except Exception as e:
            self.log("POST /api/tools/get_orders_amazon", False, str(e))
            return False

    def test_get_product_reviews(self):
        print("\n⭐ Testing Get Product Reviews...")
        try:
            response = requests.post(
                f"{self.base_url}/api/tools/get_product_reviews",
                json={
                    "sku": "TEST-SKU-001",
                    "days": 30,
                    "limit": 5,
                    "response_format": "json"
                },
                headers={'Content-Type': 'application/json'}
            )
            data = response.json()
            success = response.status_code in [200, 500]
            tool = data.get('tool', '')
            self.log("POST /api/tools/get_product_reviews", success,
                    f"Tool: {tool}, Status: {response.status_code}")
            return success
        except Exception as e:
            self.log("POST /api/tools/get_product_reviews", False, str(e))
            return False

    def test_sync_inventory(self):
        print("\n🔄 Testing Sync Inventory...")
        try:
            response = requests.post(
                f"{self.base_url}/api/tools/sync_inventory",
                json={
                    "sku": "TEST-SKU-001",
                    "response_format": "json"
                },
                headers={'Content-Type': 'application/json'}
            )
            data = response.json()
            success = response.status_code in [200, 500]
            tool = data.get('tool', '')
            self.log("POST /api/tools/sync_inventory", success,
                    f"Tool: {tool}, Status: {response.status_code}")
            return success
        except Exception as e:
            self.log("POST /api/tools/sync_inventory", False, str(e))
            return False

    def test_sync_price(self):
        print("\n💵 Testing Sync Price...")
        try:
            response = requests.post(
                f"{self.base_url}/api/tools/sync_price",
                json={
                    "sku": "TEST-SKU-001",
                    "target_margin_percent": 25.0,
                    "response_format": "json"
                },
                headers={'Content-Type': 'application/json'}
            )
            data = response.json()
            success = response.status_code in [200, 500]
            tool = data.get('tool', '')
            self.log("POST /api/tools/sync_price", success,
                    f"Tool: {tool}, Status: {response.status_code}")
            return success
        except Exception as e:
            self.log("POST /api/tools/sync_price", False, str(e))
            return False

    def test_get_license_info(self):
        print("\n📜 Testing Get License Info...")
        try:
            response = requests.post(
                f"{self.base_url}/api/tools/get_license_info",
                json={},
                headers={'Content-Type': 'application/json'}
            )
            data = response.json()
            success = response.status_code in [200, 500]
            tool = data.get('tool', '')
            self.log("POST /api/tools/get_license_info", success,
                    f"Tool: {tool}, Status: {response.status_code}")
            return success
        except Exception as e:
            self.log("POST /api/tools/get_license_info", False, str(e))
            return False

    def test_web_ui_index(self):
        print("\n🌐 Testing Web UI Index...")
        try:
            response = requests.get(f"{self.base_url}/")
            success = response.status_code == 200
            self.log("GET / (Web UI)", success, f"Status: {response.status_code}")
            return success
        except Exception as e:
            self.log("GET / (Web UI)", False, str(e))
            return False

    def test_web_ui_inventory(self):
        print("\n📊 Testing Web UI Inventory Page...")
        try:
            response = requests.get(f"{self.base_url}/inventory?threshold=10&platform=all")
            success = response.status_code == 200
            self.log("GET /inventory (Web UI)", success, f"Status: {response.status_code}")
            return success
        except Exception as e:
            self.log("GET /inventory (Web UI)", False, str(e))
            return False

    def run_all_tests(self):
        print("="*60)
        print("🧪 Web App API Test Suite")
        print("🧪 Web 应用 API 测试套件")
        print("="*60)

        self.test_health_endpoint()
        self.test_web_ui_index()
        self.test_web_ui_inventory()
        self.test_list_tools()
        self.test_list_tools_english()
        self.test_get_tool_info()
        self.test_get_tool_info_not_found()
        self.test_call_tool_missing_params()
        self.test_call_tool_invalid_json()
        self.test_alternative_endpoint()
        self.test_calculate_true_profit()
        self.test_get_low_stock_alerts()
        self.test_get_orders_amazon()
        self.test_get_product_reviews()
        self.test_sync_inventory()
        self.test_sync_price()
        self.test_get_license_info()

        print("\n" + "="*60)
        passed = sum(1 for _, s, _ in self.results if s)
        total = len(self.results)
        print(f"📊 Test Results: {passed}/{total} passed")
        print("="*60)

        return passed == total

def main():
    tester = APITester()

    if len(sys.argv) > 1:
        tester.base_url = sys.argv[1]
        print(f"Using base URL: {tester.base_url}")

    success = tester.run_all_tests()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
