# 跨境卖家 MCP 服务器 - 中文快速入门

专为中国跨境卖家打造的 MCP 工具，一键连接 1688 和亚马逊！

---

## 🏃‍♂️ 3分钟快速上手

### 第1步：安装依赖

```bash
cd /workspace/crossborder_seller_mcp
pip install -r requirements.txt
```

### 第2步：配置API密钥

复制 `.env.example` 为 `.env`，然后填入您的密钥：

```bash
cp .env.example .env
```

编辑 `.env` 文件：
```env
# 1688配置
ALIBABA_APP_KEY=您的1688应用Key
ALIBABA_APP_SECRET=您的1688应用Secret
ALIBABA_API_KEY=您的1688访问Token

# 亚马逊配置
AMAZON_CLIENT_ID=您的SP-API客户端ID
AMAZON_CLIENT_SECRET=您的SP-API客户端密钥
AMAZON_REFRESH_TOKEN=您的刷新Token
AMAZON_MARKETPLACE_ID=ATVPDKIKX0DER  # 美国站
```

### 第3步：运行测试（可选）

```bash
python test_server.py
```

### 第4步：启动服务器

```bash
python server.py
```

---

## 🛠️ 常用工具说明

### 1. 查询 1688 库存

**用途：查询供应商的库存情况**

```bash
工具: get_inventory_1688
参数: sku="SKU-12345", response_format="markdown"
```

### 2. 获取亚马逊订单

**用途：查看最近的订单情况**

```bash
工具: get_orders_amazon
参数: days=7, limit=20, response_format="markdown"
```

### 3. 同步价格（非常重要！）

**用途：计算亚马逊的最佳售价**

```bash
工具: calculate_amazon_price
参数: sku="SKU-12345", cost_cny=35, target_margin_percent=25
```

计算结果：
```
1688成本: ¥35.00
运费: $2.00
佣金: 15%
推荐售价: $10.52
利润: $2.63 (25%)
```

### 4. 监控评论（非常重要！）

**用途：发现产品问题和供应商质量问题**

```bash
工具: get_review_alerts
参数: days=7, include_supplier_flags=true
```

收到负面评论时会自动提醒，还会给出回复模板！

---

## 💡 使用场景举例

### 场景1：定价策略

您在1688看到一款无线耳机，¥35/件，想在亚马逊销售：

```bash
使用 calculate_amazon_price 工具
输入 cost_cny=35, target_margin_percent=25
推荐售价：$10.52
```

### 场景2：监控库存

```bash
每天运行 get_low_stock_alerts 工具
自动提醒您哪些产品库存不足
```

### 场景3：管理评论

```bash
每周运行 get_negative_reviews 工具
及时发现产品问题，回复客户
```

---

## 📊 支持的亚马逊站点

| 站点 | Marketplace ID |
|------|----------------|
| 🇺🇸 美国 | ATVPDKIKX0DER |
| 🇬🇧 英国 | A1F83G8C2ARO7P |
| 🇩🇪 德国 | A1PA6795UKMFR9 |
| 🇫🇷 法国 | A13V1IB3VIY7EH |
| 🇮🇹 意大利 | APJMTJMRP4FPT |
| 🇪🇸 西班牙 | A1RKKUPIHCS9HS |
| 🇯🇵 日本 | A1VC38T7YXB528 |
| 🇨🇦 加拿大 | A2EUQ1WTGCTBG2 |

---

## 📞 获取帮助

### 如何获取亚马逊 SP-API 密钥？

1. 访问 [Amazon Seller Central](https://sellercentral.amazon.com/)
2. 进入 Partner Network → Developer Central
3. 创建应用，获取 Client ID 和 Client Secret
4. 完成 OAuth 授权，获取 Refresh Token

### 如何获取 1688 API 密钥？

1. 访问 [1688开放平台](https://open.1688.com/)
2. 注册开发者账号
3. 创建应用，获取 App Key 和 App Secret
4. 获取访问 Token

---

## ⚡ 快速参考卡

### 常用参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `sku` | 产品SKU | 必填 |
| `days` | 天数 | 30 |
| `limit` | 返回数量 | 20 |
| `target_margin_percent` | 目标利润率 | 25 |
| `response_format` | 输出格式 | json |

### 输出格式

- `json` - 结构化数据，适合程序处理
- `markdown` - 人类可读格式，方便查看

---

## 🎉 开始使用吧！

您已准备好使用 MCP 服务器了！如果您是第一次使用，建议先：

1. 运行测试确认环境正常：`python test_server.py`
2. 查看 README.md 了解所有工具
3. 连接您的 API 密钥后开始使用

祝您生意兴隆！💼🚀
