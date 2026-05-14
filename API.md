# Cross-Border Seller API Documentation

Complete API reference for the Cross-Border Seller MCP Server, enabling integration between 1688 (China supplier platform) and Amazon Seller Central.

---

## Table of Contents

- [Authentication](#authentication)
- [Base URL and Headers](#base-url-and-headers)
- [API Endpoints](#api-endpoints)
  - [Tools API](#tools-api)
  - [Authentication API](#authentication-api)
  - [User Management API](#user-management-api)
- [Error Codes](#error-codes)
- [Rate Limiting](#rate-limiting)
- [Code Examples](#code-examples)

---

## Authentication

The API supports two authentication methods:

### 1. Session Cookie (Web UI)

After logging in via the web interface, a `session_id` cookie is set automatically. The server handles authentication for subsequent requests.

**Login Endpoint:** `POST /api/auth/login`

```json
{
  "email": "user@example.com",
  "password": "yourpassword"
}
```

**Response:**
```json
{
  "success": true,
  "user": {
    "user_id": "uuid",
    "email": "user@example.com",
    "role": "admin"
  }
}
```

### 2. API Key (Programmatic Access)

For programmatic access, use API keys with the `X-API-Key` header.

**Creating an API Key:**
```bash
POST /api/auth/api-keys
Content-Type: application/json

{
  "name": "My Application",
  "rate_limit": 60
}
```

**Response:**
```json
{
  "key_id": "uuid",
  "api_key": "YOUR_API_KEY_HERE",
  "name": "My Application",
  "rate_limit": 60,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Using the API Key:**
```bash
X-API-Key: YOUR_API_KEY_HERE
```

**Or via Authorization header:**
```bash
Authorization: Bearer YOUR_API_KEY_HERE
```

---

## Base URL and Headers

### Base URL

| Environment | URL |
|-------------|-----|
| Local Development | `http://localhost:5000` |
| Production | `https://your-domain.com` |

### Required Headers

```bash
Content-Type: application/json
Accept: application/json
```

### Authentication Headers

**Session Cookie:**
```bash
Cookie: session_id=your_session_id
```

**API Key:**
```bash
X-API-Key: YOUR_API_KEY_HERE
```

---

## API Endpoints

### Tools API

#### List All Tools

Retrieve a list of all available MCP tools.

```bash
GET /api/tools
```

**Response:**
```json
{
  "tools": [
    {
      "name": "get_inventory_1688",
      "description": "Get stock level for a SKU from 1688 supplier platform",
      "parameters": {
        "sku": {"type": "string", "required": true},
        "response_format": {"type": "string", "required": false, "enum": ["json", "markdown"]}
      }
    }
  ]
}
```

---

#### Get Tool Info

Get detailed information about a specific tool.

```bash
GET /api/tools/<tool_name>
```

**Example:** `GET /api/tools/get_inventory_1688`

**Response:**
```json
{
  "name": "get_inventory_1688",
  "description": "Get stock level for a SKU from 1688 supplier platform",
  "parameters": {
    "sku": {
      "type": "string",
      "required": true,
      "description": "SKU identifier for the product"
    },
    "response_format": {
      "type": "string",
      "required": false,
      "enum": ["json", "markdown"],
      "default": "json"
    }
  }
}
```

---

#### Call Tool

Execute a specific MCP tool with parameters.

```bash
POST /api/tools/<tool_name>
```

**Example:** `POST /api/tools/get_inventory_1688`

**Request Body:**
```json
{
  "sku": "SKU-12345",
  "response_format": "json"
}
```

**Response:**
```json
{
  "sku": "SKU-12345",
  "product_name": "Wireless Bluetooth Headphones",
  "stock_quantity": 500,
  "available_quantity": 450,
  "supplier_info": {
    "name": "Shenzhen Electronics Co.",
    "location": "Guangdong, China"
  }
}
```

---

### Available Tools

#### Inventory Management

##### get_inventory_1688

Get stock level for a SKU from 1688 platform.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| sku | string | Yes | Product SKU identifier |
| response_format | string | No | "json" or "markdown" (default: json) |

##### get_orders_amazon

Fetch recent Amazon orders.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| days | integer | No | Days to look back (1-90, default: 7) |
| status | string | No | Filter by status |
| limit | integer | No | Max orders (1-100, default: 50) |
| response_format | string | No | "json" or "markdown" |

##### sync_inventory

Compare 1688 stock vs Amazon listing, flag mismatches.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| sku | string | Yes | Product SKU to sync |
| response_format | string | No | "json" or "markdown" |

##### update_fulfillment_amazon

Update order fulfillment status on Amazon.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| order_id | string | Yes | Amazon order ID |
| status | string | Yes | New status (Pending, Processing, Shipped, Delivered, Cancelled) |

##### get_low_stock_alerts

Return all SKUs where stock is below threshold.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| threshold | integer | No | Custom threshold (default: 10) |
| platform | string | No | "1688", "Amazon", or "both" |
| response_format | string | No | "json" or "markdown" |

---

#### Pricing Tools

##### get_product_cost_1688

Get product pricing from 1688.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| sku | string | Yes | Product SKU |
| response_format | string | No | "json" or "markdown" |

##### calculate_amazon_price

Calculate recommended Amazon selling price.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| sku | string | Yes | Product SKU |
| cost_cny | float | No | Cost in CNY (fetches from 1688 if not provided) |
| target_margin_percent | float | No | Target margin (default: 25) |
| shipping_cost_usd | float | No | Shipping cost (default: 2.0) |
| response_format | string | No | "json" or "markdown" |

##### sync_price

Compare 1688 cost against current Amazon prices.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| sku | string | Yes | Product SKU |
| target_margin_percent | float | No | Target margin (default: 25) |
| shipping_cost_usd | float | No | Shipping cost (default: 2.0) |
| response_format | string | No | "json" or "markdown" |

##### update_amazon_price

Update Amazon listing price.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| sku | string | Yes | Product SKU |
| new_price | float | Yes | New price in USD |
| currency | string | No | Currency code (default: USD) |

##### calculate_true_profit

Calculate TRUE profit including all cost factors.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| sku | string | Yes | Product SKU |
| selling_price_usd | float | Yes | Current selling price |
| cost_cny | float | No | Product cost in CNY |
| shipping_to_amazon_usd | float | No | Shipping cost (default: 2.0) |
| amazon_referral_fee_percent | float | No | Referral fee % (default: 15) |
| fba_fee_usd | float | No | FBA fee (default: 3.5) |
| advertising_acos_percent | float | No | ACoS % (default: 20) |
| return_rate_percent | float | No | Return rate % (default: 5) |
| customs_duty_percent | float | No | Customs duty % (default: 3) |
| response_format | string | No | "json" or "markdown" |

---

#### Review Tools

##### get_competitor_prices

Search Amazon for competitor prices.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| sku | string | Yes | SKU or search keyword |
| limit | integer | No | Max competitors (1-20, default: 5) |
| response_format | string | No | "json" or "markdown" |

##### get_product_reviews

Get product reviews from Amazon.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| sku | string | Yes | SKU or ASIN |
| days | integer | No | Days to look back (default: 30) |
| min_rating | integer | No | Min rating filter (1-5) |
| max_rating | integer | No | Max rating filter (1-5) |
| limit | integer | No | Max reviews (default: 20) |
| response_format | string | No | "json" or "markdown" |

##### get_negative_reviews

Get 1-2 star reviews needing attention.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| sku | string | No | Filter by SKU |
| days | integer | No | Days to look back (default: 7) |
| severity | string | No | "critical", "warning", or "all" (default: all) |
| response_format | string | No | "json" or "markdown" |

##### get_review_alerts

Get actionable alerts for reviews needing attention.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| days | integer | No | Days to look back (default: 7) |
| include_supplier_flags | boolean | No | Enable supplier issue detection (default: true) |
| response_format | string | No | "json" or "markdown" |

---

#### Product Profile Tools

##### save_product_profile

Save product cost data for quick access.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| sku | string | Yes | SKU identifier |
| product_name | string | No | Product name |
| cost_cny | float | No | Cost in CNY |
| shipping_to_amazon_usd | float | No | Shipping cost |
| amazon_referral_fee_percent | float | No | Referral fee % |
| fba_fee_usd | float | No | FBA fee |
| monthly_storage_fee_usd | float | No | Storage fee |
| advertising_acos_percent | float | No | ACoS % |
| payment_processing_fee_percent | float | No | Payment fee % |
| return_rate_percent | float | No | Return rate % |
| customs_duty_percent | float | No | Customs duty % |
| overhead_percent | float | No | Overhead % |
| notes | string | No | Additional notes |
| response_format | string | No | "json" or "markdown" |

##### get_product_profile

Get saved product data.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| sku | string | Yes | SKU identifier |
| response_format | string | No | "json" or "markdown" |

##### list_all_products

List all saved product profiles.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| hours | integer | No | Stale threshold hours (default: 24) |
| response_format | string | No | "json" or "markdown" |

##### get_stale_products

Find products with data needing updates.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| hours | integer | No | Stale threshold hours (default: 24) |
| response_format | string | No | "json" or "markdown" |

##### get_license_info

Get current license tier and features.

No parameters required.

---

### Authentication API

#### POST /api/auth/register

Register a new user account.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "securepassword",
  "role": "viewer"
}
```

**Response:**
```json
{
  "success": true,
  "user_id": "uuid",
  "email": "user@example.com",
  "role": "viewer"
}
```

---

#### POST /api/auth/login

Authenticate user and create session.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "securepassword",
  "remember_me": true
}
```

**Response:**
```json
{
  "success": true,
  "user": {
    "user_id": "uuid",
    "email": "user@example.com",
    "role": "admin"
  }
}
```

---

#### POST /api/auth/logout

End current session.

**Response:**
```json
{
  "success": true,
  "message": "Logged out successfully"
}
```

---

#### POST /api/auth/change-password

Change user password.

**Request:**
```json
{
  "old_password": "currentpassword",
  "new_password": "newsecurepassword"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Password changed successfully"
}
```

---

#### POST /api/auth/forgot-password

Request password reset.

**Request:**
```json
{
  "email": "user@example.com"
}
```

**Response:**
```json
{
  "success": true,
  "message": "If email exists, reset instructions will be sent"
}
```

---

#### POST /api/auth/reset-password

Reset password with token.

**Request:**
```json
{
  "reset_token": "token_from_email",
  "new_password": "newsecurepassword"
}
```

---

### User Management API

#### GET /api/users

List all users (admin only).

**Response:**
```json
{
  "users": [
    {
      "user_id": "uuid",
      "email": "user@example.com",
      "role": "admin",
      "created_at": "2024-01-15T10:30:00Z",
      "last_login": "2024-01-20T14:00:00Z",
      "is_active": true
    }
  ]
}
```

---

#### GET /api/users/{user_id}

Get user details.

---

#### PUT /api/users/{user_id}

Update user.

**Request:**
```json
{
  "email": "newemail@example.com",
  "role": "manager"
}
```

---

#### DELETE /api/users/{user_id}

Delete user (admin only).

---

#### POST /api/users/{user_id}/deactivate

Deactivate user account.

---

#### POST /api/users/{user_id}/activate

Activate user account.

---

### API Keys Management

#### GET /api/auth/api-keys

List user's API keys.

**Response:**
```json
{
  "api_keys": [
    {
      "key_id": "uuid",
      "name": "My Application",
      "rate_limit": 60,
      "created_at": "2024-01-15T10:30:00Z",
      "last_used": "2024-01-20T14:00:00Z",
      "is_active": true
    }
  ]
}
```

---

#### POST /api/auth/api-keys

Create new API key.

**Request:**
```json
{
  "name": "My Application",
  "rate_limit": 60
}
```

**Response:**
```json
{
  "key_id": "uuid",
  "api_key": "YOUR_API_KEY_HERE",
  "name": "My Application",
  "rate_limit": 60,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Important:** The `api_key` is only shown once. Save it securely.

---

#### DELETE /api/auth/api-keys/{key_id}

Revoke an API key.

---

### Web UI Pages

| Endpoint | Description |
|----------|-------------|
| `GET /` | Home dashboard |
| `GET /login` | Login page |
| `GET /register` | Registration page |
| `GET /forgot-password` | Password reset request |
| `GET /profit` | True profit calculator |
| `GET /inventory` | Low stock alerts |
| `GET /reviews` | Review monitoring |
| `GET /competitor` | Competitor price analysis |
| `GET /analytics` | Analytics dashboard |
| `GET /api/docs/` | Swagger UI documentation |

---

## Error Codes

### HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request - Invalid parameters |
| 401 | Unauthorized - Authentication required |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource doesn't exist |
| 429 | Too Many Requests - Rate limit exceeded |
| 500 | Internal Server Error |

### API Error Response Format

```json
{
  "error": "error_code",
  "message": "Human readable error message",
  "details": {}
}
```

### Common Error Codes

| Error Code | HTTP Status | Description |
|------------|-------------|-------------|
| `authentication_required` | 401 | No valid authentication provided |
| `invalid_credentials` | 401 | Email or password is incorrect |
| `token_expired` | 401 | JWT token has expired |
| `insufficient_permissions` | 403 | User lacks required role/permission |
| `user_disabled` | 403 | User account is disabled |
| `invalid_parameters` | 400 | Request parameters are invalid |
| `missing_required_field` | 400 | Required field is missing |
| `rate_limit_exceeded` | 429 | Request frequency limit reached |
| `resource_not_found` | 404 | Requested resource not found |
| `internal_error` | 500 | Server-side error occurred |

### Platform-Specific Error Messages

| Platform | Error | Description |
|----------|-------|-------------|
| 1688 | Authentication failed | Check ALIBABA_APP_KEY and ALIBABA_APP_SECRET |
| 1688 | Rate limit exceeded | Wait before making more requests |
| Amazon | Access denied | Check AMAZON_CLIENT_ID and AMAZON_CLIENT_SECRET |
| Amazon | Order not found | Verify the order ID |

---

## Rate Limiting

Rate limits are based on user subscription tiers:

| Tier | Requests/Hour | Description |
|------|---------------|-------------|
| FREE | 100 | Free tier users |
| BASIC | 1,000 | Basic tier subscribers |
| PRO | 10,000 | Pro tier subscribers |
| ENTERPRISE | Unlimited | Enterprise customers |

### Rate Limit Headers

Every API response includes rate limit information:

```bash
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 995
X-RateLimit-Reset: 1705326000
```

### Handling Rate Limits

When rate limited, the API returns:

```json
{
  "error": "rate_limit_exceeded",
  "message": "Rate limit exceeded. Please try again later.",
  "retry_after": 1705326000,
  "limit": 1000,
  "tier": "FREE"
}
```

### Best Practices

1. **Implement exponential backoff** for retry logic
2. **Cache responses** when appropriate
3. **Batch requests** where possible
4. **Monitor remaining requests** via headers
5. **Upgrade tier** if higher limits are needed

---

## Code Examples

### Python

#### Install Dependencies

```python
pip install requests
```

#### List Available Tools

```python
import requests

API_BASE = "http://localhost:5000"
API_KEY = "YOUR_API_KEY_HERE"

headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

response = requests.get(f"{API_BASE}/api/tools", headers=headers)
tools = response.json()
print(tools)
```

#### Get Inventory from 1688

```python
import requests

API_BASE = "http://localhost:5000"
API_KEY = "YOUR_API_KEY_HERE"

headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

payload = {
    "sku": "SKU-12345",
    "response_format": "json"
}

response = requests.post(
    f"{API_BASE}/api/tools/get_inventory_1688",
    headers=headers,
    json=payload
)

inventory = response.json()
print(f"Stock: {inventory['stock_quantity']}")
print(f"Available: {inventory['available_quantity']}")
```

#### Calculate Amazon Price

```python
import requests

API_BASE = "http://localhost:5000"
API_KEY = "YOUR_API_KEY_HERE"

headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

payload = {
    "sku": "SKU-12345",
    "cost_cny": 35.00,
    "target_margin_percent": 25,
    "shipping_cost_usd": 2.0,
    "response_format": "json"
}

response = requests.post(
    f"{API_BASE}/api/tools/calculate_amazon_price",
    headers=headers,
    json=payload
)

result = response.json()
print(f"Recommended Price: ${result['calculation']['recommended_price_usd']}")
```

#### Get Review Alerts

```python
import requests

API_BASE = "http://localhost:5000"
API_KEY = "YOUR_API_KEY_HERE"

headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

payload = {
    "days": 7,
    "include_supplier_flags": True,
    "response_format": "json"
}

response = requests.post(
    f"{API_BASE}/api/tools/get_review_alerts",
    headers=headers,
    json=payload
)

alerts = response.json()
print(f"Total Alerts: {alerts['total_alerts']}")
for alert in alerts['alerts'][:3]:
    print(f"  [{alert['priority']}] {alert['alert_type']}: {alert['action_required']}")
```

#### Complete Python Client

```python
import requests
from typing import Optional, Dict, Any

class CrossBorderSellerAPI:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "X-API-Key": api_key,
            "Content-Type": "application/json"
        })
    
    def list_tools(self) -> Dict[str, Any]:
        response = self.session.get(f"{self.base_url}/api/tools")
        response.raise_for_status()
        return response.json()
    
    def get_inventory_1688(self, sku: str) -> Dict[str, Any]:
        response = self.session.post(
            f"{self.base_url}/api/tools/get_inventory_1688",
            json={"sku": sku, "response_format": "json"}
        )
        response.raise_for_status()
        return response.json()
    
    def get_orders_amazon(self, days: int = 7) -> Dict[str, Any]:
        response = self.session.post(
            f"{self.base_url}/api/tools/get_orders_amazon",
            json={"days": days, "response_format": "json"}
        )
        response.raise_for_status()
        return response.json()
    
    def calculate_amazon_price(
        self,
        sku: str,
        cost_cny: Optional[float] = None,
        target_margin: float = 25.0
    ) -> Dict[str, Any]:
        payload = {
            "sku": sku,
            "target_margin_percent": target_margin,
            "response_format": "json"
        }
        if cost_cny:
            payload["cost_cny"] = cost_cny
        
        response = self.session.post(
            f"{self.base_url}/api/tools/calculate_amazon_price",
            json=payload
        )
        response.raise_for_status()
        return response.json()
    
    def sync_inventory(self, sku: str) -> Dict[str, Any]:
        response = self.session.post(
            f"{self.base_url}/api/tools/sync_inventory",
            json={"sku": sku, "response_format": "json"}
        )
        response.raise_for_status()
        return response.json()
    
    def get_low_stock_alerts(self, threshold: int = 10) -> Dict[str, Any]:
        response = self.session.post(
            f"{self.base_url}/api/tools/get_low_stock_alerts",
            json={"threshold": threshold, "response_format": "json"}
        )
        response.raise_for_status()
        return response.json()


# Usage
api = CrossBorderSellerAPI(
    base_url="http://localhost:5000",
    api_key="YOUR_API_KEY_HERE"
)

# Get low stock alerts
alerts = api.get_low_stock_alerts(threshold=10)
print(f"Low stock alerts: {alerts['total_alerts']}")

# Sync inventory
sync = api.sync_inventory("SKU-12345")
print(f"Amazon stock: {sync['target_stock']}")
print(f"1688 stock: {sync['source_stock']}")
```

---

### JavaScript / Node.js

#### Install Dependencies

```bash
npm install axios
```

#### List Available Tools

```javascript
const axios = require('axios');

const API_BASE = 'http://localhost:5000';
const API_KEY = 'YOUR_API_KEY_HERE';

async function listTools() {
  const response = await axios.get(`${API_BASE}/api/tools`, {
    headers: { 'X-API-Key': API_KEY }
  });
  console.log(response.data);
}

listTools();
```

#### Get Inventory from 1688

```javascript
const axios = require('axios');

const API_BASE = 'http://localhost:5000';
const API_KEY = 'YOUR_API_KEY_HERE';

async function getInventory(sku) {
  const response = await axios.post(
    `${API_BASE}/api/tools/get_inventory_1688`,
    {
      sku: sku,
      response_format: 'json'
    },
    {
      headers: { 
        'X-API-Key': API_KEY,
        'Content-Type': 'application/json'
      }
    }
  );
  
  const inventory = response.data;
  console.log(`Stock: ${inventory.stock_quantity}`);
  console.log(`Available: ${inventory.available_quantity}`);
  console.log(`Supplier: ${inventory.supplier_info.name}`);
}

getInventory('SKU-12345');
```

#### Calculate Amazon Price

```javascript
const axios = require('axios');

const API_BASE = 'http://localhost:5000';
const API_KEY = 'YOUR_API_KEY_HERE';

async function calculatePrice(sku, costCny) {
  const response = await axios.post(
    `${API_BASE}/api/tools/calculate_amazon_price`,
    {
      sku: sku,
      cost_cny: costCny,
      target_margin_percent: 25,
      shipping_cost_usd: 2.0,
      response_format: 'json'
    },
    {
      headers: {
        'X-API-Key': API_KEY,
        'Content-Type': 'application/json'
      }
    }
  );
  
  const result = response.data;
  const calc = result.calculation;
  
  console.log('=== Price Calculation ===');
  console.log(`Cost (CNY): ¥${calc.cost_cny}`);
  console.log(`Cost (USD): $${calc.cost_usd}`);
  console.log(`Total Cost: $${calc.total_cost_usd}`);
  console.log(`Recommended Price: $${calc.recommended_price_usd}`);
  console.log(`Profit: $${calc.actual_profit_usd}`);
  console.log(`Margin: ${calc.actual_margin_percent}%`);
}

calculatePrice('SKU-12345', 35.00);
```

#### Complete JavaScript Client

```javascript
const axios = require('axios');

class CrossBorderSellerAPI {
  constructor(baseUrl, apiKey) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.apiKey = apiKey;
    this.client = axios.create({
      baseURL: this.baseUrl,
      headers: {
        'X-API-Key': this.apiKey,
        'Content-Type': 'application/json'
      }
    });
  }

  async listTools() {
    const response = await this.client.get('/api/tools');
    return response.data;
  }

  async getInventory1688(sku) {
    const response = await this.client.post('/api/tools/get_inventory_1688', {
      sku,
      response_format: 'json'
    });
    return response.data;
  }

  async getOrdersAmazon(days = 7) {
    const response = await this.client.post('/api/tools/get_orders_amazon', {
      days,
      response_format: 'json'
    });
    return response.data;
  }

  async syncInventory(sku) {
    const response = await this.client.post('/api/tools/sync_inventory', {
      sku,
      response_format: 'json'
    });
    return response.data;
  }

  async calculateAmazonPrice(sku, options = {}) {
    const payload = {
      sku,
      target_margin_percent: options.targetMargin || 25,
      shipping_cost_usd: options.shippingCost || 2.0,
      response_format: 'json'
    };
    if (options.costCny) payload.cost_cny = options.costCny;
    
    const response = await this.client.post('/api/tools/calculate_amazon_price', payload);
    return response.data;
  }

  async getLowStockAlerts(threshold = 10) {
    const response = await this.client.post('/api/tools/get_low_stock_alerts', {
      threshold,
      response_format: 'json'
    });
    return response.data;
  }

  async getReviewAlerts(days = 7, includeSupplierFlags = true) {
    const response = await this.client.post('/api/tools/get_review_alerts', {
      days,
      include_supplier_flags: includeSupplierFlags,
      response_format: 'json'
    });
    return response.data;
  }

  async updateAmazonPrice(sku, newPrice, currency = 'USD') {
    const response = await this.client.post('/api/tools/update_amazon_price', {
      sku,
      new_price: newPrice,
      currency
    });
    return response.data;
  }
}

// Usage
const api = new CrossBorderSellerAPI(
  'http://localhost:5000',
  'YOUR_API_KEY_HERE'
);

async function main() {
  // Get low stock alerts
  const alerts = await api.getLowStockAlerts(10);
  console.log(`Low stock alerts: ${alerts.total_alerts}`);

  // Check inventory sync
  const sync = await api.syncInventory('SKU-12345');
  console.log(`Mismatch detected: ${sync.mismatch_detected}`);

  // Calculate optimal price
  const priceCalc = await api.calculateAmazonPrice('SKU-12345', { 
    costCny: 35.00,
    targetMargin: 25
  });
  console.log(`Recommended price: $${priceCalc.calculation.recommended_price_usd}`);
}

main().catch(console.error);
```

---

### cURL

#### List All Tools

```bash
curl -X GET "http://localhost:5000/api/tools" \
  -H "X-API-Key: YOUR_API_KEY_HERE"
```

#### Get Inventory from 1688

```bash
curl -X POST "http://localhost:5000/api/tools/get_inventory_1688" \
  -H "X-API-Key: YOUR_API_KEY_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "sku": "SKU-12345",
    "response_format": "json"
  }'
```

#### Get Amazon Orders

```bash
curl -X POST "http://localhost:5000/api/tools/get_orders_amazon" \
  -H "X-API-Key: YOUR_API_KEY_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "days": 7,
    "limit": 20,
    "response_format": "json"
  }'
```

#### Calculate Amazon Price

```bash
curl -X POST "http://localhost:5000/api/tools/calculate_amazon_price" \
  -H "X-API-Key: YOUR_API_KEY_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "sku": "SKU-12345",
    "cost_cny": 35.00,
    "target_margin_percent": 25,
    "shipping_cost_usd": 2.0,
    "response_format": "json"
  }'
```

#### Sync Inventory

```bash
curl -X POST "http://localhost:5000/api/tools/sync_inventory" \
  -H "X-API-Key: YOUR_API_KEY_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "sku": "SKU-12345",
    "response_format": "json"
  }'
```

#### Get Low Stock Alerts

```bash
curl -X POST "http://localhost:5000/api/tools/get_low_stock_alerts" \
  -H "X-API-Key: YOUR_API_KEY_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "threshold": 10,
    "platform": "both",
    "response_format": "json"
  }'
```

#### Update Amazon Price

```bash
curl -X POST "http://localhost:5000/api/tools/update_amazon_price" \
  -H "X-API-Key: YOUR_API_KEY_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "sku": "SKU-12345",
    "new_price": 10.52,
    "currency": "USD"
  }'
```

#### Get Review Alerts

```bash
curl -X POST "http://localhost:5000/api/tools/get_review_alerts" \
  -H "X-API-Key: YOUR_API_KEY_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "days": 7,
    "include_supplier_flags": true,
    "response_format": "json"
  }'
```

#### User Login

```bash
curl -X POST "http://localhost:5000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "yourpassword",
    "remember_me": true
  }' \
  -c cookies.txt
```

#### Create API Key

```bash
curl -X POST "http://localhost:5000/api/auth/api-keys" \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "name": "My Application",
    "rate_limit": 60
  }'
```

#### View Swagger Documentation

```bash
# Open in browser
open "http://localhost:5000/api/docs/"

# Or get JSON spec
curl "http://localhost:5000/api/docs.json" \
  -H "X-API-Key: YOUR_API_KEY_HERE"
```

---

## Additional Resources

- [Swagger UI Documentation](http://localhost:5000/api/docs/) - Interactive API explorer
- [Main README](README.md) - Project overview and setup instructions
- [中文文档](README_CN.md) - Chinese documentation
