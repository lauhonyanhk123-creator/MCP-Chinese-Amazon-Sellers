# Cross-Border Seller MCP Server

跨境卖家MCP服务器 - 连接1688与亚马逊库存管理

A Model Context Protocol (MCP) server for cross-border e-commerce sellers to manage inventory between 1688 (China supplier platform) and Amazon Seller Central.

跨境电商卖家的MCP服务器，用于管理1688（中国供应商平台）和亚马逊卖家中心的库存。

---

## 🇨🇳 中文用户请看这里！

如果您是中国卖家，建议首先阅读：

- **[中文快速入门文档](README_CN.md)** - 3分钟快速上手指南
- **[中文配置文件示例](.env.cn.example)** - 已翻译的配置文件模板

---

## Table of Contents | 目录

- [Features | 功能特点](#features--功能特点)
- [Prerequisites | 前提条件](#prerequisites--前提条件)
- [Installation | 安装](#installation--安装)
- [Configuration | 配置](#configuration--配置)
- [Running the Server | 运行服务器](#running-the-server--运行服务器)
- [Available Tools | 可用工具](#available-tools--可用工具)
- [API Reference | API参考](#api-reference--api参考)
- [Testing | 测试](#testing--测试)
- [API Setup Guides | API设置指南](#api-setup-guides--api设置指南)
- [Troubleshooting | 故障排除](#troubleshooting--故障排除)

---

## Features | 功能特点

- **Multi-Platform Support | 多平台支持**: Connect to both 1688 and Amazon APIs
- **Inventory Sync | 库存同步**: Compare stock levels across platforms
- **Price Sync | 价格同步**: Calculate optimal Amazon prices based on 1688 costs
- **Order Management | 订单管理**: Fetch and update Amazon orders
- **Low Stock Alerts | 低库存警报**: Automatic alerts when stock is below threshold
- **Competitor Analysis | 竞品分析**: Research competitor pricing on Amazon
- **Review Monitor | 评论监控**: Track Amazon reviews and identify supplier quality issues
- **Smart Alerts | 智能提醒**: Automated alerts with suggested responses for negative reviews
- **Bilingual Support | 双语支持**: Full English and Chinese documentation

---

## Prerequisites | 前提条件

### Required | 必要条件

- Python 3.10 or higher | Python 3.10或更高版本
- pip or uv package manager | pip或uv包管理器
- 1688 Open Platform account | 1688开放平台账号
- Amazon Selling Partner API access | 亚马逊SP-API访问权限

### Optional | 可选条件

- Claude Desktop (for MCP integration) | Claude Desktop（用于MCP集成）

---

## Installation | 安装

### 1. Clone or Download | 1. 克隆或下载

```bash
# Clone the repository
git clone <repository-url>
cd crossborder_seller_mcp

# Or download and extract
unzip crossborder_seller_mcp.zip
cd crossborder_seller_mcp
```

### 2. Create Virtual Environment | 2. 创建虚拟环境

```bash
# Using venv
python -m venv venv

# Activate on Linux/macOS
source venv/bin/activate

# Activate on Windows
venv\Scripts\activate
```

### 3. Install Dependencies | 3. 安装依赖

```bash
# Using pip
pip install -r requirements.txt

# Or using uv (recommended)
uv pip install -r requirements.txt
```

---

## Configuration | 配置

### 1. Copy Environment File | 1. 复制环境文件

```bash
cp .env.example .env
```

### 2. Configure API Credentials | 2. 配置API凭据

Edit the `.env` file with your API credentials:

#### 1688/Alibaba Configuration | 1688/阿里巴巴配置

```
ALIBABA_APP_KEY=your_alibaba_app_key
ALIBABA_APP_SECRET=your_alibaba_app_secret
ALIBABA_API_KEY=your_alibaba_access_token
```

Get these from: [Alibaba Open Platform](https://open.1688.com/)

#### Amazon Selling Partner API Configuration | 亚马逊SP-API配置

```
AMAZON_CLIENT_ID=your_amazon_client_id
AMAZON_CLIENT_SECRET=your_amazon_client_secret
AMAZON_REFRESH_TOKEN=your_amazon_refresh_token
AMAZON_MARKETPLACE_ID=ATVPDKIKX0DER  # US marketplace
```

Get these from: [Amazon Seller Central](https://sellercentral.amazon.com/) > Partner Network

#### General Settings | 通用设置

```
LOW_STOCK_THRESHOLD=10  # Alert when stock falls below this number
```

---

## Running the Server | 运行服务器

### Development Mode | 开发模式

```bash
# Using mcp CLI
mcp dev server.py

# Or directly with Python
python server.py
```

### Claude Desktop Integration | Claude Desktop集成

```bash
# Install the server
mcp install server.py

# Or with a custom name
mcp install server.py --name "CrossBorder Seller"

# With environment variables
mcp install server.py -f .env
```

### Stdio Transport (Default) | 标准IO传输（默认）

```bash
python server.py
```

### Streamable HTTP (Remote) | 流式HTTP（远程）

```bash
python server.py --transport streamable_http --port 8000
```

### Web UI Production Deployment | Web界面生产部署

For production environments, use Gunicorn instead of the Flask development server:

```bash
# Install Gunicorn
pip install gunicorn

# Run with Gunicorn (4 workers)
gunicorn -w 4 -b 0.0.0.0:5000 web_app:app

# Or use the production start script
./start_prod.sh

# With custom configuration
PORT=8080 WORKERS=8 ./start_prod.sh
```

Production features:
- Multiple worker processes for better concurrency
- Production-grade error handling
- Access and error logging

---

## Available Tools | 可用工具

### 1. get_inventory_1688 | 获取1688库存

Get stock level for a SKU from 1688 platform.

从1688平台获取SKU的库存水平。

**Parameters | 参数:**
- `sku` (string, required): Product SKU | 产品SKU
- `response_format` (string, optional): "json" or "markdown"

**Example | 示例:**
```python
# Input
{"sku": "SKU-12345"}

# Output
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

### 2. get_orders_amazon | 获取亚马逊订单

Fetch recent Amazon orders from the last N days.

获取过去N天的亚马逊订单。

**Parameters | 参数:**
- `days` (integer, 1-90, default: 7): Number of days to look back | 回溯天数
- `status` (string, optional): Filter by status | 按状态过滤
- `limit` (integer, 1-100, default: 50): Maximum orders | 最大订单数
- `response_format` (string, optional): "json" or "markdown"

**Example | 示例:**
```python
# Input
{"days": 7, "limit": 20}

# Output
{
  "total_orders": 3,
  "orders": [
    {
      "order_id": "123-4567890-1234567",
      "status": "Shipped",
      "total_amount": "99.99",
      "currency": "USD"
    }
  ]
}
```

---

### 3. sync_inventory | 同步库存

Compare 1688 stock vs Amazon listing, flag mismatches.

比较1688库存与亚马逊上架情况，标记不匹配。

**Parameters | 参数:**
- `sku` (string, required): Product SKU to sync | 要同步的产品SKU
- `response_format` (string, optional): "json" or "markdown"

**Example | 示例:**
```python
# Input
{"sku": "SKU-12345"}

# Output
{
  "sku": "SKU-12345",
  "source_platform": "1688",
  "source_stock": 450,
  "target_platform": "Amazon",
  "target_stock": 100,
  "mismatch_detected": true,
  "mismatch_type": "overstock",
  "discrepancy": 350,
  "recommendation": "Amazon listing understocked by 350 units"
}
```

---

### 4. update_fulfillment_amazon | 更新亚马逊发货状态

Update order fulfillment status on Amazon.

更新亚马逊订单发货状态。

**Parameters | 参数:**
- `order_id` (string, required): Amazon order ID | 亚马逊订单ID
- `status` (string, required): New status | 新状态

**Valid Status Values | 有效状态值:**
- Pending | 待处理
- Processing | 处理中
- Shipped | 已发货
- Delivered | 已送达
- Cancelled | 已取消

**Example | 示例:**
```python
# Input
{"order_id": "123-4567890-1234567", "status": "Shipped"}

# Output
{
  "success": true,
  "order_id": "123-4567890-1234567",
  "new_status": "Shipped",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

---

### 5. get_low_stock_alerts | 获取低库存警报

Return all SKUs where stock is below threshold.

返回所有库存低于阈值的SKU。

**Parameters | 参数:**
- `threshold` (integer, optional): Custom threshold | 自定义阈值
- `platform` (string, optional): "1688", "Amazon", or "both"
- `response_format` (string, optional): "json" or "markdown"

**Example | 示例:**
```python
# Input
{"threshold": 10, "platform": "both"}

# Output
{
  "threshold_used": 10,
  "total_alerts": 2,
  "critical_count": 1,
  "warning_count": 1,
  "alerts": [
    {
      "sku": "SKU-67890",
      "platform": "1688",
      "current_stock": 3,
      "severity": "critical"
    }
  ]
}
```

---

### 6. get_product_cost_1688 | 获取1688产品成本

Get product pricing information from 1688 supplier platform.

从1688平台获取产品成本信息。

**Parameters | 参数:**
- `sku` (string, required): Product SKU | 产品SKU
- `response_format` (string, optional): "json" or "markdown"

**Example | 示例:**
```python
# Input
{"sku": "SKU-12345"}

# Output
{
  "sku": "SKU-12345",
  "product_name": "Wireless Bluetooth Headphones",
  "price_cny": 35.00,
  "price_usd": 4.86,
  "moq": 10,
  "supplier_info": {
    "name": "Shenzhen Electronics Co.",
    "location": "Guangdong, China"
  }
}
```

---

### 7. calculate_amazon_price | 计算亚马逊价格

Calculate recommended Amazon selling price based on 1688 cost.

根据1688成本计算推荐的亚马逊销售价格。

**Parameters | 参数:**
- `sku` (string, required): Product SKU | 产品SKU
- `cost_cny` (float, optional): Cost in CNY (fetches from 1688 if not provided) | CNY成本
- `target_margin_percent` (float, default: 25): Target profit margin | 目标利润率
- `shipping_cost_usd` (float, default: 2.0): Shipping cost per unit | 每件运输成本
- `response_format` (string, optional): "json" or "markdown"

**Price Calculation Formula | 价格计算公式:**
```
Cost USD = Cost CNY / Exchange Rate
Total Cost = Cost USD + Shipping + Amazon Fees (15%)
Price = Total Cost / (1 - Target Margin)
```

**Example | 示例:**
```python
# Input
{"sku": "SKU-12345", "target_margin_percent": 25, "shipping_cost_usd": 2.0}

# Output
{
  "sku": "SKU-12345",
  "calculation": {
    "cost_cny": 35.00,
    "cost_usd": 4.86,
    "shipping_cost_usd": 2.0,
    "amazon_fee_percent": 15.0,
    "amazon_fee_amount": 1.03,
    "total_cost_usd": 7.89,
    "recommended_price_usd": 10.52,
    "actual_profit_usd": 2.63,
    "actual_margin_percent": 25.0
  },
  "price_tiers": {
    "budget": 9.47,
    "standard": 10.52,
    "premium": 12.10
  }
}
```

---

### 8. sync_price | 同步价格

Compare 1688 cost-based pricing against current Amazon prices.

比较1688成本价与当前亚马逊价格的差异。

**Parameters | 参数:**
- `sku` (string, required): Product SKU to sync | 要同步的SKU
- `target_margin_percent` (float, default: 25): Target profit margin | 目标利润率
- `shipping_cost_usd` (float, default: 2.0): Shipping cost per unit | 每件运输成本
- `response_format` (string, optional): "json" or "markdown"

**Example | 示例:**
```python
# Input
{"sku": "SKU-12345"}

# Output
{
  "sku": "SKU-12345",
  "source_price_cny": 35.00,
  "source_price_usd": 4.86,
  "target_current_price": 14.99,
  "recommended_price_usd": 10.52,
  "action": "DECREASE_PRICE",
  "recommendation": "DECREASE price by $4.47 (29.8%) to maintain target margin.",
  "profit_analysis": {
    "current_profit": 7.10,
    "recommended_profit": 2.63,
    "profit_change": -4.47
  }
}
```

**Actions | 操作建议:**
- `KEEP_CURRENT`: Current price is optimal | 当前价格最优
- `INCREASE_PRICE`: Raise price to maximize profit | 提高价格以最大化利润
- `DECREASE_PRICE`: Lower price to maintain margin | 降低价格以保持利润率
- `CREATE_LISTING`: Create new Amazon listing | 创建新的亚马逊listing

---

### 9. update_amazon_price | 更新亚马逊价格

Update the listing price on Amazon Seller Central.

更新亚马逊卖家中心的商品价格。

**Parameters | 参数:**
- `sku` (string, required): Product SKU | 产品SKU
- `new_price` (float, required): New price in USD | 新价格（美元）
- `currency` (string, default: USD): Currency code | 货币代码

**Example | 示例:**
```python
# Input
{"sku": "SKU-12345", "new_price": 10.52, "currency": "USD"}

# Output
{
  "success": true,
  "sku": "SKU-12345",
  "previous_price": 14.99,
  "new_price": 10.52,
  "updated_at": "2024-01-15T10:30:00Z",
  "message": "Price updated from $14.99 to $10.52"
}
```

---

### 10. get_competitor_prices | 获取竞品价格

Search Amazon for competitor product prices and analysis.

搜索亚马逊竞品价格和分析。

**Parameters | 参数:**
- `sku` (string, required): SKU or search keyword | SKU或搜索关键词
- `limit` (integer, default: 5, max: 20): Maximum competitors | 最大竞品数量
- `response_format` (string, optional): "json" or "markdown"

**Example | 示例:**
```python
# Input
{"sku": "wireless headphones", "limit": 5}

# Output
{
  "search_term": "wireless headphones",
  "total_found": 3,
  "price_range": {
    "lowest": 12.99,
    "average": 20.99,
    "highest": 29.99
  },
  "competitors": [
    {
      "asin": "B08N5WRWNW",
      "title": "Wireless Bluetooth Headphones Pro",
      "price": 19.99,
      "rating": 4.5,
      "review_count": 1250
    }
  ]
}
```

---

### 11. get_product_reviews | 获取产品评论

Get product reviews from Amazon for a specific SKU or ASIN.

获取亚马逊特定SKU或ASIN的产品评论。

**Parameters | 参数:**
- `sku` (string, required): SKU or ASIN | SKU或ASIN
- `days` (integer, default: 30): Days to look back | 回溯天数
- `min_rating` (integer, optional): Minimum rating filter | 最低评分过滤
- `max_rating` (integer, optional): Maximum rating filter | 最高评分过滤
- `limit` (integer, default: 20): Maximum reviews | 最大评论数
- `response_format` (string, optional): "json" or "markdown"

**Example | 示例:**
```python
# Input
{"sku": "SKU-12345", "days": 30}

# Output
{
  "sku": "SKU-12345",
  "total_reviews": 3,
  "average_rating": 2.67,
  "reviews": [
    {
      "review_id": "REV-001",
      "rating": 1,
      "severity": "critical",
      "title": "Completely defective - stopped working after 1 day",
      "text": "This product is completely defective...",
      "date": "2024-01-10",
      "verified": true
    }
  ]
}
```

---

### 12. get_negative_reviews | 获取负面评论

Get 1-2 star reviews that need attention and response.

获取需要关注和回复的1-2星评论。

**Parameters | 参数:**
- `sku` (string, optional): Filter by specific SKU | 按SKU过滤
- `days` (integer, default: 7): Days to look back | 回溯天数
- `severity` (string, default: "all"): "critical", "warning", or "all"
- `response_format` (string, optional): "json" or "markdown"

**Example | 示例:**
```python
# Input
{"sku": "SKU-12345", "days": 7}

# Output
{
  "total_negative": 2,
  "critical_count": 1,
  "warning_count": 1,
  "reviews": [
    {
      "review_id": "REV-001",
      "rating": 1,
      "severity": "critical",
      "title": "Defective product",
      "supplier_issues": [
        {"category": "defective", "severity": "high"}
      ],
      "has_supplier_issues": true
    }
  ]
}
```

---

### 13. get_review_alerts | 获取评论提醒

Get actionable alerts for reviews that need immediate attention.

获取需要立即关注的可操作提醒。

**Parameters | 参数:**
- `days` (integer, default: 7): Days to look back | 回溯天数
- `include_supplier_flags` (boolean, default: true): Enable supplier issue detection | 启用供应商问题检测
- `response_format` (string, optional): "json" or "markdown"

**Alert Types | 提醒类型:**
- `critical_review`: 1-star review needing immediate response | 需要立即回复的1星评论
- `supplier_issue`: Review mentioning quality/defect issues | 提及质量/缺陷问题的评论
- `response_needed`: Any negative review not yet responded to | 任何未回复的负面评论
- `safety_concern`: Review mentioning safety issues | 提及安全问题的评论

**Example | 示例:**
```python
# Input
{"days": 7, "include_supplier_flags": true}

# Output
{
  "total_alerts": 3,
  "priority_breakdown": {
    "critical": 2,
    "high": 1,
    "medium": 0
  },
  "alerts": [
    {
      "alert_type": "supplier_issue",
      "priority": "critical",
      "sku": "SKU-12345",
      "rating": 1,
      "issue_category": "defective",
      "action_required": "Contact supplier about defective issue. Consider quality audit.",
      "response_template": "Dear Customer, we're sorry your SKU-12345 arrived defective..."
    }
  ]
}
```

**Supplier Issue Keywords | 供应商问题关键词:**

| Category | Keywords |
|----------|----------|
| defective | defective, broken, not working, damaged |
| quality | cheap quality, poor quality, flimsy |
| packaging | missing parts, arrived damaged, packaging torn |
| inconsistent | different from description, not as pictured |
| safety | safety issue, overheating, smells burning |

---

## API Reference | API参考

For complete API documentation including authentication, endpoints, error codes, rate limiting, and code examples in Python, JavaScript, and cURL, see the **[API Documentation](API.md)**.

### Quick Reference | 快速参考

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/tools` | GET | List all available MCP tools |
| `/api/tools/<name>` | GET | Get tool info and parameters |
| `/api/tools/<name>` | POST | Call specific MCP tool |
| `/api/auth/login` | POST | User authentication |
| `/api/auth/api-keys` | POST | Create API key |
| `/api/docs/` | GET | **Swagger UI** - Interactive API explorer |

### Authentication | 认证

The API supports two authentication methods:

1. **Session Cookie**: Login via web UI for browser-based access
2. **API Key**: Programmatic access using `X-API-Key` header

```bash
# Using API Key
curl -X POST "http://localhost:5000/api/tools/get_inventory_1688" \
  -H "X-API-Key: YOUR_API_KEY_HERE" \
  -H "Content-Type: application/json" \
  -d '{"sku": "SKU-12345", "response_format": "json"}'
```

### Swagger UI

Interactive API documentation is available at **`/api/docs/`**:

```bash
# Run server and open in browser
python web_app.py
# Then visit http://localhost:5000/api/docs/
```

---

## Price Sync Configuration | 价格同步配置

Configure pricing parameters in `.env`:

在`.env`中配置价格参数:

```bash
# USD to CNY exchange rate
USD_CNY_EXCHANGE_RATE=7.2

# Amazon referral fee percentage (varies by category)
# Electronics: 8%, Home: 15%, Clothing: 17%
AMAZON_REFERRAL_FEE_PERCENT=15.0

# Default shipping cost per unit (USD)
DEFAULT_SHIPPING_COST_USD=2.0

# Default target profit margin
DEFAULT_TARGET_MARGIN_PERCENT=25.0
```

---

## Testing | 测试

### Run Test Suite | 运行测试套件

```bash
# Run all tests with mock data
python test_server.py

# Verbose output
python test_server.py --verbose

# Expected output
# ============================================================
# Cross-Border Seller MCP Server - Test Suite
# ============================================================
# Running: get_inventory_1688... ✓
# Running: get_orders_amazon... ✓
# Running: sync_inventory... ✓
# Running: update_fulfillment_amazon... ✓
# Running: get_low_stock_alerts... ✓
# Running: get_product_cost_1688... ✓
# Running: calculate_amazon_price... ✓
# Running: sync_price... ✓
# Running: update_amazon_price... ✓
# Running: get_competitor_prices... ✓
# Running: get_product_reviews... ✓
# Running: get_negative_reviews... ✓
# Running: get_review_alerts... ✓
# Running: review_supplier_analysis... ✓
# Running: review_severity_logic... ✓
# Running: price_calculation_logic... ✓
# Running: price_action_logic... ✓
# Running: error_handling... ✓
# Running: markdown_format_output... ✓
#
# Total: 19
# Passed: 19 ✓
```

---

## API Setup Guides | API设置指南

### 1688 API Setup | 1688 API设置

1. Register at [Alibaba Open Platform](https://open.1688.com/)
2. Create an application
3. Obtain App Key and App Secret
4. Request access token via OAuth flow
5. Configure the following in `.env`:
   ```
   ALIBABA_APP_KEY=your_app_key
   ALIBABA_APP_SECRET=your_app_secret
   ALIBABA_API_KEY=your_access_token
   ```

### Amazon SP-API Setup | 亚马逊SP-API设置

1. Register as an Amazon Developer at [Amazon Developer Portal](https://developer.amazonservices.com/)
2. Create a Selling Partner API application
3. Configure OAuth permissions for:
   - `getCatalogItem`
   - `getOrders`
   - `updateFulfillmentOrder`
4. Obtain Client ID and Client Secret
5. Complete OAuth authorization flow to get Refresh Token
6. Configure in `.env`:
   ```
   AMAZON_CLIENT_ID=your_client_id
   AMAZON_CLIENT_SECRET=your_client_secret
   AMAZON_REFRESH_TOKEN=your_refresh_token
   ```

---

## Notification Preferences | 通知偏好设置

The system supports multiple notification channels:

| Channel | Description | Setup Required |
|---------|-------------|----------------|
| Email | SMTP-based email notifications | SMTP server configuration |
| Slack | Slack webhook notifications | Slack webhook URL |
| WeChat Work | 企业微信 webhook notifications | WeChat Work webhook URL |
| DingTalk | 钉钉 webhook notifications | DingTalk webhook URL |

### Notification Types | 通知类型

- **Low Stock Alerts** | 低库存警报: Triggered when inventory falls below threshold
- **Review Alerts** | 评论预警: Triggered by negative reviews needing attention
- **Task Completion** | 任务完成: Triggered when background tasks finish
- **Daily Summary** | 每日摘要: Scheduled daily inventory and order summary

### Notification Frequency | 通知频率

- `IMMEDIATE`: Send notifications as they occur
- `HOURLY_DIGEST`: Bundle notifications and send hourly
- `DAILY_DIGEST`: Bundle notifications and send once daily

### Environment Variables for Notifications | 通知环境变量

```bash
# Enable/disable notification channels
NOTIFICATION_EMAIL_ENABLED=false
NOTIFICATION_SLACK_ENABLED=false
NOTIFICATION_WECHAT_ENABLED=false
NOTIFICATION_DINGTALK_ENABLED=false

# Recipient addresses
NOTIFICATION_EMAIL_TO=your@email.com

# Webhook URLs
NOTIFICATION_SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxx
NOTIFICATION_WECHAT_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx
NOTIFICATION_DINGTALK_WEBHOOK_URL=https://oapi.dingtalk.com/robot/send?access_token=xxx

# Notification preferences
NOTIFICATION_LOW_STOCK=true
NOTIFICATION_REVIEWS=true
NOTIFICATION_TASKS=true
NOTIFICATION_FREQUENCY=immediate

# Email (SMTP) configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your@email.com
SMTP_PASSWORD=your_app_password
SMTP_FROM=your@email.com
```

---

## WeChat Work Setup | 企业微信配置

WeChat Work (企业微信) provides efficient team communication with webhook integration for automated notifications.

### Step 1: Create a WeChat Work Application | 创建企业微信应用

1. Log in to [WeChat Work Admin Console](https://work.weixin.qq.com/wework_admin/)
2. Navigate to **Applications** (应用管理)
3. Click **Create Application** (创建应用)
4. Select application type (usually **Custom App** | 自建应用)
5. Enter application name (e.g., "Cross-Border Seller Alerts")
6. Upload application icon (optional)
7. Configure application visibility scope

### Step 2: Get the Webhook URL | 获取Webhook地址

1. Open your created application
2. Navigate to **Application Settings** (应用设置)
3. Find **Webhook** (企业群机器人) section
4. Click **Add** (添加)
5. Give the webhook a name (e.g., "MCP Server Alerts")
6. Copy the generated webhook URL

**Webhook URL Format:**
```
https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
```

### Step 3: Required Permissions | 所需权限

**Admin Permissions:**
- `Super Admin` or `Application Admin` privileges to create applications
- Ability to access the application settings

**Application Settings:**
- Enable "Allow external messages" if using external contacts
- Configure message receiving permissions as needed

**Webhook Configuration:**
- Webhook can send messages to group chats
- No additional API permissions required for basic webhook usage

### Step 4: Configure Environment Variables | 配置环境变量

Add to your `.env` file:

```bash
# Enable WeChat Work notifications
NOTIFICATION_WECHAT_ENABLED=true

# Your webhook URL from Step 2
NOTIFICATION_WECHAT_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
```

### Step 5: Test the Integration | 测试集成

```bash
# Run the test suite which includes WeChat notification testing
python test_server.py

# Or send a test notification directly
python -c "
from notification import get_notification_service
service = get_notification_service()
result = service.send_test_notification(lang='en')
print('WeChat Result:', result.get('wechat'))
"
```

### Message Format | 消息格式

WeChat Work webhooks support Markdown-formatted messages:

```json
{
  "msgtype": "markdown",
  "markdown": {
    "content": "### 🔴 Low Stock Alert\n\n**Product:** Wireless Headphones\n**SKU:** SKU-12345\n**Current Stock:** 3\n**Threshold:** 10"
  }
}
```

---

## DingTalk Setup | 钉钉配置

DingTalk (钉钉) is Alibaba's enterprise communication platform with robust webhook notification support.

### Step 1: Create a DingTalk Group | 创建钉钉群

1. Open DingTalk application
2. Create a new group or select existing group for notifications
3. Go to **Group Settings** (群设置)
4. Add the "Custom Robot" (自定义机器人) integration

### Step 2: Configure Custom Robot | 配置自定义机器人

1. In Group Settings, find **Group Robots** (群机器人)
2. Click **Add Robot** (添加机器人)
3. Select **Custom** (自定义)
4. Enter robot name (e.g., "MCP Server Alerts")
5. For security settings, choose:
   - **Custom Keywords** (加签): Add keyword like "Alert" or "Notification"
   - **IP Addresses** (ip白名单): Add your server IP (optional)
   - **Signature** (加签): Copy the secret for later use

### Step 3: Get the Webhook URL | 获取Webhook地址

After adding the robot, you will receive:
- **Webhook URL**: Copy this URL
- **Secret** (if using signature): Save this for configuration

**Webhook URL Format:**
```
https://oapi.dingtalk.com/robot/send?access_token=XXXXXXXXXXXXXXXXX
```

### Step 4: Required Permissions | 所需权限

**Group Permissions:**
- Must be group owner or admin to add robots
- Requires "Add Bots" permission enabled for the group

**Robot Permissions:**
- Sending messages only (no reading/group management)
- Works with standard group membership

### Step 5: Configure Environment Variables | 配置环境变量

Add to your `.env` file:

```bash
# Enable DingTalk notifications
NOTIFICATION_DINGTALK_ENABLED=true

# Your webhook URL from Step 3
NOTIFICATION_DINGTALK_WEBHOOK_URL=https://oapi.dingtalk.com/robot/send?access_token=XXXXXXXXXXXXXXXXX
```

**Note:** If you enabled signature verification, you'll need to update the notification code to include the secret. The current implementation uses basic webhook mode.

### Step 6: Test the Integration | 测试集成

```bash
# Run the test suite
python test_server.py

# Test DingTalk specifically
python -c "
from notification import get_notification_service
service = get_notification_service()
result = service.send_test_notification(lang='cn')
print('DingTalk Result:', result)
"
```

### Message Format | 消息格式

DingTalk supports Markdown messages:

```json
{
  "msgtype": "markdown",
  "markdown": {
    "title": "🔴 Low Stock Alert",
    "text": "## 🔴 Low Stock Alert\n\n**Product:** Wireless Headphones\n**SKU:** SKU-12345\n**Current Stock:** 3\n**Threshold:** 10"
  }
}
```

---

## China-Specific Configuration | 中国特定配置

### Environment Variables for China Services | 中国服务环境变量

```bash
# WeChat Work Configuration | 企业微信配置
NOTIFICATION_WECHAT_ENABLED=true
NOTIFICATION_WECHAT_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx

# DingTalk Configuration | 钉钉配置
NOTIFICATION_DINGTALK_ENABLED=true
NOTIFICATION_DINGTALK_WEBHOOK_URL=https://oapi.dingtalk.com/robot/send?access_token=xxx

# Note: Both services use Chinese data centers by default
# No special CDN configuration needed for WeChat/DingTalk
```

### CDN Alternatives for China | 中国CDN替代方案

If external CDN resources fail to load in China:

| Resource | Default CDN | China Alternative |
|----------|-------------|-------------------|
| Python packages | PyPI | [Tsinghua Mirror](https://mirror.tuna.tsinghua.edu.cn/pypi/) |
| npm packages | npmjs.com | [Taobao Mirror](https://npmmirror.com/) |
| GitHub resources | github.com | [Fastgit](https://fastgit.org/) or [ghproxy](https://ghproxy.com/) |

**Using China Mirrors:**

```bash
# pip with Tsinghua mirror
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# npm with Taobao mirror
npm config set registry https://registry.npmmirror.com

# Git clone via mirror
git clone https://ghproxy.com/https://github.com/user/repo.git
```

### Regional Settings | 区域设置

For optimal performance in China:

```bash
# API endpoints (default to global)
# For China-specific endpoints, check with your service provider

# Timezone
TZ=Asia/Shanghai

# Currency
DEFAULT_CURRENCY=CNY
USD_CNY_EXCHANGE_RATE=7.2
```

---

## Troubleshooting | 故障排除

### Common Issues | 常见问题

#### 1. Authentication Errors | 认证错误

```
Error: 1688 authentication failed. Please check your API credentials.
```

**Solution | 解决方案:**
- Verify your API keys in `.env` are correct
- 检查.env中的API密钥是否正确
- Ensure your 1688/Amazon developer account is active
- 确保您的1688/亚马逊开发者账户处于激活状态

#### 2. Rate Limiting | 速率限制

```
Error: 1688 rate limit exceeded. Please wait before making more requests.
```

**Solution | 解决方案:**
- Add delays between requests
- 在请求之间添加延迟
- Contact API provider for higher limits
- 联系API提供商获取更高限额

#### 3. Module Not Found | 模块未找到

```
ModuleNotFoundError: No module named 'mcp'
```

**Solution | 解决方案:**
```bash
pip install -r requirements.txt
```

#### 4. Invalid SKU | 无效的SKU

```
Error: 1688 resource not found. Please verify the SKU.
```

**Solution | 解决方案:**
- Check if the SKU exists on the platform
- 确认SKU是否存在于平台上
- Verify spelling and format
- 验证拼写和格式

---

### China-Specific Troubleshooting | 中国特定故障排除

#### 5. WeChat Work Webhook Not Working | 企业微信Webhook不工作

**Symptoms | 症状:**
- Messages not appearing in WeChat Work group
- HTTP 400 or 401 errors

**Solutions | 解决方案:**
1. Verify webhook URL is correct and complete
   ```
   # Should be:
   https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=XXX
   # Not:
   https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=XXX&debug=1
   ```
2. Check if the application has permission to send messages
3. Ensure the group robot is properly added
4. Verify the webhook key hasn't expired or been regenerated

#### 6. DingTalk Webhook Not Working | 钉钉Webhook不工作

**Symptoms | 症状:**
- Messages not appearing in DingTalk group
- Error code 300001 or 300002

**Solutions | 解决方案:**
1. Check if the access token is valid
   ```
   # Verify URL format:
   https://oapi.dingtalk.com/robot/send?access_token=XXX
   ```
2. If using signature verification, ensure the secret matches
3. Verify the custom keyword is present in the message content
4. Check if the group allows external bots

#### 7. CDN Resources Not Loading | CDN资源无法加载

**Symptoms | 症状:**
- Python packages fail to install
- Git clone hangs or times out
- npm packages fail to download

**Solutions | 解决方案:**
1. Use China-specific mirrors:
   ```bash
   # pip
   pip install package -i https://pypi.tuna.tsinghua.edu.cn/simple
   
   # git
   git config --global url."https://ghproxy.com/".insteadOf https://github.com
   ```

2. For GitHub access, use mirrors:
   ```bash
   # Clone via ghproxy
   git clone https://ghproxy.com/https://github.com/user/repo.git
   
   # Or use fastgit
   git clone https://download.fastgit.org/user/repo.git
   ```

3. Check network connectivity:
   ```bash
   # Test connectivity
   ping github.com
   curl -I https://pypi.org
   ```

#### 8. VPN Requirements for Setup | VPN设置要求（可选）

**During Initial Setup | 初始设置期间:**
- VPN may be required to access:
  - GitHub for repository cloning
  - PyPI for some packages
  - Amazon/1688 developer portals

**For Runtime Operations | 运行时操作:**
- VPN not required for:
  - WeChat Work API calls (hosted in China)
  - DingTalk API calls (hosted in China)
  - 1688 API calls (hosted in China)
- VPN may be required for:
  - Amazon SP-API calls (if in China)
  - Some npm package installations

---

## Project Structure | 项目结构

```
crossborder_seller_mcp/
├── server.py           # Main MCP server | 主MCP服务器
├── notification.py    # Notification service | 通知服务
├── test_server.py     # Test suite | 测试套件
├── requirements.txt   # Python dependencies | Python依赖
├── .env                # Environment variables | 环境变量
├── .env.example        # Environment template | 环境变量模板
├── .env.cn.example     # Chinese configuration template | 中文配置模板
├── README.md           # Documentation (English) | 文档（英文）
└── README_CN.md        # Documentation (Chinese) | 文档（中文）
```

---

## License | 许可证

MIT License

---

## Support | 支持

For issues and feature requests, please open an issue on the repository.

如有问题或功能请求，请在仓库中提交issue。

---

**Made for Cross-Border Sellers | 为跨境卖家打造**
