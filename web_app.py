#!/usr/bin/env python3
"""
Cross-Border Seller Web UI - No Installation Required!
跨境卖家Web界面 - 无需安装！

Just run: python web_app.py
Then open: http://localhost:5000 in your browser
"""

from flask import Flask, render_template, request, jsonify
import json
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import our existing functions
from license_manager import get_license_manager, LicenseTier

# Initialize Flask app
app = Flask(__name__)

# Bilingual text support
TEXT = {
    'cn': {
        'title': '跨境卖家AI助手',
        'subtitle': '1688 + Amazon 一站式管理工具',
        'nav_home': '首页',
        'nav_profit': '利润计算',
        'nav_inventory': '库存管理',
        'nav_pricing': '价格同步',
        'nav_reviews': '评论监控',
        'welcome': '欢迎使用跨境卖家AI助手',
        'welcome_desc': '无需安装，打开浏览器即可使用！',
        'quick_actions': '快捷操作',
        'profit_calc': '真实利润计算器',
        'low_stock': '库存预警',
        'comp_price': '竞品价格分析',
        'review_alert': '评论警报',
        'enter_sku': '输入SKU',
        'enter_price': '输入售价 (USD)',
        'calculate': '计算',
        'profit_result': '利润计算结果',
        'net_profit': '净利润',
        'profit_margin': '利润率',
        'total_cost': '总成本',
        'status': '状态',
        'profitable': '✅ 盈利',
        'not_profitable': '❌ 亏损',
        'cost_breakdown': '成本明细',
        'language': '语言',
        'chinese': '中文',
        'english': 'English'
    },
    'en': {
        'title': 'Cross-Border Seller AI Assistant',
        'subtitle': 'All-in-one tool for 1688 + Amazon',
        'nav_home': 'Home',
        'nav_profit': 'Profit Calculator',
        'nav_inventory': 'Inventory',
        'nav_pricing': 'Pricing',
        'nav_reviews': 'Reviews',
        'welcome': 'Welcome to Cross-Border Seller AI Assistant',
        'welcome_desc': 'No installation needed - just open your browser!',
        'quick_actions': 'Quick Actions',
        'profit_calc': 'True Profit Calculator',
        'low_stock': 'Low Stock Alerts',
        'comp_price': 'Competitor Price Analysis',
        'review_alert': 'Review Alerts',
        'enter_sku': 'Enter SKU',
        'enter_price': 'Enter Selling Price (USD)',
        'calculate': 'Calculate',
        'profit_result': 'Profit Calculation Result',
        'net_profit': 'Net Profit',
        'profit_margin': 'Profit Margin',
        'total_cost': 'Total Cost',
        'status': 'Status',
        'profitable': '✅ Profitable',
        'not_profitable': '❌ Not Profitable',
        'cost_breakdown': 'Cost Breakdown',
        'language': 'Language',
        'chinese': '中文',
        'english': 'English'
    }
}

def get_text(lang, key):
    """Get bilingual text"""
    return TEXT.get(lang, 'cn').get(key, key)

@app.route('/')
def index():
    """Home page"""
    lang = request.args.get('lang', 'cn')
    return render_template('index.html', lang=lang, get_text=lambda key: get_text(lang, key))

@app.route('/profit', methods=['GET', 'POST'])
def profit():
    """Profit Calculator page"""
    lang = request.args.get('lang', 'cn')
    
    if request.method == 'POST':
        # Get form data
        sku = request.form.get('sku', 'SKU-12345')
        selling_price = float(request.form.get('selling_price', 29.99))
        cost_cny = float(request.form.get('cost_cny', 35.0))
        
        # Calculate true profit (using our existing logic)
        result = calculate_true_profit_simple(
            selling_price_usd=selling_price,
            cost_cny=cost_cny
        )
        
        return render_template('profit.html', 
                             lang=lang, 
                             get_text=lambda key: get_text(lang, key),
                             result=result,
                             sku=sku,
                             selling_price=selling_price)
    
    return render_template('profit.html', 
                         lang=lang, 
                         get_text=lambda key: get_text(lang, key),
                         result=None)

def calculate_true_profit_simple(selling_price_usd: float, cost_cny: float):
    """Simple version of true profit calculation for web UI"""
    exchange_rate = 7.2
    cost_usd = cost_cny / exchange_rate
    
    # Calculate cost components
    shipping = 2.0
    referral_fee = selling_price_usd * 0.15
    fba_fee = 3.5
    storage = 0.3
    advertising = selling_price_usd * 0.15
    payment_fee = selling_price_usd * 0.029
    returns = (cost_usd + shipping) * 0.05
    customs = cost_usd * 0.03
    overhead = selling_price_usd * 0.05
    
    total_cost = (cost_usd + shipping + referral_fee + fba_fee + storage + 
                 advertising + payment_fee + returns + customs + overhead)
    
    net_profit = selling_price_usd - total_cost
    profit_margin = (net_profit / selling_price_usd * 100) if selling_price_usd > 0 else 0
    is_profitable = net_profit > 0
    
    return {
        'selling_price_usd': selling_price_usd,
        'cost_cny': cost_cny,
        'cost_usd': round(cost_usd, 2),
        'net_profit_usd': round(net_profit, 2),
        'profit_margin_percent': round(profit_margin, 1),
        'total_cost_usd': round(total_cost, 2),
        'is_profitable': is_profitable,
        'cost_breakdown': {
            'product_cost_usd': round(cost_usd, 2),
            'shipping_to_amazon_usd': round(shipping, 2),
            'amazon_referral_fee_usd': round(referral_fee, 2),
            'fba_fulfillment_fee_usd': round(fba_fee, 2),
            'monthly_storage_fee_usd': round(storage, 2),
            'advertising_cost_usd': round(advertising, 2),
            'payment_processing_fee_usd': round(payment_fee, 2),
            'return_cost_usd': round(returns, 2),
            'customs_duty_usd': round(customs, 2),
            'overhead_usd': round(overhead, 2)
        }
    }

@app.route('/api/profit', methods=['POST'])
def api_profit():
    """API endpoint for profit calculation"""
    data = request.json
    result = calculate_true_profit_simple(
        selling_price_usd=data.get('selling_price', 29.99),
        cost_cny=data.get('cost_cny', 35.0)
    )
    return jsonify(result)

if __name__ == '__main__':
    print("="*60)
    print("🚀 Cross-Border Seller Web UI")
    print("跨境卖家Web界面 - 启动中...")
    print("="*60)
    print("")
    print("📱 Open your browser and go to:")
    print("   http://localhost:5000")
    print("")
    print("🌐 Language support: 中文 (Chinese) + English")
    print("")
    print("="*60)
    
    app.run(host='0.0.0.0', port=5000, debug=True)
