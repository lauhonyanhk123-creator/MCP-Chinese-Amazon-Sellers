#!/usr/bin/env python3
"""
Cross-Border Seller Web UI - No Installation Required!
跨境卖家Web界面 - 无需安装！

Just run: python web_app.py
Then open: http://localhost:5000 in your browser

REST API Endpoints:
    - GET  /api/tools          - List all available MCP tools
    - GET  /api/tools/<name>   - Get tool info and parameters
    - POST /api/tools/<name>   - Call specific MCP tool with parameters
"""

import asyncio
import csv
import hashlib
import io
import json
import math
import os
import random
import secrets
import threading
import traceback
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Any

from dotenv import load_dotenv
from flasgger import Swagger
from flask import (
    Flask,
    Response,
    flash,
    g,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_compress import Compress

load_dotenv()

from audit import AuditAction, AuditLogger, ResourceType
from auth import (
    PERMISSIONS,
    audit_logger,
    auth_service,
    create_api_key_for_user,
    get_user_permissions,
    list_user_api_keys,
    login_required,
    permission_required,
    revoke_user_api_key,
    role_required,
)
from notification import NotificationPreference, NotificationTemplates, get_notification_service
from rate_limiter import get_rate_limiter, rate_limit
from cache import CacheManager, cached

cache_manager = CacheManager()


class AsyncRunner:
    """Helper class to run async coroutines from sync context"""
    _loop = None
    _thread = None

    @classmethod
    def run_async(cls, coro):
        """Run an async coroutine and return its result"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


_process_start_time = datetime.now()
_request_counter = 0
_request_counter_lock = threading.Lock()
_endpoint_timings = {}
_endpoint_timings_lock = threading.Lock()

_redis_pool = None

def get_redis_pool():
    """Get or create Redis connection pool for connection reuse."""
    global _redis_pool
    if _redis_pool is None:
        import redis
        redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
        _redis_pool = redis.ConnectionPool.from_url(
            redis_url,
            max_connections=50,
            decode_responses=True
        )
    return _redis_pool


def get_uptime():
    """Get uptime statistics"""
    global _request_counter
    current_time = datetime.now()
    uptime_seconds = (current_time - _process_start_time).total_seconds()
    
    return {
        'start_time': _process_start_time.isoformat(),
        'uptime_seconds': uptime_seconds,
        'total_requests': _request_counter
    }


def track_request_time(f):
    """Decorator to track endpoint response times"""
    from functools import wraps
    import time
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        global _endpoint_timings, _request_counter
        
        with _request_counter_lock:
            _request_counter += 1
        
        start_time = time.time()
        result = f(*args, **kwargs)
        elapsed = time.time() - start_time
        
        endpoint_name = f.__name__
        with _endpoint_timings_lock:
            if endpoint_name not in _endpoint_timings:
                _endpoint_timings[endpoint_name] = []
            _endpoint_timings[endpoint_name].append({
                'timestamp': datetime.now().isoformat(),
                'duration_ms': round(elapsed * 1000, 2)
            })
            if len(_endpoint_timings[endpoint_name]) > 100:
                _endpoint_timings[endpoint_name] = _endpoint_timings[endpoint_name][-100:]
        
        return result
    
    return decorated_function



def generate_date_range(days: int) -> list[str]:
    """Generate a list of date strings for the past N days"""
    return [(datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(days)]

def format_currency_filter(value):
    """Jinja filter for formatting currency"""
    return f"${value:,.2f}"

def get_client_info():
    """Get client IP and user agent from request"""
    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ',' in ip_address:
        ip_address = ip_address.split(',')[0].strip()
    user_agent = request.headers.get('User-Agent', '')
    return ip_address, user_agent

def log_audit(user_id, action, resource_type, resource_id=None, details=None):
    """Helper to log audit events"""
    ip_address, user_agent = get_client_info()
    AuditLogger.log_action(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent
    )

def generate_etag(data: Any) -> str:
    """Generate ETag from data using MD5 hash"""
    data_str = json.dumps(data, sort_keys=True, default=str)
    hash_value = hashlib.md5(data_str.encode()).hexdigest()
    return f'"{hash_value}"'

def add_etag_and_cache(response: Response, max_age: int = 60) -> Response:
    """Add ETag and Cache-Control headers to response"""
    response.headers['Cache-Control'] = f'public, max-age={max_age}'
    return response

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.jinja_env.filters['format_currency'] = format_currency_filter

@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

SWAGGER_CONFIG = {
    'title': 'Cross-Border Seller API',
    'version': '1.0.0',
    'description': 'REST API for Cross-Border Seller Management - 1688 + Amazon integration',
    'termsOfService': '',
    'contact': {
        'name': 'API Support',
        'email': 'support@crossborder-seller.com'
    },
    'license': {
        'name': 'MIT',
        'url': 'https://opensource.org/licenses/MIT'
    },
    'specs_route': '/api/docs/',
    'specs_json_route': '/api/docs.json',
    'swagger_ui': True,
    'swagger_ui_version': '4.18.2',
    'static_url_path': '/flasgger_static',
    'basePath': '',
    'schemes': ['http', 'https'],
    'headers': [],
    'specs': [
        {
            'endpoint': 'apispec',
            'route': '/api/docs.json',
            'rule_filter': lambda rule: True,
            'model_filter': lambda tag: True
        }
    ]
}

swagger = Swagger(app, config=SWAGGER_CONFIG)

Compress(app)

@app.context_processor
def inject_user_session():
    """Inject user session info into all templates"""
    session_id = request.cookies.get('session_id')
    user_email = None
    user_role = None

    if session_id:
        session = auth_service.get_session(session_id)
        if session:
            payload = auth_service.verify_token(session['token'])
            if payload:
                user = auth_service.get_user(payload['user_id'])
                if user:
                    user_email = user['email']
                    user_role = user['role']

    return {
        'session_id': session_id,
        'user_email': user_email,
        'user_role': user_role
    }

@app.route('/health')
def health_check():
    """Health check endpoint for Docker/container orchestration"""
    import sqlite3
    from pathlib import Path

    health_status = {
        'status': 'healthy',
        'service': 'crossborder-seller',
        'version': '1.0.0',
        'timestamp': datetime.now().isoformat(),
        'checks': {}
    }

    try:
        db_path = Path(__file__).parent / 'seller_data.db'
        if db_path.exists():
            conn = sqlite3.connect(db_path)
            conn.execute('SELECT 1')
            conn.close()
            health_status['checks']['database'] = 'ok'
        else:
            health_status['checks']['database'] = 'not_initialized'
    except Exception as e:
        health_status['checks']['database'] = f'error: {e!s}'
        health_status['status'] = 'degraded'

    try:
        import redis
        redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
        r = redis.from_url(redis_url)
        r.ping()
        health_status['checks']['redis'] = 'ok'
    except Exception as e:
        health_status['checks']['redis'] = f'unavailable: {e!s}'
        health_status['status'] = 'degraded'

    status_code = 200 if health_status['status'] == 'healthy' else 503
    return jsonify(health_status), status_code


@app.route('/api/performance')
@app.route('/api/metrics')
@login_required
def performance_metrics():
    """Return performance metrics for monitoring"""
    lang = request.args.get('lang', 'en')
    
    with _endpoint_timings_lock:
        timings_summary = {}
        for endpoint, records in _endpoint_timings.items():
            if records:
                durations = [r['duration_ms'] for r in records]
                timings_summary[endpoint] = {
                    'count': len(durations),
                    'avg_ms': round(sum(durations) / len(durations), 2),
                    'min_ms': round(min(durations), 2),
                    'max_ms': round(max(durations), 2)
                }
    
    metrics = {
        'cache': cache_manager.get_stats(),
        'database': {
            'status': 'ok'
        },
        'uptime': get_uptime(),
        'endpoint_timings': timings_summary
    }
    
    return jsonify(metrics)


TEXT = {
    'cn': {
        'title': '跨境卖家AI助手',
        'subtitle': '1688 + Amazon 一站式管理工具',
        'nav_home': '首页',
        'nav_profit': '利润计算',
        'nav_inventory': '库存管理',
        'nav_pricing': '价格同步',
        'nav_reviews': '评论监控',
        'nav_competitor': '竞品价格',
        'nav_analytics': '数据分析',
        'competitor_page_title': '竞品价格分析',
        'competitor_search_placeholder': '搜索ASIN或关键词',
        'competitor_max_results': '最大结果数',
        'competitor_col_asin': 'ASIN',
        'competitor_col_product': '产品名称',
        'competitor_col_price': '价格',
        'competitor_col_rating': '评分',
        'competitor_col_seller': '卖家',
        'competitor_no_results': '未找到竞品',
        'competitor_found_count': '找到 X 个竞品',
        'competitor_price_range': '价格区间',
        'competitor_trends': '竞品趋势',
        'price_history': '价格历史',
        'market_position': '市场定位',
        'price_alert': '价格警报',
        'significant_change': '重大变化',
        'view_history': '查看历史',
        'price_rank': '价格排名',
        'percentile': '百分位',
        'relative_position': '相对位置',
        'current_position': '当前位置',
        'position_premium': '高端定位',
        'position_upper_mid': '中高端',
        'position_lower_mid': '中低端',
        'position_budget': '经济型',
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
        'english': 'English',
        'low_stock_page_title': '库存预警',
        'low_stock_threshold_label': '库存阈值',
        'low_stock_platform_filter_label': '平台筛选',
        'low_stock_platform_all': '全部',
        'low_stock_platform_1688': '1688',
        'low_stock_platform_amazon': 'Amazon',
        'low_stock_apply_button': '应用筛选',
        'low_stock_col_product_name': '产品名称',
        'low_stock_col_sku': 'SKU',
        'low_stock_col_platform': '平台',
        'low_stock_col_current_stock': '当前库存',
        'low_stock_col_shortage': '缺口',
        'low_stock_col_severity': '严重程度',
        'low_stock_no_alerts': '暂无库存预警',
        'low_stock_summary': '共 X 个库存预警',
        'reviews_page_title': '评论监控',
        'reviews_filter_rating': '按评分筛选',
        'reviews_filter_days': '最近天数',
        'reviews_all_ratings': '全部评分',
        'reviews_reviewer': '评论者',
        'reviews_product': '产品',
        'reviews_rating': '评分',
        'reviews_date': '日期',
        'reviews_suggested_response': '建议回复',
        'reviews_no_alerts': '暂无评论警报',
        'reviews_alert_count': 'X 条评论需要关注',
        'reviews_supplier_issue': '供应商问题',
        'reviews_critical_review': '差评',
        'reviews_response_needed': '需要回复',
        'reviews_action_required': '需要处理',
        'reviews_review_text': '评论内容',
        'reviews_issue_type': '问题类型',
        'reviews_priority': '优先级',
        'reviews_priority_critical': '紧急',
        'reviews_priority_high': '高',
        'reviews_priority_medium': '中',
        'reviews_copy_response': '复制回复',
        'reviews_copied': '已复制!',
        'api_error_title': 'API 错误',
        'api_error_invalid_json': '无效的 JSON 数据',
        'api_error_missing_params': '缺少必需参数',
        'api_error_tool_not_found': '工具不存在',
        'api_error_internal': '服务器内部错误',
        'api_success': '操作成功',
        'api_tools_list': '可用工具列表',
        'api_tool_info': '工具信息',
        'api_tool_called': '工具调用结果',
        'api_params': '参数',
        'api_result': '结果',
        'api_description': '描述',
        'api_required_params': '必需参数',
        'api_optional_params': '可选参数',
        'dashboard_page_title': '仪表板',
        'dashboard_low_stock': '低库存产品',
        'dashboard_pending_orders': '待处理订单',
        'dashboard_negative_reviews': '负面评论',
        'dashboard_todays_revenue': '今日收入',
        'dashboard_quick_actions': '快速操作',
        'dashboard_refresh': '刷新',
        'dashboard_last_updated': '最后更新',
        'dashboard_critical': '紧急',
        'dashboard_warning': '警告',
        'dashboard_go_to_inventory': '查看库存',
        'dashboard_go_to_orders': '查看订单',
        'dashboard_go_to_reviews': '查看评论',
        'task_queue': '任务队列',
        'task_processing': '处理中',
        'task_completed': '已完成',
        'task_failed': '失败',
        'task_pending': '待处理',
        'dashboard_sync_status': '同步状态',
        'dashboard_active_tasks': '进行中任务',
        'dashboard_recent_tasks': '最近任务',
        'task_view_all': '查看全部',
        'task_no_active': '无进行中任务',
        'trend_vs_last_week': '较上周',
        'trend_vs_yesterday': '较昨日',
        'trend_stable': '趋势稳定',
        'trend_up': '上升',
        'trend_down': '下降',
        'status_good': '良好',
        'status_attention': '需关注',
        'status_critical': '紧急',
        'historical_data': '历史数据',
        'trend_analysis': '趋势分析',
        'forecast': '预测',
        'stockout_prediction': '库存预测',
        'days_until_stockout': '预计库存天数',
        'recommended_reorder': '建议补货量',
        'view_history': '查看历史',
        'historical_comparison': '历史对比',
        'growth_rate': '增长率',
        'inventory_forecast': '库存预测',
        'sales_velocity': '销售速度',
        'reorder_lead_time': '补货周期',
        'safety_stock': '安全库存',
        'risk_level': '风险等级',
        'risk_low': '低风险',
        'risk_medium': '中风险',
        'risk_high': '高风险',
        'risk_critical': '严重风险',
        'confidence': '置信度',
        'health_score': '健康指数',
        'inventory_health': '库存健康',
        'health_good': '良好',
        'health_moderate': '一般',
        'health_poor': '需关注',
        'period_days': '时间段',
        'compare_periods': '对比时段',
        'current_period': '本期',
        'previous_period': '上期',
        'change_percent': '变化率',
        'no_historical_data': '暂无历史数据',
        'generate_forecast': '生成预测',
        'trend_stable': '趋势稳定',
        'trend_growing': '增长趋势',
        'trend_declining': '下降趋势',
        'metric_improving': '改善中',
        'metric_worsening': '恶化中',
        'stockout_prediction': '库存预测',
        'days_until_stockout': '预计缺货天数',
        'recommended_reorder': '建议补货量',
        'risk_level': '风险等级',
        'risk_high': '高风险',
        'risk_medium': '中风险',
        'risk_low': '低风险',
        'risk_critical': '严重风险',
        'inventory_health': '库存健康度',
        'lead_time': '补货周期',
        'days_of_supply': '库存天数',
        'avg_days_supply': '平均库存天数',
        'products_at_risk': '风险产品数',
        'reorder_urgency': '补货紧迫度',
        'urgency_critical': '紧急',
        'urgency_high': '高',
        'urgency_medium': '中',
        'urgency_low': '低',
        'predicted_stockout': '预计缺货日期',
        'safety_stock': '安全库存',
        'reorder_point': '补货点',
        'risk_threshold': '风险阈值',
        'no_predictions': '暂无库存预测',
        'rate_limit_exceeded': '请求过于频繁',
        'try_again_in': '请在以下时间后重试',
        'upgrade_plan': '升级方案',
        'current_limit': '当前限制',
        'remaining': '剩余次数',
        'login': '登录',
        'logout': '退出',
        'register': '注册',
        'email': '邮箱',
        'password': '密码',
        'confirm_password': '确认密码',
        'forgot_password': '忘记密码',
        'welcome': '欢迎',
        'remember_me': '记住我',
        'create_account': '创建账户',
        'already_have_account': '已有账户',
        'forgot_password_desc': '输入您的邮箱地址，我们将发送密码重置链接',
        'reset_password': '重置密码',
        'new_password': '新密码',
        'confirm_new_password': '确认新密码',
        'password_reset_sent': '密码重置链接已发送到您的邮箱',
        'password_reset_success': '密码重置成功',
        'invalid_reset_token': '无效或过期的重置链接',
        'password_mismatch': '两次输入的密码不一致',
        'password_too_short': '密码至少需要8个字符',
        'email_required': '请输入邮箱',
        'password_required': '请输入密码',
        'invalid_email_format': '邮箱格式不正确',
        'registration_success': '注册成功，请登录',
        'registration_failed': '注册失败，请重试',
        'account_disabled': '账户已被禁用',
        'login_success': '登录成功',
        'logout_success': '已退出登录',
        'logout_confirm': '确定要退出登录吗？',
        'session_expired': '会话已过期，请重新登录',
        'unauthorized': '未授权访问',
        'role_admin': '管理员',
        'role_manager': '经理',
        'role_viewer': '访客',
        'select_role': '选择角色',
        'terms_of_service': '服务条款',
        'agree_terms': '我已阅读并同意服务条款',
        'user_profile': '用户资料',
        'change_password': '修改密码',
        'current_password': '当前密码',
        'profile_settings': '个人设置',
        'quickstart_title': '开发者快速入门',
        'quickstart_subtitle': '学习如何快速集成和使用API',
        'auth_title': '认证方式',
        'auth_method_1_title': '会话 Cookie',
        'auth_method_1_desc': '登录后获取session_id，使用Cookie进行认证',
        'auth_method_2_title': 'API Key',
        'auth_method_2_desc': '使用API密钥进行认证，适合程序化访问',
        'base_url_title': '基础 URL',
        'common_headers': '通用请求头',
        'request_headers': '# 请求头',
        'use_case_1_title': '列出所有工具',
        'use_case_1_desc': '获取所有可用的MCP工具列表及其描述',
        'use_case_2_title': '调用工具',
        'use_case_2_desc': '使用指定参数调用特定的MCP工具',
        'use_case_3_title': '导出库存数据',
        'use_case_3_desc': '将库存数据导出为CSV格式',
        'example_response': '示例响应',
        'error_handling_title': '错误处理',
        'error_handling_desc': '了解常见的API错误代码和处理方式',
        'common_errors': '常见错误代码',
        'error_401': '认证失败，请检查API Key或Session是否有效',
        'error_429': '请求频率超限，请稍后重试',
        'error_500': '服务器内部错误，请联系技术支持',
        'changelog_title': '更新日志',
        'changelog_subtitle': '查看API的版本历史和更新内容',
        'latest': '最新',
        'breaking_changes': '破坏性变更',
        'new_features': '新功能',
        'improvements': '改进',
        'bug_fixes': '错误修复',
        'view_json_api': '查看JSON API',
    },
    'en': {
        'title': 'Cross-Border Seller AI Assistant',
        'subtitle': 'All-in-one tool for 1688 + Amazon',
        'nav_home': 'Home',
        'nav_profit': 'Profit Calculator',
        'nav_inventory': 'Inventory',
        'nav_pricing': 'Pricing',
        'nav_reviews': 'Reviews',
        'nav_competitor': 'Competitor Prices',
        'nav_analytics': 'Analytics',
        'competitor_page_title': 'Competitor Price Analysis',
        'competitor_search_placeholder': 'Search ASIN or Keyword',
        'competitor_max_results': 'Max Results',
        'competitor_col_asin': 'ASIN',
        'competitor_col_product': 'Product Name',
        'competitor_col_price': 'Price',
        'competitor_col_rating': 'Rating',
        'competitor_col_seller': 'Seller',
        'competitor_no_results': 'No competitors found',
        'competitor_found_count': 'X competitors found',
        'competitor_price_range': 'Price Range',
        'competitor_trends': 'Competitor Trends',
        'price_history': 'Price History',
        'market_position': 'Market Position',
        'price_alert': 'Price Alert',
        'significant_change': 'Significant Change',
        'view_history': 'View History',
        'price_rank': 'Price Rank',
        'percentile': 'Percentile',
        'relative_position': 'Relative Position',
        'current_position': 'Current Position',
        'position_premium': 'Premium',
        'position_upper_mid': 'Upper Mid',
        'position_lower_mid': 'Lower Mid',
        'position_budget': 'Budget',
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
        'english': 'English',
        'low_stock_page_title': 'Low Stock Alerts',
        'low_stock_threshold_label': 'Stock Threshold',
        'low_stock_platform_filter_label': 'Platform Filter',
        'low_stock_platform_all': 'All',
        'low_stock_platform_1688': '1688',
        'low_stock_platform_amazon': 'Amazon',
        'low_stock_apply_button': 'Apply Filters',
        'low_stock_col_product_name': 'Product Name',
        'low_stock_col_sku': 'SKU',
        'low_stock_col_platform': 'Platform',
        'low_stock_col_current_stock': 'Current Stock',
        'low_stock_col_shortage': 'Shortage',
        'low_stock_col_severity': 'Severity',
        'low_stock_no_alerts': 'No low stock alerts',
        'low_stock_summary': 'X low stock alerts total',
        'reviews_page_title': 'Review Alerts',
        'reviews_filter_rating': 'Filter by Rating',
        'reviews_filter_days': 'Days Back',
        'reviews_all_ratings': 'All Ratings',
        'reviews_reviewer': 'Reviewer',
        'reviews_product': 'Product',
        'reviews_rating': 'Rating',
        'reviews_date': 'Date',
        'reviews_suggested_response': 'Suggested Response',
        'reviews_no_alerts': 'No review alerts',
        'reviews_alert_count': 'X reviews need attention',
        'reviews_supplier_issue': 'Supplier Issue',
        'reviews_critical_review': 'Critical Review',
        'reviews_response_needed': 'Response Needed',
        'reviews_action_required': 'Action Required',
        'reviews_review_text': 'Review Text',
        'reviews_issue_type': 'Issue Type',
        'reviews_priority': 'Priority',
        'reviews_priority_critical': 'Critical',
        'reviews_priority_high': 'High',
        'reviews_priority_medium': 'Medium',
        'reviews_copy_response': 'Copy Response',
        'reviews_copied': 'Copied!',
        'api_error_title': 'API Error',
        'api_error_invalid_json': 'Invalid JSON data',
        'api_error_missing_params': 'Missing required parameters',
        'api_error_tool_not_found': 'Tool not found',
        'api_error_internal': 'Internal server error',
        'api_success': 'Operation successful',
        'api_tools_list': 'Available tools list',
        'api_tool_info': 'Tool information',
        'api_tool_called': 'Tool call result',
        'api_params': 'Parameters',
        'api_result': 'Result',
        'api_description': 'Description',
        'api_required_params': 'Required parameters',
        'api_optional_params': 'Optional parameters',
        'dashboard_page_title': 'Dashboard',
        'dashboard_low_stock': 'Low Stock Products',
        'dashboard_pending_orders': 'Pending Orders',
        'dashboard_negative_reviews': 'Negative Reviews',
        'dashboard_todays_revenue': "Today's Revenue",
        'dashboard_quick_actions': 'Quick Actions',
        'dashboard_refresh': 'Refresh',
        'dashboard_last_updated': 'Last Updated',
        'dashboard_critical': 'Critical',
        'dashboard_warning': 'Warning',
        'dashboard_go_to_inventory': 'View Inventory',
        'dashboard_go_to_orders': 'View Orders',
        'dashboard_go_to_reviews': 'View Reviews',
        'task_queue': 'Task Queue',
        'task_processing': 'Processing',
        'task_completed': 'Completed',
        'task_failed': 'Failed',
        'task_pending': 'Pending',
        'dashboard_sync_status': 'Sync Status',
        'dashboard_active_tasks': 'Active Tasks',
        'dashboard_recent_tasks': 'Recent Tasks',
        'task_view_all': 'View All',
        'task_no_active': 'No active tasks',
        'analytics_page_title': 'Analytics Dashboard',
        'sales_trend': 'Sales Trend',
        'revenue_trend': 'Revenue Trend',
        'low_stock_trend': 'Low Stock Alerts Trend',
        'review_sentiment': 'Review Sentiment',
        'order_status': 'Order Status',
        'date_range': 'Date Range',
        'days_7': 'Last 7 Days',
        'days_30': 'Last 30 Days',
        'days_90': 'Last 90 Days',
        'total_orders': 'Total Orders',
        'total_revenue': 'Total Revenue',
        'avg_order_value': 'Avg Order Value',
        'low_stock_count': '低库存项目',
        'analytics_summary': '统计概览',
        'nav_analytics': '数据分析',
        'offline_title': '您已离线',
        'offline_desc': '网络连接已断开，请检查您的网络设置',
        'cached_data_available': '有可用的缓存数据',
        'try_again': '重试',
        'go_to_dashboard': '返回仪表板',
        'offline_indicator': '您已离线',
        'install_app': '安装应用',
        'add_to_home_screen': '添加到主屏幕',
        'not_now': '暂不需要',
        'schedule_management': '任务调度',
        'schedule_desc': '管理定时任务和自动化工作流',
        'create_schedule': '创建调度',
        'edit_schedule': '编辑调度',
        'schedule_name': '调度名称',
        'schedule_name_placeholder': '例如：每日库存检查',
        'task_type': '任务类型',
        'schedule_type': '调度类型',
        'interval': '间隔',
        'cron': 'Cron表达式',
        'cron_expression': 'Cron表达式',
        'next_run': '下次运行',
        'last_run': '上次运行',
        'scheduled_tasks': '定时任务列表',
        'schedule_active': '运行中',
        'schedule_paused': '已暂停',
        'schedule_total_runs': '总执行次数',
        'available_task_templates': '可用任务模板',
        'select_task_type': '选择任务类型',
        'run_every': '每隔执行',
        'minutes': '分钟',
        'hours': '小时',
        'days': '天',
        'interval_help': '设置任务重复执行的时间间隔',
        'cron_preview': 'Cron预览',
        'cron_invalid': '无效的Cron表达式',
        'cron_help': '格式: 分 时 日 月 周 (0-6, 0=周日)',
        'minute': '分',
        'hour': '时',
        'day_of_month': '日',
        'month': '月',
        'day_of_week': '周',
        'task_parameters': '任务参数',
        'task_parameters_desc': '根据任务类型配置执行参数',
        'enable_schedule': '启用调度',
        'schedule_enabled': '调度已启用',
        'schedule_disabled': '调度已暂停',
        'notification_preferences': '通知设置',
        'notifications': '通知设置',
        'email_notifications': '邮件通知',
        'slack_notifications': 'Slack通知',
        'wechat_notifications': '企业微信通知',
        'dingtalk_notifications': '钉钉通知',
        'email_address': '邮箱地址',
        'webhook_url': 'Webhook地址',
        'wechat_webhook_url': '企业微信Webhook地址',
        'dingtalk_webhook_url': '钉钉Webhook地址',
        'wechat_webhook_help': '在企业微信管理后台获取群机器人的Webhook地址',
        'dingtalk_webhook_help': '在钉钉群设置中获取群机器人的Webhook地址',
        'slack_webhook_help': '在Slack App设置中获取Incoming Webhook地址',
        'enable_wechat': '启用企业微信',
        'enable_dingtalk': '启用钉钉',
        'send_dingtalk_test': '发送钉钉测试',
        'international_only': '国际版',
        'slack_notifications_desc': '适用于国际团队协作',
        'test_sent_success': '测试消息已发送',
        'test_sent_failed': '发送失败，请检查配置',
        'smtp_settings': 'SMTP设置',
        'wechat_setup': '企业微信配置',
        'smtp_host': 'SMTP服务器',
        'smtp_port': 'SMTP端口',
        'smtp_username': 'SMTP用户名',
        'smtp_password': 'SMTP密码',
        'notification_low_stock': '库存预警通知',
        'notification_reviews': '评论通知',
        'notification_tasks': '任务通知',
        'notification_frequency': '通知频率',
        'notification_immediate': '立即发送',
        'notification_hourly': '每小时汇总',
        'notification_daily': '每日汇总',
        'notification_queue': '通知队列',
        'notification_history': '通知历史',
        'notification_no_history': '暂无通知历史',
        'save_settings': '保存设置',
        'send_test': '发送测试',
        'send_wechat_test': '发送企业微信测试',
        'notify_on_success': '任务成功时通知',
        'notify_on_failure': '任务失败时通知',
        'actions': '操作',
        'edit': '编辑',
        'toggle': '切换',
        'delete': '删除',
        'back_to_schedule': '返回调度管理',
        'active': '活动',
        'paused': '已暂停',
        'no_schedules': '暂无定时任务',
        'no_schedules_desc': '创建一个定时任务来自动化您的工作流程',
        'confirm_delete': '确定要删除这个调度任务吗？',
        'save': '保存',
        'cancel': '取消',
        'save_failed': '保存失败',
        'sync_inventory': '同步库存',
        'sync_inventory_desc': '同步1688和Amazon库存',
        'check_alerts': '检查警报',
        'check_alerts_desc': '检查库存和评论警报',
        'sync_prices': '同步价格',
        'sync_prices_desc': '同步1688成本和Amazon价格',
        'fetch_orders': '获取订单',
        'fetch_orders_desc': '从Amazon获取最新订单',
        'audit_logs': '操作日志',
        'audit_action': '操作',
        'audit_user': '用户',
        'audit_resource': '资源',
        'audit_details': '详情',
        'audit_timestamp': '时间',
        'audit_ip_address': 'IP地址',
        'export_logs': '导出日志',
        'filter_by_user': '按用户筛选',
        'filter_by_action': '按操作筛选',
        'filter_by_resource': '按资源筛选',
        'filter_by_date': '按日期筛选',
        'no_logs_found': '暂无日志记录',
        'log_details': '日志详情',
        'view_timeline': '查看时间线',
        'export_csv': '导出CSV',
        'export_json': '导出JSON',
        'all_actions': '所有操作',
        'all_resources': '所有资源',
        'date_from': '开始日期',
        'date_to': '结束日期',
        'apply_filters': '应用筛选',
        'clear_filters': '清除筛选',
        'total_logs': '共 X 条记录',
        'page': '第',
        'of': '页',
        'previous': '上一页',
        'next': '下一页',
    },
    'en': {
        'title': 'Cross-Border Seller AI Assistant',
        'subtitle': 'All-in-one tool for 1688 + Amazon',
        'nav_home': 'Home',
        'nav_profit': 'Profit Calculator',
        'nav_inventory': 'Inventory',
        'nav_pricing': 'Pricing',
        'nav_reviews': 'Reviews',
        'nav_competitor': 'Competitor Prices',
        'competitor_page_title': 'Competitor Price Analysis',
        'competitor_search_placeholder': 'Search ASIN or Keyword',
        'competitor_max_results': 'Max Results',
        'competitor_col_asin': 'ASIN',
        'competitor_col_product': 'Product Name',
        'competitor_col_price': 'Price',
        'competitor_col_rating': 'Rating',
        'competitor_col_seller': 'Seller',
        'competitor_no_results': 'No competitors found',
        'competitor_found_count': 'X competitors found',
        'competitor_price_range': 'Price Range',
        'competitor_trends': 'Competitor Trends',
        'price_history': 'Price History',
        'market_position': 'Market Position',
        'price_alert': 'Price Alert',
        'significant_change': 'Significant Change',
        'view_history': 'View History',
        'price_rank': 'Price Rank',
        'percentile': 'Percentile',
        'relative_position': 'Relative Position',
        'current_position': 'Current Position',
        'position_premium': 'Premium',
        'position_upper_mid': 'Upper Mid',
        'position_lower_mid': 'Lower Mid',
        'position_budget': 'Budget',
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
        'english': 'English',
        'low_stock_page_title': 'Low Stock Alerts',
        'low_stock_threshold_label': 'Stock Threshold',
        'low_stock_platform_filter_label': 'Platform Filter',
        'low_stock_platform_all': 'All',
        'low_stock_platform_1688': '1688',
        'low_stock_platform_amazon': 'Amazon',
        'low_stock_apply_button': 'Apply Filters',
        'low_stock_col_product_name': 'Product Name',
        'low_stock_col_sku': 'SKU',
        'low_stock_col_platform': 'Platform',
        'low_stock_col_current_stock': 'Current Stock',
        'low_stock_col_shortage': 'Shortage',
        'low_stock_col_severity': 'Severity',
        'low_stock_no_alerts': 'No low stock alerts',
        'low_stock_summary': 'X low stock alerts total',
        'reviews_page_title': 'Review Alerts',
        'reviews_filter_rating': 'Filter by Rating',
        'reviews_filter_days': 'Days Back',
        'reviews_all_ratings': 'All Ratings',
        'reviews_reviewer': 'Reviewer',
        'reviews_product': 'Product',
        'reviews_rating': 'Rating',
        'reviews_date': 'Date',
        'reviews_suggested_response': 'Suggested Response',
        'reviews_no_alerts': 'No review alerts',
        'reviews_alert_count': 'X reviews need attention',
        'reviews_supplier_issue': 'Supplier Issue',
        'reviews_critical_review': 'Critical Review',
        'reviews_response_needed': 'Response Needed',
        'reviews_action_required': 'Action Required',
        'reviews_review_text': 'Review Text',
        'reviews_issue_type': 'Issue Type',
        'reviews_priority': 'Priority',
        'reviews_priority_critical': 'Critical',
        'reviews_priority_high': 'High',
        'reviews_priority_medium': 'Medium',
        'reviews_copy_response': 'Copy Response',
        'reviews_copied': 'Copied!',
        'api_error_title': 'API Error',
        'api_error_invalid_json': 'Invalid JSON data',
        'api_error_missing_params': 'Missing required parameters',
        'api_error_tool_not_found': 'Tool not found',
        'api_error_internal': 'Internal server error',
        'api_success': 'Operation successful',
        'api_tools_list': 'Available tools list',
        'api_tool_info': 'Tool information',
        'api_tool_called': 'Tool call result',
        'api_params': 'Parameters',
        'api_result': 'Result',
        'api_description': 'Description',
        'api_required_params': 'Required parameters',
        'api_optional_params': 'Optional parameters',
        'dashboard_page_title': 'Dashboard',
        'dashboard_low_stock': 'Low Stock Products',
        'dashboard_pending_orders': 'Pending Orders',
        'dashboard_negative_reviews': 'Negative Reviews',
        'dashboard_todays_revenue': "Today's Revenue",
        'dashboard_quick_actions': 'Quick Actions',
        'dashboard_refresh': 'Refresh',
        'dashboard_last_updated': 'Last Updated',
        'dashboard_critical': 'Critical',
        'dashboard_warning': 'Warning',
        'dashboard_go_to_inventory': 'View Inventory',
        'dashboard_go_to_orders': 'View Orders',
        'dashboard_go_to_reviews': 'View Reviews',
        'task_queue': 'Task Queue',
        'task_processing': 'Processing',
        'task_completed': 'Completed',
        'task_failed': 'Failed',
        'task_pending': 'Pending',
        'dashboard_sync_status': 'Sync Status',
        'dashboard_active_tasks': 'Active Tasks',
        'dashboard_recent_tasks': 'Recent Tasks',
        'task_view_all': 'View All',
        'task_no_active': 'No active tasks',
        'export': 'Export',
        'export_all': 'Export All',
        'csv_format': 'CSV Format',
        'pdf_format': 'PDF Format',
        'download': 'Download',
        'export_inventory': 'Export Inventory',
        'export_orders': 'Export Orders',
        'export_reviews': 'Export Reviews',
        'export_competitors': 'Export Competitors',
        'export_analytics': 'Export Analytics',
        'export_report': 'Export Report',
        'date_range': 'Date Range',
        'filter': 'Filter',
        'analytics_page_title': 'Analytics Dashboard',
        'analytics_date_range': 'Date Range',
        'analytics_last_7_days': 'Last 7 Days',
        'analytics_last_30_days': 'Last 30 Days',
        'analytics_last_90_days': 'Last 90 Days',
        'analytics_total_orders': 'Total Orders',
        'analytics_total_revenue': 'Total Revenue',
        'analytics_avg_daily_orders': 'Avg Daily Orders',
        'analytics_avg_order_value': 'Avg Order Value',
        'analytics_low_stock_alerts': 'Low Stock Alerts',
        'analytics_review_alerts': 'Review Alerts',
        'analytics_orders_trend': 'Orders Trend',
        'analytics_revenue_trend': 'Revenue Trend',
        'analytics_order_status': 'Order Status Distribution',
        'analytics_reviews_by_rating': 'Reviews by Rating',
        'analytics_no_data': 'No data available',
        'revenue_overview': 'Revenue Overview',
        'top_products': 'Top Products',
        'inventory_status': 'Inventory Status',
        'low_stock_count': 'Low Stock Items',
        'analytics_summary': 'Summary Statistics',
        'offline_title': "You're Offline",
        'offline_desc': 'Your internet connection is offline. Please check your network settings.',
        'cached_data_available': 'Cached data available',
        'try_again': 'Try Again',
        'go_to_dashboard': 'Go to Dashboard',
        'offline_indicator': "You're offline",
        'install_app': 'Install App',
        'add_to_home_screen': 'Add to Home Screen',
        'not_now': 'Not Now',
        'schedule_management': 'Task Schedule',
        'schedule_desc': 'Manage scheduled tasks and automated workflows',
        'create_schedule': 'Create Schedule',
        'edit_schedule': 'Edit Schedule',
        'schedule_name': 'Schedule Name',
        'schedule_name_placeholder': 'e.g., Daily Inventory Check',
        'task_type': 'Task Type',
        'schedule_type': 'Schedule Type',
        'interval': 'Interval',
        'cron': 'Cron Expression',
        'cron_expression': 'Cron Expression',
        'next_run': 'Next Run',
        'last_run': 'Last Run',
        'scheduled_tasks': 'Scheduled Tasks',
        'schedule_active': 'Active',
        'schedule_paused': 'Paused',
        'schedule_total_runs': 'Total Runs',
        'available_task_templates': 'Available Task Templates',
        'select_task_type': 'Select Task Type',
        'run_every': 'Run Every',
        'minutes': 'Minutes',
        'hours': 'Hours',
        'days': 'Days',
        'interval_help': 'Set the time interval for task repetition',
        'cron_preview': 'Cron Preview',
        'cron_invalid': 'Invalid cron expression',
        'cron_help': 'Format: min hour day month weekday (0-6, 0=Sunday)',
        'minute': 'Min',
        'hour': 'Hour',
        'day_of_month': 'Day',
        'month': 'Month',
        'day_of_week': 'Weekday',
        'task_parameters': 'Task Parameters',
        'task_parameters_desc': 'Configure parameters based on task type',
        'enable_schedule': 'Enable Schedule',
        'schedule_enabled': 'Schedule Enabled',
        'schedule_disabled': 'Schedule Paused',
        'notification_preferences': 'Notification Preferences',
        'notifications': 'Notifications',
        'email_notifications': 'Email Notifications',
        'slack_notifications': 'Slack Notifications',
        'wechat_notifications': 'WeChat Work Notifications',
        'dingtalk_notifications': 'DingTalk Notifications',
        'email_address': 'Email Address',
        'webhook_url': 'Webhook URL',
        'wechat_webhook_url': 'WeChat Work Webhook URL',
        'dingtalk_webhook_url': 'DingTalk Webhook URL',
        'wechat_webhook_help': 'Get the webhook URL from WeChat Work admin panel',
        'dingtalk_webhook_help': 'Get the webhook URL from DingTalk group settings',
        'slack_webhook_help': 'Get the Incoming Webhook URL from Slack App settings',
        'enable_wechat': 'Enable WeChat Work',
        'enable_dingtalk': 'Enable DingTalk',
        'send_dingtalk_test': 'Test DingTalk',
        'international_only': 'International',
        'slack_notifications_desc': 'For international team collaboration',
        'test_sent_success': 'Test message sent',
        'test_sent_failed': 'Failed to send, please check config',
        'smtp_settings': 'SMTP Settings',
        'wechat_setup': 'WeChat Work Setup',
        'smtp_host': 'SMTP Host',
        'smtp_port': 'SMTP Port',
        'smtp_username': 'SMTP Username',
        'smtp_password': 'SMTP Password',
        'notification_low_stock': 'Low Stock Alerts',
        'notification_reviews': 'Review Alerts',
        'notification_tasks': 'Task Notifications',
        'notification_frequency': 'Notification Frequency',
        'notification_immediate': 'Send Immediately',
        'notification_hourly': 'Hourly Digest',
        'notification_daily': 'Daily Digest',
        'notification_queue': 'Notification Queue',
        'notification_history': 'Notification History',
        'notification_no_history': 'No notification history',
        'save_settings': 'Save Settings',
        'send_test': 'Send Test',
        'send_wechat_test': 'Test WeChat',
        'notify_on_success': 'Notify on task success',
        'notify_on_failure': 'Notify on task failure',
        'actions': 'Actions',
        'edit': 'Edit',
        'toggle': 'Toggle',
        'delete': 'Delete',
        'back_to_schedule': 'Back to Schedule',
        'active': 'Active',
        'paused': 'Paused',
        'no_schedules': 'No Scheduled Tasks',
        'no_schedules_desc': 'Create a scheduled task to automate your workflow',
        'confirm_delete': 'Are you sure you want to delete this schedule?',
        'save': 'Save',
        'cancel': 'Cancel',
        'save_failed': 'Failed to save',
        'sync_inventory': 'Sync Inventory',
        'sync_inventory_desc': 'Sync 1688 and Amazon inventory',
        'check_alerts': 'Check Alerts',
        'check_alerts_desc': 'Check inventory and review alerts',
        'sync_prices': 'Sync Prices',
        'sync_prices_desc': 'Sync 1688 cost and Amazon prices',
        'fetch_orders': 'Fetch Orders',
        'fetch_orders_desc': 'Get latest orders from Amazon',
        'audit_logs': 'Audit Logs',
        'audit_action': 'Action',
        'audit_user': 'User',
        'audit_resource': 'Resource',
        'audit_details': 'Details',
        'audit_timestamp': 'Timestamp',
        'audit_ip_address': 'IP Address',
        'export_logs': 'Export Logs',
        'filter_by_user': 'Filter by User',
        'filter_by_action': 'Filter by Action',
        'filter_by_resource': 'Filter by Resource',
        'filter_by_date': 'Filter by Date',
        'no_logs_found': 'No logs found',
        'log_details': 'Log Details',
        'view_timeline': 'View Timeline',
        'export_csv': 'Export CSV',
        'export_json': 'Export JSON',
        'all_actions': 'All Actions',
        'all_resources': 'All Resources',
        'date_from': 'Start Date',
        'date_to': 'End Date',
        'apply_filters': 'Apply Filters',
        'clear_filters': 'Clear Filters',
        'total_logs': 'X logs total',
        'page': 'Page',
        'of': 'of',
        'previous': 'Previous',
        'next': 'Next',
        'stockout_prediction': 'Stockout Prediction',
        'days_until_stockout': 'Days Until Stockout',
        'recommended_reorder': 'Recommended Reorder',
        'risk_level': 'Risk Level',
        'risk_high': 'High Risk',
        'risk_medium': 'Medium Risk',
        'risk_low': 'Low Risk',
        'risk_critical': 'Critical Risk',
        'inventory_health': 'Inventory Health',
        'lead_time': 'Lead Time',
        'days_of_supply': 'Days of Supply',
        'avg_days_supply': 'Avg Days Supply',
        'products_at_risk': 'Products at Risk',
        'reorder_urgency': 'Reorder Urgency',
        'urgency_critical': 'Critical',
        'urgency_high': 'High',
        'urgency_medium': 'Medium',
        'urgency_low': 'Low',
        'predicted_stockout': 'Predicted Stockout',
        'safety_stock': 'Safety Stock',
        'reorder_point': 'Reorder Point',
        'risk_threshold': 'Risk Threshold',
        'no_predictions': 'No stockout predictions',
        'price_optimization': 'Price Optimization',
        'recommended_price': 'Recommended Price',
        'price_range': 'Price Range',
        'competitor_analysis': 'Competitor Analysis',
        'target_margin': 'Target Margin',
        'aggressive': 'Aggressive',
        'balanced': 'Balanced',
        'premium': 'Premium',
        'optimal_price': 'Optimal Price',
        'min_price': 'Minimum Price',
        'max_price': 'Maximum Price',
        'avg_price': 'Average Price',
        'current_price': 'Current Price',
        'price_strategy': 'Price Strategy',
        'margin_analysis': 'Margin Analysis',
        'competitive_threats': 'Competitive Threats',
        'threat_level': 'Threat Level',
        'threat_critical': 'Critical',
        'threat_high': 'High',
        'threat_medium': 'Medium',
        'price_sensitivity': 'Price Sensitivity',
        'elasticity': 'Elasticity',
        'apply_price': 'Apply Price',
        'set_alert': 'Set Alert',
        'price_recommendation': 'Price Recommendation',
        'competitors_found': 'Competitors Found',
        'market_position': 'Market Position',
        'budget': 'Budget',
        'mid_market': 'Mid-Market',
        'price_optimizer_page_title': 'Price Optimizer',
        'rate_limit_exceeded': 'Rate Limit Exceeded',
        'try_again_in': 'Try again in',
        'upgrade_plan': 'Upgrade Plan',
        'current_limit': 'Current Limit',
        'remaining': 'Remaining',
        'admin': '管理员',
        'manager': '经理',
        'viewer': '访客',
        'user_management': '用户管理',
        'role_management': '角色管理',
        'permissions': '权限',
        'audit_logs': '审计日志',
        'admin_dashboard': '管理员仪表板',
        'total_users': '用户总数',
        'active_sessions': '活跃会话',
        'api_usage': 'API使用量',
        'recent_activity': '最近活动',
        'system_health': '系统健康',
        'add_user': '添加用户',
        'edit_user': '编辑用户',
        'delete_user': '删除用户',
        'assign_role': '分配角色',
        'enable_user': '启用用户',
        'disable_user': '禁用用户',
        'search_users': '搜索用户',
        'filter_by_role': '按角色筛选',
        'all_roles': '所有角色',
        'permission_matrix': '权限矩阵',
        'role_permissions': '角色权限',
        'save_changes': '保存更改',
        'confirm_delete_user': '确定要删除此用户吗？',
        'user_created': '用户创建成功',
        'user_updated': '用户更新成功',
        'user_deleted': '用户删除成功',
        'invalid_credentials': '无效的凭据',
        'login_required': '请先登录',
        'access_denied': '访问被拒绝',
        'insufficient_permissions': '权限不足',
    },
    'en': {
        'admin': 'Admin',
        'manager': 'Manager',
        'viewer': 'Viewer',
        'user_management': 'User Management',
        'role_management': 'Role Management',
        'permissions': 'Permissions',
        'audit_logs': 'Audit Logs',
        'admin_dashboard': 'Admin Dashboard',
        'total_users': 'Total Users',
        'active_sessions': 'Active Sessions',
        'api_usage': 'API Usage',
        'recent_activity': 'Recent Activity',
        'system_health': 'System Health',
        'add_user': 'Add User',
        'edit_user': 'Edit User',
        'delete_user': 'Delete User',
        'assign_role': 'Assign Role',
        'enable_user': 'Enable User',
        'disable_user': 'Disable User',
        'search_users': 'Search Users',
        'filter_by_role': 'Filter by Role',
        'all_roles': 'All Roles',
        'permission_matrix': 'Permission Matrix',
        'role_permissions': 'Role Permissions',
        'save_changes': 'Save Changes',
        'confirm_delete_user': 'Are you sure you want to delete this user?',
        'user_created': 'User created successfully',
        'user_updated': 'User updated successfully',
        'user_deleted': 'User deleted successfully',
        'invalid_credentials': 'Invalid credentials',
        'login_required': 'Please login first',
        'access_denied': 'Access denied',
        'insufficient_permissions': 'Insufficient permissions',
        'login': 'Login',
        'logout': 'Logout',
        'register': 'Register',
        'email': 'Email',
        'password': 'Password',
        'confirm_password': 'Confirm Password',
        'forgot_password': 'Forgot Password',
        'welcome': 'Welcome',
        'remember_me': 'Remember Me',
        'create_account': 'Create Account',
        'already_have_account': 'Already have an account',
        'forgot_password_desc': 'Enter your email address and we will send you a password reset link',
        'reset_password': 'Reset Password',
        'new_password': 'New Password',
        'confirm_new_password': 'Confirm New Password',
        'password_reset_sent': 'Password reset link has been sent to your email',
        'password_reset_success': 'Password reset successfully',
        'invalid_reset_token': 'Invalid or expired reset link',
        'password_mismatch': 'Passwords do not match',
        'password_too_short': 'Password must be at least 8 characters',
        'email_required': 'Email is required',
        'password_required': 'Password is required',
        'invalid_email_format': 'Invalid email format',
        'registration_success': 'Registration successful, please login',
        'registration_failed': 'Registration failed, please try again',
        'account_disabled': 'Account has been disabled',
        'login_success': 'Login successful',
        'logout_success': 'Logged out successfully',
        'logout_confirm': 'Are you sure you want to logout?',
        'session_expired': 'Session expired, please login again',
        'unauthorized': 'Unauthorized access',
        'role_admin': 'Administrator',
        'role_manager': 'Manager',
        'role_viewer': 'Viewer',
        'select_role': 'Select Role',
        'terms_of_service': 'Terms of Service',
        'agree_terms': 'I have read and agree to the Terms of Service',
        'user_profile': 'User Profile',
        'change_password': 'Change Password',
        'current_password': 'Current Password',
        'profile_settings': 'Profile Settings',
        'quickstart_title': 'Quick Start Guide',
        'quickstart_subtitle': 'Learn how to quickly integrate and use the API',
        'auth_title': 'Authentication',
        'auth_method_1_title': 'Session Cookie',
        'auth_method_1_desc': 'Login to get session_id, authenticate using Cookie',
        'auth_method_2_title': 'API Key',
        'auth_method_2_desc': 'Authenticate using API key, suitable for programmatic access',
        'base_url_title': 'Base URL',
        'common_headers': 'Common Headers',
        'request_headers': '# Request Headers',
        'use_case_1_title': 'List All Tools',
        'use_case_1_desc': 'Get a list of all available MCP tools and their descriptions',
        'use_case_2_title': 'Call a Tool',
        'use_case_2_desc': 'Call a specific MCP tool with the given parameters',
        'use_case_3_title': 'Export Inventory',
        'use_case_3_desc': 'Export inventory data in CSV format',
        'example_response': 'Example Response',
        'error_handling_title': 'Error Handling',
        'error_handling_desc': 'Learn about common API error codes and how to handle them',
        'common_errors': 'Common Error Codes',
        'error_401': 'Authentication failed, please check if API Key or Session is valid',
        'error_429': 'Rate limit exceeded, please retry later',
        'error_500': 'Internal server error, please contact support',
        'changelog_title': 'Changelog',
        'changelog_subtitle': 'View version history and updates',
        'latest': 'Latest',
        'breaking_changes': 'Breaking Changes',
        'new_features': 'New Features',
        'improvements': 'Improvements',
        'bug_fixes': 'Bug Fixes',
        'view_json_api': 'View JSON API',
    }
}

TOOL_REGISTRY = {}

def get_text(lang, key):
    """Get bilingual text"""
    return TEXT.get(lang, 'en').get(key, key)

def register_tool(name: str, func: Callable, description: str, params_schema: dict, return_schema: dict = None):
    """Register a tool in the registry"""
    TOOL_REGISTRY[name] = {
        'name': name,
        'function': func,
        'description': description,
        'params_schema': params_schema,
        'return_schema': return_schema or {'type': 'string'}
    }

def init_tool_registry():
    """Initialize the tool registry with all MCP tools"""

    register_tool(
        'get_low_stock_alerts',
        None,
        'Return all SKUs where stock is below the configured threshold. 获取低于阈值的库存警告。',
        {
            'threshold': {'type': 'integer', 'description': 'Custom stock threshold (default: 10)', 'required': False, 'default': 10},
            'platform': {'type': 'string', 'description': "Filter by platform: '1688', 'Amazon', or 'both'", 'required': False, 'default': 'both'},
            'response_format': {'type': 'string', 'description': "Output format: 'markdown' or 'json'", 'required': False, 'default': 'json'}
        }
    )

    register_tool(
        'get_competitor_prices',
        None,
        'Search Amazon for competitor product prices. 在Amazon搜索竞品价格。',
        {
            'sku': {'type': 'string', 'description': 'SKU or search keyword to find competitors', 'required': True},
            'limit': {'type': 'integer', 'description': 'Maximum competitors to return (1-20)', 'required': False, 'default': 5},
            'response_format': {'type': 'string', 'description': "Output format: 'markdown' or 'json'", 'required': False, 'default': 'json'}
        }
    )

    register_tool(
        'get_review_alerts',
        None,
        'Get actionable alerts for reviews that need immediate attention. 获取需要立即处理的评论警告。',
        {
            'days': {'type': 'integer', 'description': 'Number of days to look back (1-90)', 'required': False, 'default': 7},
            'include_supplier_flags': {'type': 'boolean', 'description': 'Flag reviews that indicate supplier quality issues', 'required': False, 'default': True},
            'response_format': {'type': 'string', 'description': "Output format: 'markdown' or 'json'", 'required': False, 'default': 'json'}
        }
    )

    register_tool(
        'get_product_cost_1688',
        None,
        'Get product cost and pricing information from 1688 supplier platform. 从1688获取产品成本。',
        {
            'sku': {'type': 'string', 'description': 'Product SKU identifier', 'required': True},
            'response_format': {'type': 'string', 'description': "Output format: 'markdown' or 'json'", 'required': False, 'default': 'json'}
        }
    )

    register_tool(
        'calculate_amazon_price',
        None,
        'Calculate recommended Amazon selling price based on 1688 cost. 基于1688成本计算Amazon售价。',
        {
            'sku': {'type': 'string', 'description': 'Product SKU identifier', 'required': True},
            'cost_cny': {'type': 'number', 'description': 'Product cost in CNY (fetches from 1688 if not provided)', 'required': False},
            'target_margin_percent': {'type': 'number', 'description': 'Target profit margin percentage (default: 25%)', 'required': False, 'default': 25.0},
            'shipping_cost_usd': {'type': 'number', 'description': 'Shipping cost per unit in USD (default: $2.00)', 'required': False, 'default': 2.0},
            'response_format': {'type': 'string', 'description': "Output format: 'markdown' or 'json'", 'required': False, 'default': 'json'}
        }
    )

    register_tool(
        'sync_inventory',
        None,
        'Compare 1688 stock levels against Amazon listings and flag inventory mismatches. 比较1688和Amazon库存。',
        {
            'sku': {'type': 'string', 'description': 'Product SKU to synchronize', 'required': True},
            'response_format': {'type': 'string', 'description': "Output format: 'markdown' or 'json'", 'required': False, 'default': 'json'}
        }
    )

    register_tool(
        'get_orders_amazon',
        None,
        'Fetch recent Amazon orders from the Selling Partner API. 获取Amazon订单。',
        {
            'days': {'type': 'integer', 'description': 'Number of days to look back (1-90)', 'required': False, 'default': 7},
            'status': {'type': 'string', 'description': "Filter by order status (e.g., 'Pending', 'Shipped')", 'required': False},
            'limit': {'type': 'integer', 'description': 'Maximum orders to return (1-100)', 'required': False, 'default': 50},
            'response_format': {'type': 'string', 'description': "Output format: 'markdown' or 'json'", 'required': False, 'default': 'json'}
        }
    )

    register_tool(
        'get_product_reviews',
        None,
        'Get product reviews from Amazon for a specific SKU or ASIN. 获取Amazon产品评论。',
        {
            'sku': {'type': 'string', 'description': 'SKU or ASIN to fetch reviews for', 'required': True},
            'days': {'type': 'integer', 'description': 'Number of days to look back (1-90)', 'required': False, 'default': 30},
            'min_rating': {'type': 'integer', 'description': 'Filter by minimum rating (1-5)', 'required': False},
            'max_rating': {'type': 'integer', 'description': 'Filter by maximum rating (1-5)', 'required': False},
            'limit': {'type': 'integer', 'description': 'Maximum reviews to return (1-100)', 'required': False, 'default': 20},
            'response_format': {'type': 'string', 'description': "Output format: 'markdown' or 'json'", 'required': False, 'default': 'json'}
        }
    )

    register_tool(
        'get_negative_reviews',
        None,
        'Get 1-2 star reviews that need attention and response. 获取差评。',
        {
            'sku': {'type': 'string', 'description': 'Filter by specific SKU (optional)', 'required': False},
            'days': {'type': 'integer', 'description': 'Number of days to look back (1-90)', 'required': False, 'default': 7},
            'severity': {'type': 'string', 'description': "Filter by severity: 'critical' (1 star), 'warning' (2 stars), or 'all'", 'required': False, 'default': 'all'},
            'response_format': {'type': 'string', 'description': "Output format: 'markdown' or 'json'", 'required': False, 'default': 'json'}
        }
    )

    register_tool(
        'sync_price',
        None,
        'Compare 1688 cost-based pricing against current Amazon prices and flag mismatches. 比较1688成本和Amazon价格。',
        {
            'sku': {'type': 'string', 'description': 'Product SKU to sync pricing', 'required': True},
            'target_margin_percent': {'type': 'number', 'description': 'Target profit margin percentage (default: 25%)', 'required': False, 'default': 25.0},
            'shipping_cost_usd': {'type': 'number', 'description': 'Shipping cost per unit in USD (default: $2.00)', 'required': False, 'default': 2.0},
            'response_format': {'type': 'string', 'description': "Output format: 'markdown' or 'json'", 'required': False, 'default': 'json'}
        }
    )

    register_tool(
        'update_amazon_price',
        None,
        'Update the listing price on Amazon Seller Central. 更新Amazon价格。',
        {
            'sku': {'type': 'string', 'description': 'Product SKU identifier', 'required': True},
            'new_price': {'type': 'number', 'description': 'New price in USD (must be > 0)', 'required': True},
            'currency': {'type': 'string', 'description': 'Currency code (default: USD)', 'required': False, 'default': 'USD'}
        }
    )

    register_tool(
        'get_inventory_1688',
        None,
        'Get stock level for a SKU from 1688 supplier platform. 获取1688库存。',
        {
            'sku': {'type': 'string', 'description': 'Product SKU identifier', 'required': True},
            'response_format': {'type': 'string', 'description': "Output format: 'markdown' or 'json'", 'required': False, 'default': 'json'}
        }
    )

    register_tool(
        'calculate_true_profit',
        None,
        'Calculate TRUE profit including ALL cross-border cost factors. 计算真实利润。',
        {
            'sku': {'type': 'string', 'description': 'Product SKU identifier', 'required': True},
            'selling_price_usd': {'type': 'number', 'description': 'Current selling price on Amazon in USD', 'required': True},
            'cost_cny': {'type': 'number', 'description': 'Product cost from 1688 in CNY', 'required': False},
            'shipping_to_amazon_usd': {'type': 'number', 'description': 'Shipping cost from supplier to warehouse (default: $2.00)', 'required': False, 'default': 2.0},
            'fba_fee_usd': {'type': 'number', 'description': 'FBA fulfillment fee per unit in USD (default: $3.50)', 'required': False, 'default': 3.5},
            'monthly_storage_fee_usd': {'type': 'number', 'description': 'Monthly storage fee per unit in USD (default: $0.30)', 'required': False, 'default': 0.3},
            'advertising_acos_percent': {'type': 'number', 'description': 'Advertising ACoS percentage (default: 20%)', 'required': False, 'default': 20.0},
            'payment_processing_fee_percent': {'type': 'number', 'description': 'Payment processing fee percentage (default: 2.9%)', 'required': False, 'default': 2.9},
            'return_rate_percent': {'type': 'number', 'description': 'Return rate percentage (default: 5%)', 'required': False, 'default': 5.0},
            'customs_duty_percent': {'type': 'number', 'description': 'Customs duty percentage (default: 3%)', 'required': False, 'default': 3.0},
            'overhead_percent': {'type': 'number', 'description': 'Overhead percentage (default: 8%)', 'required': False, 'default': 8.0},
            'response_format': {'type': 'string', 'description': "Output format: 'markdown' or 'json'", 'required': False, 'default': 'json'}
        }
    )

    register_tool(
        'save_product_profile',
        None,
        'Save or update product cost data to keep it up-to-date. 保存产品成本数据。',
        {
            'sku': {'type': 'string', 'description': 'SKU identifier', 'required': True},
            'product_name': {'type': 'string', 'description': 'Product name', 'required': False},
            'cost_cny': {'type': 'number', 'description': 'Product cost in CNY', 'required': False},
            'shipping_to_amazon_usd': {'type': 'number', 'description': 'Shipping cost to Amazon in USD', 'required': False},
            'amazon_referral_fee_percent': {'type': 'number', 'description': 'Amazon referral fee percentage', 'required': False},
            'fba_fee_usd': {'type': 'number', 'description': 'FBA fulfillment fee in USD', 'required': False},
            'monthly_storage_fee_usd': {'type': 'number', 'description': 'Monthly storage fee in USD', 'required': False},
            'advertising_acos_percent': {'type': 'number', 'description': 'Advertising ACoS percentage', 'required': False},
            'payment_processing_fee_percent': {'type': 'number', 'description': 'Payment processing fee percentage', 'required': False},
            'return_rate_percent': {'type': 'number', 'description': 'Return rate percentage', 'required': False},
            'customs_duty_percent': {'type': 'number', 'description': 'Customs duty percentage', 'required': False},
            'overhead_percent': {'type': 'number', 'description': 'Overhead percentage', 'required': False},
            'notes': {'type': 'string', 'description': 'Additional notes', 'required': False},
            'response_format': {'type': 'string', 'description': "Output format: 'markdown' or 'json'", 'required': False, 'default': 'json'}
        }
    )

    register_tool(
        'get_product_profile',
        None,
        'Get saved product data. Returns warning if data is stale. 获取已保存的产品数据。',
        {
            'sku': {'type': 'string', 'description': 'SKU identifier', 'required': True},
            'response_format': {'type': 'string', 'description': "Output format: 'markdown' or 'json'", 'required': False, 'default': 'json'}
        }
    )

    register_tool(
        'list_all_products',
        None,
        'List all saved product profiles. Shows freshness status. 列出所有已保存的产品。',
        {
            'hours': {'type': 'integer', 'description': 'Hours to consider data stale (1-720)', 'required': False, 'default': 24},
            'response_format': {'type': 'string', 'description': "Output format: 'markdown' or 'json'", 'required': False, 'default': 'json'}
        }
    )

    register_tool(
        'get_stale_products',
        None,
        'Find products with data that needs updating. 查找需要更新的产品。',
        {
            'hours': {'type': 'integer', 'description': 'Hours to consider data stale (1-720)', 'required': False, 'default': 24},
            'response_format': {'type': 'string', 'description': "Output format: 'markdown' or 'json'", 'required': False, 'default': 'json'}
        }
    )

    register_tool(
        'update_fulfillment_amazon',
        None,
        'Update order fulfillment status on Amazon Seller Central. 更新Amazon订单状态。',
        {
            'order_id': {'type': 'string', 'description': 'Amazon order ID', 'required': True},
            'status': {'type': 'string', 'description': "New fulfillment status: 'Pending', 'Processing', 'Shipped', 'Delivered', 'Cancelled'", 'required': True}
        }
    )

    register_tool(
        'get_license_info',
        None,
        'Get current license tier and features. 获取许可证信息和功能。',
        {}
    )

init_tool_registry()

@app.context_processor
def inject_user():
    return dict(
        current_user=session.get('user'),
        PERMISSIONS=PERMISSIONS
    )

@app.route('/login', methods=['GET', 'POST'])
def login():
    lang = request.args.get('lang', 'cn')
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember_me = request.form.get('remember_me') == 'on'

        if not email or not password:
            flash(get_text(lang, 'email_required') + ' ' + get_text(lang, 'password_required'), 'error')
            return render_template('login.html', lang=lang, get_text=lambda key: get_text(lang, key))

        user = auth_service.authenticate_user(email, password)
        if user:
            token = auth_service.generate_token(user['user_id'], remember_me)
            session_id = auth_service.create_session(
                user['user_id'],
                token,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent')
            )

            audit_logger.log('login', user['user_id'], {'email': email})

            response = make_response(redirect(request.args.get('next') or url_for('index')))
            response.set_cookie('session_id', session_id, max_age=720*3600 if remember_me else 24*3600)
            response.set_cookie('auth_token', token, max_age=720*3600 if remember_me else 24*3600)

            flash(get_text(lang, 'login_success'), 'success')
            return response
        else:
            flash(get_text(lang, 'invalid_credentials'), 'error')

    return render_template('login.html', lang=lang, get_text=lambda key: get_text(lang, key))

@app.route('/logout')
def logout():
    lang = request.args.get('lang', 'cn')
    session_id = request.cookies.get('session_id')

    if session_id:
        session = auth_service.get_session(session_id)
        if session:
            auth_service.delete_session(session_id)
            audit_logger.log('logout', session['user_id'], {})

    response = make_response(redirect(url_for('login')))
    response.delete_cookie('session_id')
    response.delete_cookie('auth_token')

    flash(get_text(lang, 'logout_success'), 'success')
    return response

@app.route('/register', methods=['GET', 'POST'])
def register():
    lang = request.args.get('lang', 'cn')
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        role = request.form.get('role', 'viewer')
        terms_accepted = request.form.get('terms') == 'on'

        if not email or not password:
            flash(get_text(lang, 'email_required') + ' ' + get_text(lang, 'password_required'), 'error')
            return render_template('register.html', lang=lang, get_text=lambda key: get_text(lang, key))

        if password != confirm_password:
            flash(get_text(lang, 'password_mismatch'), 'error')
            return render_template('register.html', lang=lang, get_text=lambda key: get_text(lang, key))

        if len(password) < 8:
            flash(get_text(lang, 'password_too_short'), 'error')
            return render_template('register.html', lang=lang, get_text=lambda key: get_text(lang, key))

        result = auth_service.register_user(email, password, role)

        if result.get('success'):
            audit_logger.log('register', result['user_id'], {'email': email, 'role': role})
            flash(get_text(lang, 'registration_success'), 'success')
            return redirect(url_for('login', lang=lang))
        else:
            flash(result.get('error', get_text(lang, 'registration_failed')), 'error')

    return render_template('register.html', lang=lang, get_text=lambda key: get_text(lang, key))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    lang = request.args.get('lang', 'cn')
    if request.method == 'POST':
        email = request.form.get('email')

        if not email:
            flash(get_text(lang, 'email_required'), 'error')
            return render_template('forgot_password.html', lang=lang, get_text=lambda key: get_text(lang, key))

        result = auth_service.reset_password_request(email)

        if result.get('success') and result.get('reset_token'):
            audit_logger.log('password_reset_request', None, {'email': email})

        flash(get_text(lang, 'password_reset_sent'), 'success')
        return redirect(url_for('login', lang=lang))

    return render_template('forgot_password.html', lang=lang, get_text=lambda key: get_text(lang, key))

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    lang = request.args.get('lang', 'cn')

    user_id = auth_service.verify_reset_token(token)
    if not user_id:
        flash(get_text(lang, 'invalid_reset_token'), 'error')
        return redirect(url_for('forgot_password', lang=lang))

    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if password != confirm_password:
            flash(get_text(lang, 'password_mismatch'), 'error')
            return render_template('reset_password.html', lang=lang, token=token, get_text=lambda key: get_text(lang, key))

        if len(password) < 8:
            flash(get_text(lang, 'password_too_short'), 'error')
            return render_template('reset_password.html', lang=lang, token=token, get_text=lambda key: get_text(lang, key))

        result = auth_service.reset_password(token, password)

        if result.get('success'):
            audit_logger.log('password_reset_complete', user_id, {})
            flash(get_text(lang, 'password_reset_success'), 'success')
            return redirect(url_for('login', lang=lang))
        else:
            flash(result.get('error', get_text(lang, 'invalid_reset_token')), 'error')

    return render_template('reset_password.html', lang=lang, token=token, get_text=lambda key: get_text(lang, key))

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    lang = request.args.get('lang', 'cn')
    data = request.get_json()

    email = data.get('email')
    password = data.get('password')
    remember_me = data.get('remember_me', False)

    if not email or not password:
        return jsonify({'error': get_text(lang, 'email_required') + ' ' + get_text(lang, 'password_required')}), 400

    user = auth_service.authenticate_user(email, password)
    if not user:
        return jsonify({'error': get_text(lang, 'invalid_credentials')}), 401

    token = auth_service.generate_token(user['user_id'], remember_me)
    session_id = auth_service.create_session(
        user['user_id'],
        token,
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent')
    )

    audit_logger.log('api_login', user['user_id'], {'email': email})

    return jsonify({
        'success': True,
        'token': token,
        'session_id': session_id,
        'user': {
            'user_id': user['user_id'],
            'email': user['email'],
            'role': user['role']
        }
    })

@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    lang = request.args.get('lang', 'cn')
    session_id = request.cookies.get('session_id')

    if session_id:
        session = auth_service.get_session(session_id)
        if session:
            auth_service.delete_session(session_id)
            audit_logger.log('api_logout', session['user_id'], {})

    return jsonify({'success': True, 'message': get_text(lang, 'logout_success')})

@app.route('/api/auth/me')
def api_me():
    lang = request.args.get('lang', 'cn')
    token = None
    session_id = request.cookies.get('session_id')

    if 'Authorization' in request.headers:
        auth_header = request.headers['Authorization']
        try:
            scheme, token = auth_header.split(' ', 1)
            if scheme.lower() != 'bearer':
                token = None
        except ValueError:
            token = None

    if not token and session_id:
        session = auth_service.get_session(session_id)
        if session:
            token = session['token']

    if not token:
        return jsonify({'error': get_text(lang, 'login_required')}), 401

    payload = auth_service.verify_token(token)
    if not payload:
        return jsonify({'error': get_text(lang, 'session_expired')}), 401

    user = auth_service.get_user(payload['user_id'])
    if not user:
        return jsonify({'error': get_text(lang, 'login_required')}), 401

    return jsonify({
        'success': True,
        'user': {
            'user_id': user['user_id'],
            'email': user['email'],
            'role': user['role'],
            'created_at': user['created_at'],
            'last_login': user['last_login']
        }
    })

@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard page with key metrics"""
    lang = request.args.get('lang', 'cn')
    user = session.get('user')

    low_stock_count = 0
    low_stock_critical = 0
    pending_orders_count = 0
    negative_reviews_count = 0
    negative_reviews_critical = 0
    todays_revenue = 0.0

    low_stock_history = [0] * 7
    revenue_history = [0.0] * 7
    reviews_history = [0] * 7
    orders_history = [0] * 7

    active_tasks = get_active_tasks()
    recent_tasks = get_all_tasks(limit=5)

    METRICS_CACHE = {
        'data': None,
        'timestamp': None
    }
    METRICS_CACHE_LOCK = threading.Lock()
    CACHE_DURATION = 60

    with METRICS_CACHE_LOCK:
        if (METRICS_CACHE['data'] and METRICS_CACHE['timestamp'] and
            (datetime.now() - METRICS_CACHE['timestamp']).total_seconds() < CACHE_DURATION):
            cached = METRICS_CACHE['data']
            low_stock_count = cached['low_stock_count']
            low_stock_critical = cached['low_stock_critical']
            pending_orders_count = cached['pending_orders_count']
            negative_reviews_count = cached['negative_reviews_count']
            negative_reviews_critical = cached['negative_reviews_critical']
            todays_revenue = cached['todays_revenue']
            low_stock_history = cached.get('low_stock_history', [0] * 7)
            revenue_history = cached.get('revenue_history', [0.0] * 7)
            reviews_history = cached.get('reviews_history', [0] * 7)
            orders_history = cached.get('orders_history', [0] * 7)
        else:
            try:
                low_stock_result = AsyncRunner.run_async(call_mcp_tool('get_low_stock_alerts', {
                    'response_format': 'json'
                }))
                if low_stock_result.get('success'):
                    import json
                    low_stock_data = json.loads(low_stock_result['data'])
                    alerts = low_stock_data.get('alerts', [])
                    low_stock_count = len(alerts)
                    low_stock_critical = sum(1 for a in alerts if a.get('severity') == 'critical')
                    low_stock_history = [low_stock_count + i for i in range(7)]
            except Exception:
                pass

            try:
                orders_result = AsyncRunner.run_async(call_mcp_tool('get_orders_amazon', {
                    'days': 1,
                    'limit': 100,
                    'response_format': 'json'
                }))
                if orders_result.get('success'):
                    import json
                    orders_data = json.loads(orders_result['data'])
                    orders = orders_data.get('orders', [])
                    pending_orders_count = sum(1 for o in orders if o.get('status') == 'Pending')
                    for order in orders:
                        try:
                            todays_revenue += float(order.get('total_amount', 0))
                        except (ValueError, TypeError):
                            pass
                    orders_history = [pending_orders_count + i for i in range(7)]
                    revenue_history = [todays_revenue + (i * 10.5) for i in range(7)]
            except Exception:
                pass

            try:
                reviews_result = AsyncRunner.run_async(call_mcp_tool('get_review_alerts', {
                    'days': 7,
                    'include_supplier_flags': True,
                    'response_format': 'json'
                }))
                if reviews_result.get('success'):
                    import json
                    reviews_data = json.loads(reviews_result['data'])
                    negative_reviews_count = reviews_data.get('total_alerts', 0)
                    priority_breakdown = reviews_data.get('priority_breakdown', {})
                    negative_reviews_critical = priority_breakdown.get('critical', 0)
                    reviews_history = [negative_reviews_count + i for i in range(7)]
            except Exception:
                pass

            METRICS_CACHE['data'] = {
                'low_stock_count': low_stock_count,
                'low_stock_critical': low_stock_critical,
                'pending_orders_count': pending_orders_count,
                'negative_reviews_count': negative_reviews_count,
                'negative_reviews_critical': negative_reviews_critical,
                'todays_revenue': todays_revenue,
                'low_stock_history': low_stock_history,
                'revenue_history': revenue_history,
                'reviews_history': reviews_history,
                'orders_history': orders_history
            }
            METRICS_CACHE['timestamp'] = datetime.now()

    def calculate_trend(current, previous, higher_is_good=True):
        if previous == 0:
            return {'direction': 'stable', 'percent': 0}
        change = ((current - previous) / previous) * 100
        if abs(change) < 5:
            return {'direction': 'stable', 'percent': abs(change)}
        if higher_is_good:
            return {'direction': 'up' if change > 0 else 'down', 'percent': abs(change)}
        return {'direction': 'down' if change > 0 else 'up', 'percent': abs(change)}

    def get_relative_time(timestamp):
        try:
            dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
            diff = datetime.now() - dt
            if diff.days > 0:
                return f"{diff.days}d ago"
            hours = diff.seconds // 3600
            if hours > 0:
                return f"{hours}h ago"
            minutes = diff.seconds // 60
            return f"{minutes}m ago"
        except:
            return timestamp

    def get_trend_arrow(direction):
        arrows = {'up': '↑', 'down': '↓', 'stable': '→'}
        return arrows.get(direction, '→')

    low_stock_trend = calculate_trend(low_stock_count, low_stock_history[1] if len(low_stock_history) > 1 else 0, higher_is_good=False)
    revenue_trend = calculate_trend(todays_revenue, revenue_history[1] if len(revenue_history) > 1 else 0, higher_is_good=True)
    reviews_trend = calculate_trend(negative_reviews_count, reviews_history[1] if len(reviews_history) > 1 else 0, higher_is_good=False)
    orders_trend = calculate_trend(pending_orders_count, orders_history[1] if len(orders_history) > 1 else 0, higher_is_good=False)

    low_stock_trend['arrow'] = get_trend_arrow(low_stock_trend['direction'])
    revenue_trend['arrow'] = get_trend_arrow(revenue_trend['direction'])
    reviews_trend['arrow'] = get_trend_arrow(reviews_trend['direction'])
    orders_trend['arrow'] = get_trend_arrow(orders_trend['direction'])

    low_stock_status = 'critical' if low_stock_critical > 0 else ('attention' if low_stock_count > 0 else 'good')
    reviews_status = 'critical' if negative_reviews_critical > 0 else ('attention' if negative_reviews_count > 0 else 'good')
    orders_status = 'attention' if pending_orders_count > 5 else 'good'

    last_updated = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    relative_time = get_relative_time(last_updated)

    try:
        limiter = get_rate_limiter()
        rate_limit_info = limiter.get_rate_limit_info()
    except Exception:
        rate_limit_info = {'limit': 100, 'remaining': 100, 'reset': int(time.time()) + 3600, 'tier': 'FREE'}

    return render_template('dashboard.html',
                         lang=lang,
                         get_text=lambda key: get_text(lang, key),
                         low_stock_count=low_stock_count,
                         low_stock_critical=low_stock_critical,
                         pending_orders_count=pending_orders_count,
                         negative_reviews_count=negative_reviews_count,
                         negative_reviews_critical=negative_reviews_critical,
                         todays_revenue=round(todays_revenue, 2),
                         last_updated=last_updated,
                         relative_time=relative_time,
                         active_tasks=active_tasks,
                         recent_tasks=recent_tasks,
                         low_stock_trend=low_stock_trend,
                         revenue_trend=revenue_trend,
                         reviews_trend=reviews_trend,
                         orders_trend=orders_trend,
                         low_stock_history=low_stock_history,
                         revenue_history=revenue_history,
                         reviews_history=reviews_history,
                         orders_history=orders_history,
                         low_stock_status=low_stock_status,
                         reviews_status=reviews_status,
                         orders_status=orders_status,
                         request=request)

@app.route('/analytics')
@login_required
def analytics():
    """Analytics page with historical data and charts"""
    lang = request.args.get('lang', 'cn')
    date_range = request.args.get('date_range', '30d')

    days_map = {'7d': 7, '30d': 30, '90d': 90}
    days = days_map.get(date_range, 30)
    dates = generate_date_range(days)

    orders_data = None
    low_stock_data = None
    reviews_data = None
    is_mock_data = False

    try:
        orders_result = AsyncRunner.run_async(call_mcp_tool('get_orders_amazon', {
            'days': days,
            'limit': 100,
            'response_format': 'json'
        }))
        if orders_result.get('success'):
            import json
            orders_data = json.loads(orders_result['data'])
    except Exception:
        pass

    try:
        low_stock_result = AsyncRunner.run_async(call_mcp_tool('get_low_stock_alerts', {
            'threshold': 10,
            'platform': 'both',
            'response_format': 'json'
        }))
        if low_stock_result.get('success'):
            import json
            low_stock_data = json.loads(low_stock_result['data'])
    except Exception:
        pass

    try:
        reviews_result = AsyncRunner.run_async(call_mcp_tool('get_review_alerts', {
            'days': days,
            'include_supplier_flags': True,
            'response_format': 'json'
        }))
        if reviews_result.get('success'):
            import json
            reviews_data = json.loads(reviews_result['data'])
    except Exception:
        pass

    if not orders_data and not low_stock_data and not reviews_data:
        is_mock_data = True
        orders_data = generate_mock_historical_data(days)

    orders_aggregated = aggregate_orders_by_date(
        orders_data.get('orders', []) if isinstance(orders_data, dict) else [],
        dates
    ) if orders_data and isinstance(orders_data, dict) else orders_data if orders_data else generate_mock_historical_data(days)

    if is_mock_data:
        orders_aggregated = orders_data

    return render_template('analytics.html',
                         lang=lang,
                         get_text=lambda key: get_text(lang, key),
                         date_range=date_range,
                         orders_data=orders_aggregated,
                         low_stock_data=low_stock_data,
                         reviews_data=reviews_data,
                         is_mock_data=is_mock_data,
                         dates=json.dumps(dates),
                         request=request)

@app.route('/inventory')
@login_required
def inventory():
    lang = request.args.get('lang', 'cn')

    inventory_data = []

    try:
        result = AsyncRunner.run_async(call_mcp_tool('get_low_stock_alerts', {
            'threshold': 10,
            'platform': 'both',
            'response_format': 'json'
        }))

        if result.get('success'):
            import json
            data = json.loads(result['data'])
            inventory_data = data.get('alerts', [])
    except Exception:
        inventory_data = []

    return render_template('inventory.html',
                         lang=lang,
                         get_text=lambda key: get_text(lang, key),
                         inventory_data=inventory_data,
                         request=request)

async def call_mcp_tool(tool_name: str, params: dict) -> dict:
    """Call an MCP tool by name with parameters"""
    try:
        if tool_name == 'get_low_stock_alerts':
            from server import GetLowStockAlertsInput, ResponseFormat, get_low_stock_alerts
            response_format = ResponseFormat(params.get('response_format', 'json'))
            input_params = GetLowStockAlertsInput(
                threshold=params.get('threshold'),
                platform=params.get('platform'),
                response_format=response_format
            )
            result = await get_low_stock_alerts(input_params)
            return {'success': True, 'data': result, 'tool': tool_name}

        elif tool_name == 'get_competitor_prices':
            from server import GetCompetitorPricesInput, ResponseFormat, get_competitor_prices
            response_format = ResponseFormat(params.get('response_format', 'json'))
            input_params = GetCompetitorPricesInput(
                sku=params.get('sku'),
                limit=params.get('limit', 5),
                response_format=response_format
            )
            result = await get_competitor_prices(input_params)
            return {'success': True, 'data': result, 'tool': tool_name}

        elif tool_name == 'get_review_alerts':
            from server import GetReviewAlertsInput, ResponseFormat, get_review_alerts
            response_format = ResponseFormat(params.get('response_format', 'json'))
            input_params = GetReviewAlertsInput(
                days=params.get('days', 7),
                include_supplier_flags=params.get('include_supplier_flags', True),
                response_format=response_format
            )
            result = await get_review_alerts(input_params)
            return {'success': True, 'data': result, 'tool': tool_name}

        elif tool_name == 'get_product_cost_1688':
            from server import GetProductCost1688Input, ResponseFormat, get_product_cost_1688
            response_format = ResponseFormat(params.get('response_format', 'json'))
            input_params = GetProductCost1688Input(
                sku=params.get('sku'),
                response_format=response_format
            )
            result = await get_product_cost_1688(input_params)
            return {'success': True, 'data': result, 'tool': tool_name}

        elif tool_name == 'calculate_amazon_price':
            from server import CalculateAmazonPriceInput, ResponseFormat, calculate_amazon_price
            response_format = ResponseFormat(params.get('response_format', 'json'))
            input_params = CalculateAmazonPriceInput(
                sku=params.get('sku'),
                cost_cny=params.get('cost_cny'),
                target_margin_percent=params.get('target_margin_percent', 25.0),
                shipping_cost_usd=params.get('shipping_cost_usd', 2.0),
                response_format=response_format
            )
            result = await calculate_amazon_price(input_params)
            return {'success': True, 'data': result, 'tool': tool_name}

        elif tool_name == 'sync_inventory':
            from server import ResponseFormat, SyncInventoryInput, sync_inventory
            response_format = ResponseFormat(params.get('response_format', 'json'))
            input_params = SyncInventoryInput(
                sku=params.get('sku'),
                response_format=response_format
            )
            result = await sync_inventory(input_params)
            return {'success': True, 'data': result, 'tool': tool_name}

        elif tool_name == 'get_orders_amazon':
            from server import GetOrdersAmazonInput, ResponseFormat, get_orders_amazon
            response_format = ResponseFormat(params.get('response_format', 'json'))
            input_params = GetOrdersAmazonInput(
                days=params.get('days', 7),
                status=params.get('status'),
                limit=params.get('limit', 50),
                response_format=response_format
            )
            result = await get_orders_amazon(input_params)
            return {'success': True, 'data': result, 'tool': tool_name}

        elif tool_name == 'get_product_reviews':
            from server import GetProductReviewsInput, ResponseFormat, get_product_reviews
            response_format = ResponseFormat(params.get('response_format', 'json'))
            input_params = GetProductReviewsInput(
                sku=params.get('sku'),
                days=params.get('days', 30),
                min_rating=params.get('min_rating'),
                max_rating=params.get('max_rating'),
                limit=params.get('limit', 20),
                response_format=response_format
            )
            result = await get_product_reviews(input_params)
            return {'success': True, 'data': result, 'tool': tool_name}

        elif tool_name == 'get_negative_reviews':
            from server import GetNegativeReviewsInput, ResponseFormat, get_negative_reviews
            response_format = ResponseFormat(params.get('response_format', 'json'))
            input_params = GetNegativeReviewsInput(
                sku=params.get('sku'),
                days=params.get('days', 7),
                severity=params.get('severity', 'all'),
                response_format=response_format
            )
            result = await get_negative_reviews(input_params)
            return {'success': True, 'data': result, 'tool': tool_name}

        elif tool_name == 'sync_price':
            from server import ResponseFormat, SyncPriceInput, sync_price
            response_format = ResponseFormat(params.get('response_format', 'json'))
            input_params = SyncPriceInput(
                sku=params.get('sku'),
                target_margin_percent=params.get('target_margin_percent', 25.0),
                shipping_cost_usd=params.get('shipping_cost_usd', 2.0),
                response_format=response_format
            )
            result = await sync_price(input_params)
            return {'success': True, 'data': result, 'tool': tool_name}

        elif tool_name == 'update_amazon_price':
            from server import UpdateAmazonPriceInput, update_amazon_price
            input_params = UpdateAmazonPriceInput(
                sku=params.get('sku'),
                new_price=params.get('new_price'),
                currency=params.get('currency', 'USD')
            )
            result = await update_amazon_price(input_params)
            return {'success': True, 'data': result, 'tool': tool_name}

        elif tool_name == 'get_inventory_1688':
            from server import GetInventory1688Input, ResponseFormat, get_inventory_1688
            response_format = ResponseFormat(params.get('response_format', 'json'))
            input_params = GetInventory1688Input(
                sku=params.get('sku'),
                response_format=response_format
            )
            result = await get_inventory_1688(input_params)
            return {'success': True, 'data': result, 'tool': tool_name}

        elif tool_name == 'calculate_true_profit':
            from server import CalculateTrueProfitInput, ResponseFormat, calculate_true_profit
            response_format = ResponseFormat(params.get('response_format', 'json'))
            input_params = CalculateTrueProfitInput(
                sku=params.get('sku'),
                selling_price_usd=params.get('selling_price_usd'),
                cost_cny=params.get('cost_cny'),
                shipping_to_amazon_usd=params.get('shipping_to_amazon_usd', 2.0),
                amazon_referral_fee_percent=params.get('amazon_referral_fee_percent'),
                fba_fee_usd=params.get('fba_fee_usd', 3.5),
                monthly_storage_fee_usd=params.get('monthly_storage_fee_usd', 0.3),
                advertising_acos_percent=params.get('advertising_acos_percent', 20.0),
                payment_processing_fee_percent=params.get('payment_processing_fee_percent', 2.9),
                return_rate_percent=params.get('return_rate_percent', 5.0),
                customs_duty_percent=params.get('customs_duty_percent', 3.0),
                overhead_percent=params.get('overhead_percent', 8.0),
                response_format=response_format
            )
            result = await calculate_true_profit(input_params)
            return {'success': True, 'data': result, 'tool': tool_name}

        elif tool_name == 'save_product_profile':
            from server import ResponseFormat, SaveProductProfileInput, save_product_profile_tool
            response_format = ResponseFormat(params.get('response_format', 'json'))
            input_params = SaveProductProfileInput(
                sku=params.get('sku'),
                product_name=params.get('product_name'),
                cost_cny=params.get('cost_cny'),
                shipping_to_amazon_usd=params.get('shipping_to_amazon_usd'),
                amazon_referral_fee_percent=params.get('amazon_referral_fee_percent'),
                fba_fee_usd=params.get('fba_fee_usd'),
                monthly_storage_fee_usd=params.get('monthly_storage_fee_usd'),
                advertising_acos_percent=params.get('advertising_acos_percent'),
                payment_processing_fee_percent=params.get('payment_processing_fee_percent'),
                return_rate_percent=params.get('return_rate_percent'),
                customs_duty_percent=params.get('customs_duty_percent'),
                overhead_percent=params.get('overhead_percent'),
                notes=params.get('notes'),
                response_format=response_format
            )
            result = await save_product_profile_tool(input_params)
            return {'success': True, 'data': result, 'tool': tool_name}

        elif tool_name == 'get_product_profile':
            from server import GetProductProfileInput, ResponseFormat, get_product_profile_tool
            response_format = ResponseFormat(params.get('response_format', 'json'))
            input_params = GetProductProfileInput(
                sku=params.get('sku'),
                response_format=response_format
            )
            result = await get_product_profile_tool(input_params)
            return {'success': True, 'data': result, 'tool': tool_name}

        elif tool_name == 'list_all_products':
            from server import GetStaleProductsInput, ResponseFormat, list_all_products
            response_format = ResponseFormat(params.get('response_format', 'json'))
            input_params = GetStaleProductsInput(
                hours=params.get('hours', 24),
                response_format=response_format
            )
            result = await list_all_products(input_params)
            return {'success': True, 'data': result, 'tool': tool_name}

        elif tool_name == 'get_stale_products':
            from server import GetStaleProductsInput, ResponseFormat, get_stale_products_tool
            response_format = ResponseFormat(params.get('response_format', 'json'))
            input_params = GetStaleProductsInput(
                hours=params.get('hours', 24),
                response_format=response_format
            )
            result = await get_stale_products_tool(input_params)
            return {'success': True, 'data': result, 'tool': tool_name}

        elif tool_name == 'update_fulfillment_amazon':
            from server import UpdateFulfillmentAmazonInput, update_fulfillment_amazon
            input_params = UpdateFulfillmentAmazonInput(
                order_id=params.get('order_id'),
                status=params.get('status')
            )
            result = await update_fulfillment_amazon(input_params)
            return {'success': True, 'data': result, 'tool': tool_name}

        elif tool_name == 'get_license_info':
            from server import get_license_info
            result = await get_license_info()
            return {'success': True, 'data': result, 'tool': tool_name}

        else:
            return {'success': False, 'error': f'Tool "{tool_name}" not found', 'tool': tool_name}

    except Exception as e:
        return {'success': False, 'error': str(e), 'tool': tool_name, 'traceback': traceback.format_exc()}

@app.route('/')
def index():
    """Home page"""
    lang = request.args.get('lang', 'cn')
    return render_template('index.html', lang=lang, get_text=lambda key: get_text(lang, key), request=request)

@app.route('/profit', methods=['GET', 'POST'])
def profit():
    """Profit Calculator page"""
    lang = request.args.get('lang', 'cn')

    if request.method == 'POST':
        sku = request.form.get('sku', 'SKU-12345')
        selling_price = float(request.form.get('selling_price', 29.99))
        cost_cny = float(request.form.get('cost_cny', 35.0))

        result = calculate_true_profit_simple(
            selling_price_usd=selling_price,
            cost_cny=cost_cny
        )

        return render_template('profit.html',
                             lang=lang,
                             get_text=lambda key: get_text(lang, key),
                             result=result,
                             sku=sku,
                             selling_price=selling_price,
                             request=request)

    return render_template('profit.html',
                         lang=lang,
                         get_text=lambda key: get_text(lang, key),
                         result=None,
                         request=request)

def calculate_true_profit_simple(selling_price_usd: float, cost_cny: float):
    """Simple version of true profit calculation for web UI"""
    exchange_rate = 7.2
    cost_usd = cost_cny / exchange_rate

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

@app.route('/inventory-alerts')
def inventory_alerts():
    """Inventory Alerts page"""
    lang = request.args.get('lang', 'cn')
    threshold = request.args.get('threshold', 10, type=int)
    platform = request.args.get('platform', 'all')
    risk_threshold = request.args.get('risk_threshold', 14, type=int)

    platform_param = 'both' if platform == 'all' else platform

    filtered_alerts = []
    predictions = []
    health_score = None

    try:
        from analytics_engine import analyzer

        risk_products = analyzer.identify_risk_products(threshold_days=risk_threshold)

        for rp in risk_products:
            dos = analyzer.calculate_days_of_supply(rp['sku'])
            reorder = analyzer.calculate_reorder_quantity(
                rp['sku'],
                sales_velocity=dos.get('avg_daily_demand', 0),
                lead_time=14,
                target_days=30
            )
            predictions.append({
                'sku': rp['sku'],
                'product_name': rp.get('product_name', 'Unknown'),
                'current_stock': rp.get('current_stock', 0),
                'days_until_stockout': rp.get('days_until_stockout', float('inf')),
                'risk_level': rp.get('risk_level', 'low'),
                'predicted_stockout_date': rp.get('predicted_stockout_date'),
                'reorder_quantity': reorder.get('reorder_quantity', 0),
                'reorder_urgency': reorder.get('urgency', 'none'),
                'days_of_supply': dos.get('days_of_supply', float('inf'))
            })

        health_score = analyzer.get_inventory_health_score()

    except Exception:
        predictions = []

    try:
        result = AsyncRunner.run_async(call_mcp_tool('get_low_stock_alerts', {
            'threshold': threshold,
            'platform': platform_param,
            'response_format': 'json'
        }))

        if result.get('success'):
            import json
            data = json.loads(result['data'])
            raw_alerts = data.get('alerts', [])

            for alert in raw_alerts:
                if 'error' in alert:
                    continue

                current_stock = alert.get('current_stock', 0)
                alert_threshold = alert.get('threshold', threshold)
                shortage = alert.get('shortage', alert_threshold - current_stock)

                if shortage >= 15:
                    severity = 'critical'
                elif shortage >= 5:
                    severity = 'warning'
                else:
                    severity = 'low'

                filtered_alerts.append({
                    'product_name': alert.get('product_name', 'Unknown'),
                    'sku': alert.get('sku', 'N/A'),
                    'platform': alert.get('platform', 'Unknown'),
                    'current_stock': current_stock,
                    'threshold': alert_threshold,
                    'shortage': shortage,
                    'severity': severity
                })

            filtered_alerts.sort(key=lambda x: (
                0 if x['severity'] == 'critical' else 1 if x['severity'] == 'warning' else 2,
                -x['shortage']
            ))

    except Exception:
        filtered_alerts = []

    avg_days_supply = 0
    if predictions:
        finite_dos = [p['days_of_supply'] for p in predictions if p['days_of_supply'] != float('inf')]
        if finite_dos:
            avg_days_supply = sum(finite_dos) / len(finite_dos)

    return render_template('inventory.html',
                         lang=lang,
                         get_text=lambda key: get_text(lang, key),
                         alerts=filtered_alerts,
                         predictions=predictions,
                         health_score=health_score,
                         avg_days_supply=round(avg_days_supply, 1),
                         threshold=threshold,
                         platform=platform,
                         risk_threshold=risk_threshold,
                         request=request)

@app.route('/competitor', methods=['GET', 'POST'])
@login_required
def competitor():
    """Competitor Price Analysis page"""
    lang = request.args.get('lang', 'cn')

    results = []
    search_term = request.args.get('asin_or_keyword', '')
    max_results = request.args.get('max_results', 5, type=int)
    price_range = None

    if search_term:
        try:
            result = AsyncRunner.run_async(call_mcp_tool('get_competitor_prices', {
                'sku': search_term,
                'limit': max_results,
                'response_format': 'json'
            }))

            if result.get('success'):
                import json
                data = json.loads(result['data'])
                results = data.get('competitors', [])
                if results and 'price_range' in data:
                    price_range = data['price_range']
        except Exception:
            results = []

    return render_template('competitor.html',
                         lang=lang,
                         get_text=lambda key: get_text(lang, key),
                         results=results,
                         search_term=search_term,
                         max_results=max_results,
                         price_range=price_range,
                         request=request)

@app.route('/price-optimizer')
@login_required
@role_required('manager')
def price_optimizer():
    """AI-Powered Price Optimization page"""
    lang = request.args.get('lang', 'cn')
    sku = request.args.get('sku', '')
    asin = request.args.get('asin', '')
    strategy = request.args.get('strategy', 'balanced')

    recommendation = None
    competitor_analysis = None
    threats = []

    if sku:
        try:
            from price_optimizer import optimizer
            recommendation = optimizer.get_price_recommendation(sku, strategy=strategy)
            asin_param = sku.replace('SKU', 'ASIN')
            competitor_analysis = optimizer.analyze_competition(asin_param)
            threats = optimizer.detect_competitive_threats(
                asin_param,
                current_price=recommendation.get('current_price') if recommendation else None
            )
        except Exception:
            pass

    return render_template('price_optimizer.html',
                         lang=lang,
                         get_text=lambda key: get_text(lang, key),
                         sku=sku,
                         asin=asin or sku.replace('SKU', 'ASIN'),
                         strategy=strategy,
                         recommendation=recommendation,
                         competitor_analysis=competitor_analysis,
                         threats=threats,
                         request=request)

@app.route('/reviews')
@login_required
def reviews():
    """Review Alerts page"""
    lang = request.args.get('lang', 'cn')
    days_back = request.args.get('days_back', 7, type=int)
    rating_threshold = request.args.get('rating_threshold', 0, type=int)
    asin = request.args.get('asin', '')

    alerts = []
    total_alerts = 0
    priority_breakdown = {'critical': 0, 'high': 0, 'medium': 0}

    try:
        result = AsyncRunner.run_async(call_mcp_tool('get_review_alerts', {
            'days': days_back,
            'include_supplier_flags': True,
            'response_format': 'json'
        }))

        if result.get('success'):
            import json
            data = json.loads(result['data'])
            alerts = data.get('alerts', [])
            total_alerts = data.get('total_alerts', 0)
            priority_breakdown = data.get('priority_breakdown', {'critical': 0, 'high': 0, 'medium': 0})

            if rating_threshold > 0:
                alerts = [a for a in alerts if a.get('rating', 5) <= rating_threshold]
                total_alerts = len(alerts)
    except Exception:
        alerts = []

    return render_template('reviews.html',
                         lang=lang,
                         get_text=lambda key: get_text(lang, key),
                         alerts=alerts,
                         total_alerts=total_alerts,
                         priority_breakdown=priority_breakdown,
                         days_back=days_back,
                         rating_threshold=rating_threshold,
                         request=request)

@app.route('/offline')
def offline():
    """Offline fallback page"""
    lang = request.args.get('lang', 'cn')
    return render_template('offline.html', lang=lang, get_text=lambda key: get_text(lang, key), request=request)

@app.route('/quickstart')
def quickstart():
    """Developer Quick Start Guide page"""
    lang = request.args.get('lang', 'cn')
    return render_template('quickstart.html', lang=lang, get_text=lambda key: get_text(lang, key), request=request)

@app.route('/changelog')
def changelog_page():
    """Changelog page"""
    lang = request.args.get('lang', 'cn')
    versions = [
        {
            'version': '1.5.0',
            'date': '2024-01-15',
            'is_latest': True,
            'breaking_changes': [],
            'features': [
                'Added real-time inventory sync between 1688 and Amazon',
                'New competitor price tracking with historical data',
                'Automated review response suggestions using AI',
                'Support for scheduled task management',
            ],
            'improvements': [
                'Improved API response times by 40%',
                'Enhanced inventory forecasting accuracy',
                'Better error handling and logging',
            ],
            'bug_fixes': [
                'Fixed issue with API rate limiting on bulk operations',
                'Corrected currency conversion for CNY to USD',
            ]
        },
        {
            'version': '1.4.0',
            'date': '2023-12-20',
            'is_latest': False,
            'breaking_changes': [],
            'features': [
                'New profit margin calculator with tax support',
                'Added Webhook notifications for critical alerts',
                'Support for multiple warehouse inventory tracking',
            ],
            'improvements': [
                'Updated 1688 API integration to v3.0',
                'Enhanced data caching for better performance',
            ],
            'bug_fixes': [
                'Fixed timezone issues in scheduled reports',
            ]
        },
        {
            'version': '1.3.0',
            'date': '2023-11-15',
            'is_latest': False,
            'breaking_changes': [
                'Renamed API endpoint /api/inventory to /api/inventory/list',
            ],
            'features': [
                'New low stock alert system with configurable thresholds',
                'Added review sentiment analysis',
            ],
            'improvements': [
                'UI/UX improvements across all pages',
            ],
            'bug_fixes': [
                'Fixed session timeout issues',
            ]
        },
        {
            'version': '1.2.0',
            'date': '2023-10-01',
            'is_latest': False,
            'breaking_changes': [],
            'features': [
                'Initial MCP Server integration',
                'Basic inventory management',
                'Order tracking from Amazon SP-API',
            ],
            'improvements': [],
            'bug_fixes': []
        }
    ]
    return render_template('changelog.html', lang=lang, get_text=lambda key: get_text(lang, key), versions=versions, request=request)

@app.route('/api/changelog')
def api_changelog():
    """API Changelog endpoint - returns JSON with version history"""
    versions = [
        {
            'version': '1.5.0',
            'date': '2024-01-15',
            'breaking_changes': [],
            'features': [
                'Added real-time inventory sync between 1688 and Amazon',
                'New competitor price tracking with historical data',
                'Automated review response suggestions using AI',
                'Support for scheduled task management',
            ],
            'improvements': [
                'Improved API response times by 40%',
                'Enhanced inventory forecasting accuracy',
                'Better error handling and logging',
            ],
            'bug_fixes': [
                'Fixed issue with API rate limiting on bulk operations',
                'Corrected currency conversion for CNY to USD',
            ]
        },
        {
            'version': '1.4.0',
            'date': '2023-12-20',
            'breaking_changes': [],
            'features': [
                'New profit margin calculator with tax support',
                'Added Webhook notifications for critical alerts',
                'Support for multiple warehouse inventory tracking',
            ],
            'improvements': [
                'Updated 1688 API integration to v3.0',
                'Enhanced data caching for better performance',
            ],
            'bug_fixes': [
                'Fixed timezone issues in scheduled reports',
            ]
        },
        {
            'version': '1.3.0',
            'date': '2023-11-15',
            'breaking_changes': [
                'Renamed API endpoint /api/inventory to /api/inventory/list',
            ],
            'features': [
                'New low stock alert system with configurable thresholds',
                'Added review sentiment analysis',
            ],
            'improvements': [
                'UI/UX improvements across all pages',
            ],
            'bug_fixes': [
                'Fixed session timeout issues',
            ]
        },
        {
            'version': '1.2.0',
            'date': '2023-10-01',
            'breaking_changes': [],
            'features': [
                'Initial MCP Server integration',
                'Basic inventory management',
                'Order tracking from Amazon SP-API',
            ],
            'improvements': [],
            'bug_fixes': []
        }
    ]
    return jsonify({
        'success': True,
        'versions': versions,
        'current_version': '1.5.0',
        'latest': '1.5.0'
    })

def offline():
    """Offline fallback page"""
    lang = request.args.get('lang', 'cn')
    return render_template('offline.html', lang=lang, get_text=lambda key: get_text(lang, key), request=request)

@app.route('/tasks')
@login_required
@role_required('manager')
def tasks():
    """Task Queue page"""
    lang = request.args.get('lang', 'cn')
    status_filter = request.args.get('status', '')
    limit = request.args.get('limit', 50, type=int)

    if status_filter:
        all_tasks = get_all_tasks(status=status_filter, limit=limit)
    else:
        all_tasks = get_all_tasks(limit=limit)

    active_count = len(get_active_tasks())
    pending_count = len(get_all_tasks(status='pending'))
    running_count = len(get_all_tasks(status='running'))
    completed_count = len(get_all_tasks(status='completed'))
    failed_count = len(get_all_tasks(status='failed'))

    return render_template('tasks.html',
                         lang=lang,
                         get_text=lambda key: get_text(lang, key),
                         tasks=all_tasks,
                         active_count=active_count,
                         pending_count=pending_count,
                         running_count=running_count,
                         completed_count=completed_count,
                         failed_count=failed_count,
                         status_filter=status_filter,
                         request=request)

def calculate_trend(current: float, previous: float, higher_is_good: bool = True) -> dict:
    """Calculate trend direction, percentage, and whether it's positive"""
    if previous == 0:
        if current == 0:
            return {'direction': 'stable', 'percentage': 0, 'is_positive': True}
        return {'direction': 'up', 'percentage': 100, 'is_positive': higher_is_good}

    change_pct = ((current - previous) / previous) * 100

    if abs(change_pct) < 5:
        return {'direction': 'stable', 'percentage': abs(round(change_pct, 1)), 'is_positive': True}

    direction = 'up' if change_pct > 0 else 'down'
    is_positive = (change_pct > 0) == higher_is_good

    return {
        'direction': direction,
        'percentage': abs(round(change_pct, 1)),
        'is_positive': is_positive
    }

def get_trend_arrow(direction: str) -> str:
    """Get arrow symbol for trend direction"""
    arrows = {'up': '↑', 'down': '↓', 'stable': '→'}
    return arrows.get(direction, '→')

METRICS_CACHE = {
    'data': None,
    'timestamp': None,
}
METRICS_CACHE_LOCK = threading.Lock()
CACHE_DURATION = 60

@app.route('/dashboard-full')
def dashboard_full():
    """Dashboard page with key metrics"""
    lang = request.args.get('lang', 'cn')

    low_stock_count = 0
    low_stock_critical = 0
    pending_orders_count = 0
    negative_reviews_count = 0
    negative_reviews_critical = 0
    todays_revenue = 0.0

    low_stock_history = [0] * 7
    revenue_history = [0.0] * 7
    reviews_history = [0] * 7
    orders_history = [0] * 7

    active_tasks = get_active_tasks()
    recent_tasks = get_all_tasks(limit=5)

    with METRICS_CACHE_LOCK:
        if (METRICS_CACHE['data'] and METRICS_CACHE['timestamp'] and
            (datetime.now() - METRICS_CACHE['timestamp']).total_seconds() < CACHE_DURATION):
            cached = METRICS_CACHE['data']
            low_stock_count = cached['low_stock_count']
            low_stock_critical = cached['low_stock_critical']
            pending_orders_count = cached['pending_orders_count']
            negative_reviews_count = cached['negative_reviews_count']
            negative_reviews_critical = cached['negative_reviews_critical']
            todays_revenue = cached['todays_revenue']
            low_stock_history = cached.get('low_stock_history', [0] * 7)
            revenue_history = cached.get('revenue_history', [0.0] * 7)
            reviews_history = cached.get('reviews_history', [0] * 7)
            orders_history = cached.get('orders_history', [0] * 7)
        else:
            try:
                low_stock_result = AsyncRunner.run_async(call_mcp_tool('get_low_stock_alerts', {
                    'response_format': 'json'
                }))
                if low_stock_result.get('success'):
                    import json
                    low_stock_data = json.loads(low_stock_result['data'])
                    low_stock_count = low_stock_data.get('total_alerts', 0)
                    low_stock_critical = low_stock_data.get('critical_count', 0)
                    low_stock_history = [low_stock_count + i for i in range(7)]
            except Exception:
                pass

            try:
                orders_result = AsyncRunner.run_async(call_mcp_tool('get_orders_amazon', {
                    'days': 1,
                    'response_format': 'json'
                }))
                if orders_result.get('success'):
                    import json
                    orders_data = json.loads(orders_result['data'])
                    orders = orders_data.get('orders', [])
                    pending_orders_count = sum(1 for o in orders if o.get('status') == 'Pending')
                    for order in orders:
                        try:
                            todays_revenue += float(order.get('total_amount', 0))
                        except (ValueError, TypeError):
                            pass
                    orders_history = [pending_orders_count + i for i in range(7)]
                    revenue_history = [todays_revenue + (i * 10.5) for i in range(7)]
            except Exception:
                pass

            try:
                reviews_result = AsyncRunner.run_async(call_mcp_tool('get_review_alerts', {
                    'days': 7,
                    'include_supplier_flags': True,
                    'response_format': 'json'
                }))
                if reviews_result.get('success'):
                    import json
                    reviews_data = json.loads(reviews_result['data'])
                    negative_reviews_count = reviews_data.get('total_alerts', 0)
                    priority_breakdown = reviews_data.get('priority_breakdown', {})
                    negative_reviews_critical = priority_breakdown.get('critical', 0)
                    reviews_history = [negative_reviews_count + i for i in range(7)]
            except Exception:
                pass

            METRICS_CACHE['data'] = {
                'low_stock_count': low_stock_count,
                'low_stock_critical': low_stock_critical,
                'pending_orders_count': pending_orders_count,
                'negative_reviews_count': negative_reviews_count,
                'negative_reviews_critical': negative_reviews_critical,
                'todays_revenue': todays_revenue,
                'low_stock_history': low_stock_history,
                'revenue_history': revenue_history,
                'reviews_history': reviews_history,
                'orders_history': orders_history
            }
            METRICS_CACHE['timestamp'] = datetime.now()

    low_stock_trend = calculate_trend(low_stock_count, low_stock_history[1] if len(low_stock_history) > 1 else 0, higher_is_good=False)
    revenue_trend = calculate_trend(todays_revenue, revenue_history[1] if len(revenue_history) > 1 else 0, higher_is_good=True)
    reviews_trend = calculate_trend(negative_reviews_count, reviews_history[1] if len(reviews_history) > 1 else 0, higher_is_good=False)
    orders_trend = calculate_trend(pending_orders_count, orders_history[1] if len(orders_history) > 1 else 0, higher_is_good=False)

    low_stock_trend['arrow'] = get_trend_arrow(low_stock_trend['direction'])
    revenue_trend['arrow'] = get_trend_arrow(revenue_trend['direction'])
    reviews_trend['arrow'] = get_trend_arrow(reviews_trend['direction'])
    orders_trend['arrow'] = get_trend_arrow(orders_trend['direction'])

    low_stock_status = 'critical' if low_stock_critical > 0 else ('attention' if low_stock_count > 0 else 'good')
    reviews_status = 'critical' if negative_reviews_critical > 0 else ('attention' if negative_reviews_count > 0 else 'good')
    orders_status = 'attention' if pending_orders_count > 5 else 'good'

    last_updated = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    relative_time = get_relative_time(last_updated)

    try:
        limiter = get_rate_limiter()
        rate_limit_info = limiter.get_rate_limit_info()
    except Exception:
        rate_limit_info = {'limit': 100, 'remaining': 100, 'reset': int(time.time()) + 3600, 'tier': 'FREE'}

    return render_template('dashboard.html',
                         lang=lang,
                         get_text=lambda key: get_text(lang, key),
                         low_stock_count=low_stock_count,
                         low_stock_critical=low_stock_critical,
                         pending_orders_count=pending_orders_count,
                         negative_reviews_count=negative_reviews_count,
                         negative_reviews_critical=negative_reviews_critical,
                         todays_revenue=round(todays_revenue, 2),
                         last_updated=last_updated,
                         relative_time=relative_time,
                         active_tasks=active_tasks,
                         recent_tasks=recent_tasks,
                         low_stock_trend=low_stock_trend,
                         revenue_trend=revenue_trend,
                         reviews_trend=reviews_trend,
                         orders_trend=orders_trend,
                         low_stock_history=low_stock_history,
                         revenue_history=revenue_history,
                         reviews_history=reviews_history,
                         orders_history=orders_history,
                         low_stock_status=low_stock_status,
                         reviews_status=reviews_status,
                         orders_status=orders_status,
                         rate_limit_info=rate_limit_info,
                         request=request)

@app.route('/analytics-full')
def analytics_full():
    """Analytics page with historical data and charts"""
    lang = request.args.get('lang', 'cn')
    date_range = request.args.get('date_range', '30d')

    days_map = {'7d': 7, '30d': 30, '90d': 90}
    days = days_map.get(date_range, 30)
    dates = generate_date_range(days)

    orders_data = None
    low_stock_data = None
    reviews_data = None
    is_mock_data = False

    try:
        orders_result = AsyncRunner.run_async(call_mcp_tool('get_orders_amazon', {
            'days': days,
            'response_format': 'json'
        }))
        if orders_result.get('success'):
            import json
            orders_raw = json.loads(orders_result['data'])
            orders_list = orders_raw.get('orders', [])
            if orders_list:
                orders_data = aggregate_orders_by_date(orders_list, dates)
    except Exception:
        pass

    try:
        low_stock_result = AsyncRunner.run_async(call_mcp_tool('get_low_stock_alerts', {
            'response_format': 'json'
        }))
        if low_stock_result.get('success'):
            import json
            low_stock_raw = json.loads(low_stock_result['data'])
            alerts_list = low_stock_raw.get('alerts', [])
            if alerts_list:
                low_stock_data = aggregate_low_stock_by_date(alerts_list, dates)
    except Exception:
        pass

    try:
        reviews_result = AsyncRunner.run_async(call_mcp_tool('get_review_alerts', {
            'days': days,
            'include_supplier_flags': True,
            'response_format': 'json'
        }))
        if reviews_result.get('success'):
            import json
            reviews_raw = json.loads(reviews_result['data'])
            alerts_list = reviews_raw.get('alerts', [])
            if alerts_list:
                reviews_data = aggregate_reviews_by_date(alerts_list, dates)
    except Exception:
        pass

    if not orders_data and not reviews_data:
        mock_data = generate_mock_historical_data(days)
        is_mock_data = True
        orders_data = {
            'labels': mock_data['labels'],
            'order_counts': mock_data['order_counts'],
            'revenues': mock_data['revenues'],
            'status_counts': mock_data['status_distribution'],
            'total_orders': mock_data['total_orders'],
            'total_revenue': mock_data['total_revenue'],
            'avg_daily_orders': mock_data['avg_daily_orders'],
            'avg_order_value': mock_data['avg_order_value']
        }
        reviews_data = {
            'labels': mock_data['labels'],
            'rating_counts': mock_data['rating_distribution'],
            'total_reviews': sum(mock_data['rating_distribution'].values()),
            'avg_rating': round(sum(r * c for r, c in mock_data['rating_distribution'].items()) / sum(mock_data['rating_distribution'].values()), 1)
        }
        low_stock_data = {
            'labels': dates,
            'critical': [random.randint(0, 3) for _ in dates],
            'warning': [random.randint(2, 8) for _ in dates],
            'total_critical': random.randint(5, 15),
            'total_warning': random.randint(15, 30)
        }

    orders_chart = {
        'labels': orders_data['labels'],
        'datasets': [
            {
                'label': get_text(lang, 'analytics_orders_trend'),
                'data': orders_data['order_counts'],
                'borderColor': 'rgb(75, 192, 192)',
                'backgroundColor': 'rgba(75, 192, 192, 0.2)',
                'fill': True
            }
        ]
    }

    revenue_chart = {
        'labels': orders_data['labels'],
        'datasets': [
            {
                'label': get_text(lang, 'analytics_revenue_trend'),
                'data': orders_data['revenues'],
                'borderColor': 'rgb(54, 162, 235)',
                'backgroundColor': 'rgba(54, 162, 235, 0.2)',
                'fill': True
            }
        ]
    }

    status_labels = list(orders_data['status_counts'].keys())
    status_values = list(orders_data['status_counts'].values())
    order_status_chart = {
        'labels': status_labels,
        'datasets': [{
            'data': status_values,
            'backgroundColor': [
                'rgb(255, 99, 132)',
                'rgb(255, 159, 64)',
                'rgb(54, 162, 235)',
                'rgb(255, 205, 86)'
            ]
        }]
    }

    rating_labels = [f'{i} ' + '\u2605' for i in range(5, 0, -1)]
    rating_values = [reviews_data['rating_counts'].get(i, 0) for i in range(5, 0, -1)]
    reviews_chart = {
        'labels': rating_labels,
        'datasets': [{
            'label': get_text(lang, 'analytics_reviews_by_rating'),
            'data': rating_values,
            'backgroundColor': [
                'rgba(255, 99, 132, 0.7)',
                'rgba(255, 159, 64, 0.7)',
                'rgba(255, 205, 86, 0.7)',
                'rgba(75, 192, 192, 0.7)',
                'rgba(54, 162, 235, 0.7)'
            ],
            'borderWidth': 1
        }]
    }

    summary = {
        'total_orders': orders_data.get('total_orders', 0),
        'total_revenue': orders_data.get('total_revenue', 0),
        'avg_daily_orders': orders_data.get('avg_daily_orders', 0),
        'avg_order_value': orders_data.get('avg_order_value', 0),
        'low_stock_critical': low_stock_data.get('total_critical', 0) if low_stock_data else 0,
        'low_stock_warning': low_stock_data.get('total_warning', 0) if low_stock_data else 0,
        'total_reviews': reviews_data.get('total_reviews', 0) if reviews_data else 0,
        'avg_rating': reviews_data.get('avg_rating', 0) if reviews_data else 0
    }

    return render_template('analytics.html',
                         lang=lang,
                         get_text=lambda key: get_text(lang, key),
                         date_range=date_range,
                         days=days,
                         orders_data=orders_data,
                         low_stock_data=low_stock_data,
                         reviews_data=reviews_data,
                         orders_chart=orders_chart,
                         revenue_chart=revenue_chart,
                         order_status_chart=order_status_chart,
                         reviews_chart=reviews_chart,
                         summary=summary,
                         is_mock_data=is_mock_data,
                         request=request)

def get_relative_time(timestamp_str: str) -> str:
    """Convert timestamp to relative time string"""
    try:
        dt = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
        diff = datetime.now() - dt
        seconds = diff.total_seconds()
        if seconds < 60:
            return 'just now'
        minutes = int(seconds / 60)
        if minutes < 60:
            return f'{minutes}m ago'
        hours = int(minutes / 60)
        if hours < 24:
            return f'{hours}h ago'
        days = int(hours / 24)
        return f'{days}d ago'
    except:
        return 'unknown'

@app.route('/api/profit', methods=['POST'])
def api_profit():
    """API endpoint for profit calculation"""
    data = request.json
    result = calculate_true_profit_simple(
        selling_price_usd=data.get('selling_price', 29.99),
        cost_cny=data.get('cost_cny', 35.0)
    )
    return jsonify(result)

@app.route('/api/tools', methods=['GET'])
@rate_limit('BASIC')
def api_list_tools():
    """GET /api/tools - List all available MCP tools with descriptions
    ---
    tags:
      - Tools
    parameters:
      - name: lang
        in: query
        type: string
        required: false
        default: en
        description: Language for response messages (en or cn)
    responses:
      200:
        description: List of all available MCP tools
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            message:
              type: string
            total_tools:
              type: integer
            tools:
              type: array
              items:
                type: object
                properties:
                  name:
                    type: string
                    description: Tool name identifier
                  description:
                    type: string
                    description: Tool description
                  required_parameters:
                    type: array
                    items:
                      type: string
                    description: List of required parameter names
                  optional_parameters:
                    type: array
                    items:
                      type: string
                    description: List of optional parameter names
                  parameter_details:
                    type: object
                    description: Detailed schema for all parameters
    """
    lang = request.args.get('lang', 'en')

    tools_list = []
    for name, tool in TOOL_REGISTRY.items():
        params = tool['params_schema']
        required = [p for p, v in params.items() if v.get('required', False)]
        optional = [p for p, v in params.items() if not v.get('required', False)]

        tools_list.append({
            'name': name,
            'description': tool['description'],
            'required_parameters': required,
            'optional_parameters': optional,
            'parameter_details': params
        })

    response_data = {
        'success': True,
        'message': get_text(lang, 'api_tools_list'),
        'total_tools': len(tools_list),
        'tools': tools_list
    }

    etag = generate_etag(response_data)
    if request.headers.get('If-None-Match') == etag:
        return '', 304

    response = make_response(jsonify(response_data))
    response.headers['ETag'] = etag
    return add_etag_and_cache(response, max_age=300)

@app.route('/api/tools/<tool_name>', methods=['GET'])
def api_get_tool_info(tool_name: str):
    """GET /api/tools/<tool_name> - Get tool info and parameters
    ---
    tags:
      - Tools
    parameters:
      - name: tool_name
        in: path
        type: string
        required: true
        description: The name of the MCP tool
      - name: lang
        in: query
        type: string
        required: false
        default: en
        description: Language for response messages (en or cn)
    responses:
      200:
        description: Tool information and parameters
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            message:
              type: string
            tool:
              type: object
              properties:
                name:
                  type: string
                description:
                  type: string
                required_parameters:
                  type: array
                  items:
                    type: string
                optional_parameters:
                  type: array
                  items:
                    type: string
                parameter_details:
                  type: object
                example_usage:
                  type: object
      404:
        description: Tool not found
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: false
            error:
              type: string
            message:
              type: string
    """
    lang = request.args.get('lang', 'en')

    if tool_name not in TOOL_REGISTRY:
        return jsonify({
            'success': False,
            'error': get_text(lang, 'api_error_tool_not_found'),
            'message': f'Tool "{tool_name}" not found'
        }), 404

    tool = TOOL_REGISTRY[tool_name]
    params = tool['params_schema']
    required = [p for p, v in params.items() if v.get('required', False)]
    optional = [p for p, v in params.items() if not v.get('required', False)]

    response_data = {
        'success': True,
        'message': get_text(lang, 'api_tool_info'),
        'tool': {
            'name': tool_name,
            'description': tool['description'],
            'required_parameters': required,
            'optional_parameters': optional,
            'parameter_details': params,
            'example_usage': _get_tool_example(tool_name)
        }
    }

    etag = generate_etag(response_data)
    if request.headers.get('If-None-Match') == etag:
        return '', 304

    response = make_response(jsonify(response_data))
    response.headers['ETag'] = etag
    return add_etag_and_cache(response, max_age=300)

@app.route('/api/tools/<tool_name>', methods=['POST'])
def api_call_tool(tool_name: str):
    """POST /api/tools/<tool_name> - Call specific MCP tool with parameters
    ---
    tags:
      - Tools
    parameters:
      - name: tool_name
        in: path
        type: string
        required: true
        description: The name of the MCP tool to call
      - name: lang
        in: query
        type: string
        required: false
        default: en
        description: Language for response messages (en or cn)
      - name: body
        in: body
        required: true
        schema:
          type: object
          description: Tool parameters as JSON
          example:
            sku: "SKU-12345"
            threshold: 10
            platform: "both"
    responses:
      200:
        description: Tool execution successful
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            message:
              type: string
            tool:
              type: string
            parameters_used:
              type: object
            result:
              type: object
              description: Tool execution result data
      400:
        description: Invalid request (missing parameters or invalid JSON)
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: false
            error:
              type: string
            message:
              type: string
            missing_parameters:
              type: array
              items:
                type: string
      404:
        description: Tool not found
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: false
            error:
              type: string
            message:
              type: string
      500:
        description: Tool execution failed
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: false
            error:
              type: string
            message:
              type: string
            tool:
              type: string
            traceback:
              type: string
    """
    lang = request.args.get('lang', 'en')

    if tool_name not in TOOL_REGISTRY:
        return jsonify({
            'success': False,
            'error': get_text(lang, 'api_error_tool_not_found'),
            'message': f'Tool "{tool_name}" not found'
        }), 404

    try:
        if not request.is_json:
            return jsonify({
                'success': False,
                'error': get_text(lang, 'api_error_invalid_json'),
                'message': 'Request must be JSON'
            }), 400

        params = request.json
        if params is None:
            return jsonify({
                'success': False,
                'error': get_text(lang, 'api_error_invalid_json'),
                'message': 'Invalid JSON body'
            }), 400

        tool_schema = TOOL_REGISTRY[tool_name]['params_schema']
        required_params = [p for p, v in tool_schema.items() if v.get('required', False)]
        missing_params = [p for p in required_params if p not in params or params[p] is None]

        if missing_params:
            return jsonify({
                'success': False,
                'error': get_text(lang, 'api_error_missing_params'),
                'message': f'Missing required parameters: {", ".join(missing_params)}',
                'missing_parameters': missing_params
            }), 400

        merged_params = {}
        for param_name, param_schema in tool_schema.items():
            if param_name in params:
                merged_params[param_name] = params[param_name]
            elif param_schema.get('default') is not None:
                merged_params[param_name] = param_schema['default']

        result = AsyncRunner.run_async(call_mcp_tool(tool_name, merged_params))

        if result.get('success'):
            try:
                cache_manager.invalidate_pattern('api:tools:*')
                if tool_name in ('sync_inventory', 'sync_price', 'update_amazon_price',
                                 'save_product_profile', 'update_fulfillment_amazon'):
                    cache_manager.invalidate_pattern('api:analytics:*')
            except Exception:
                pass

            return jsonify({
                'success': True,
                'message': get_text(lang, 'api_tool_called'),
                'tool': tool_name,
                'parameters_used': merged_params,
                'result': result.get('data')
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Unknown error'),
                'tool': tool_name,
                'message': 'Tool execution failed',
                'traceback': result.get('traceback')
            }), 500

    except Exception as e:
        return jsonify({
            'success': False,
            'error': get_text(lang, 'api_error_internal'),
            'message': str(e),
            'tool': tool_name
        }), 500

def _get_tool_example(tool_name: str) -> dict:
    """Get example usage for a tool"""
    examples = {
        'get_low_stock_alerts': {'threshold': 10, 'platform': 'both', 'response_format': 'json'},
        'get_competitor_prices': {'sku': 'SKU-12345', 'limit': 5, 'response_format': 'json'},
        'get_review_alerts': {'days': 7, 'include_supplier_flags': True, 'response_format': 'json'},
        'get_product_cost_1688': {'sku': 'SKU-12345', 'response_format': 'json'},
        'calculate_amazon_price': {'sku': 'SKU-12345', 'cost_cny': 35.0, 'target_margin_percent': 25.0, 'response_format': 'json'},
        'sync_inventory': {'sku': 'SKU-12345', 'response_format': 'json'},
        'get_orders_amazon': {'days': 7, 'limit': 50, 'response_format': 'json'},
        'get_product_reviews': {'sku': 'SKU-12345', 'days': 30, 'limit': 20, 'response_format': 'json'},
        'get_negative_reviews': {'days': 7, 'severity': 'all', 'response_format': 'json'},
        'sync_price': {'sku': 'SKU-12345', 'target_margin_percent': 25.0, 'response_format': 'json'},
        'update_amazon_price': {'sku': 'SKU-12345', 'new_price': 29.99, 'currency': 'USD'},
        'get_inventory_1688': {'sku': 'SKU-12345', 'response_format': 'json'},
        'calculate_true_profit': {'sku': 'SKU-12345', 'selling_price_usd': 29.99, 'cost_cny': 35.0, 'response_format': 'json'},
        'save_product_profile': {'sku': 'SKU-12345', 'cost_cny': 35.0, 'product_name': 'Example Product', 'response_format': 'json'},
        'get_product_profile': {'sku': 'SKU-12345', 'response_format': 'json'},
        'list_all_products': {'hours': 24, 'response_format': 'json'},
        'get_stale_products': {'hours': 24, 'response_format': 'json'},
        'update_fulfillment_amazon': {'order_id': '123-4567890-1234567', 'status': 'Shipped'},
        'get_license_info': {}
    }
    return examples.get(tool_name, {})

@app.route('/api/tools', methods=['POST'])
@rate_limit('BASIC')
def api_call_tool_with_name():
    """POST /api/tools - Alternative endpoint with tool_name in body"""
    lang = request.args.get('lang', 'en')

    try:
        if not request.is_json:
            return jsonify({
                'success': False,
                'error': get_text(lang, 'api_error_invalid_json'),
                'message': 'Request must be JSON'
            }), 400

        data = request.json
        tool_name = data.get('tool_name') or data.get('tool')

        if not tool_name:
            return jsonify({
                'success': False,
                'error': get_text(lang, 'api_error_missing_params'),
                'message': 'Missing required parameter: tool_name'
            }), 400

        if tool_name not in TOOL_REGISTRY:
            return jsonify({
                'success': False,
                'error': get_text(lang, 'api_error_tool_not_found'),
                'message': f'Tool "{tool_name}" not found'
            }), 404

        params = data.get('parameters', data)
        if 'tool_name' in params:
            del params['tool_name']
        if 'tool' in params:
            del params['tool']
        if 'parameters' in params:
            del params['parameters']

        result = AsyncRunner.run_async(call_mcp_tool(tool_name, params))

        if result.get('success'):
            try:
                cache_manager.invalidate_pattern('api:tools:*')
                if tool_name in ('sync_inventory', 'sync_price', 'update_amazon_price',
                                 'save_product_profile', 'update_fulfillment_amazon'):
                    cache_manager.invalidate_pattern('api:analytics:*')
            except Exception:
                pass

            return jsonify({
                'success': True,
                'message': get_text(lang, 'api_tool_called'),
                'tool': tool_name,
                'parameters_used': params,
                'result': result.get('data')
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Unknown error'),
                'tool': tool_name,
                'message': 'Tool execution failed'
            }), 500

    except Exception as e:
        return jsonify({
            'success': False,
            'error': get_text(lang, 'api_error_internal'),
            'message': str(e)
        }), 500

@app.route('/api/tasks', methods=['POST'])
def api_create_task():
    """POST /api/tasks - Submit a new background task"""
    lang = request.args.get('lang', 'en')

    try:
        if not request.is_json:
            return jsonify({
                'success': False,
                'error': get_text(lang, 'api_error_invalid_json'),
                'message': 'Request must be JSON'
            }), 400

        data = request.json
        tool_name = data.get('tool_name')
        parameters = data.get('parameters', {})

        if not tool_name:
            return jsonify({
                'success': False,
                'error': get_text(lang, 'api_error_missing_params'),
                'message': 'Missing required parameter: tool_name'
            }), 400

        if tool_name not in TOOL_REGISTRY:
            return jsonify({
                'success': False,
                'error': get_text(lang, 'api_error_tool_not_found'),
                'message': f'Tool "{tool_name}" not found'
            }), 404

        task_schema = TOOL_REGISTRY[tool_name]['params_schema']
        required_params = [p for p, v in task_schema.items() if v.get('required', False)]
        missing_params = [p for p in required_params if p not in parameters or parameters[p] is None]

        if missing_params:
            return jsonify({
                'success': False,
                'error': get_text(lang, 'api_error_missing_params'),
                'message': f'Missing required parameters: {", ".join(missing_params)}',
                'missing_parameters': missing_params
            }), 400

        task = submit_background_task(tool_name, parameters)

        return jsonify({
            'success': True,
            'message': 'Task submitted successfully',
            'task_id': task['task_id'],
            'status': task['status'],
            'created_at': task['created_at']
        }), 202

    except Exception as e:
        return jsonify({
            'success': False,
            'error': get_text(lang, 'api_error_internal'),
            'message': str(e)
        }), 500

@app.route('/api/tasks/<task_id>', methods=['GET'])
def api_get_task(task_id: str):
    """GET /api/tasks/<task_id> - Get task status"""
    lang = request.args.get('lang', 'en')

    task = get_task(task_id)
    if task is None:
        return jsonify({
            'success': False,
            'error': 'Task not found',
            'message': f'Task "{task_id}" not found'
        }), 404

    response = {
        'success': True,
        'task_id': task['task_id'],
        'tool_name': task['tool_name'],
        'status': task['status'],
        'progress': task['progress'],
        'message': task['message'],
        'created_at': task['created_at'],
        'started_at': task['started_at'],
        'completed_at': task['completed_at']
    }

    if task['status'] == 'completed':
        response['result'] = task['result']
    elif task['status'] == 'failed':
        response['error'] = task['error']

    return jsonify(response)

@app.route('/api/tasks', methods=['GET'])
def api_list_tasks():
    """GET /api/tasks - List all tasks"""
    lang = request.args.get('lang', 'en')
    status = request.args.get('status')
    limit = request.args.get('limit', 100, type=int)

    all_tasks = get_all_tasks(status=status, limit=limit)

    summaries = [{
        'task_id': t['task_id'],
        'tool_name': t['tool_name'],
        'status': t['status'],
        'progress': t['progress'],
        'created_at': t['created_at'],
        'completed_at': t['completed_at']
    } for t in all_tasks]

    return jsonify({
        'success': True,
        'total_tasks': len(TASK_QUEUE),
        'active_count': len(get_active_tasks()),
        'status_filter': status,
        'tasks': summaries
    })

@app.route('/api/tasks/<task_id>', methods=['DELETE'])
def api_delete_task(task_id: str):
    """DELETE /api/tasks/<task_id> - Delete a task"""
    lang = request.args.get('lang', 'en')

    with TASK_LOCK:
        if task_id not in TASK_QUEUE:
            return jsonify({
                'success': False,
                'error': 'Task not found',
                'message': f'Task "{task_id}" not found'
            }), 404

        del TASK_QUEUE[task_id]

    return jsonify({
        'success': True,
        'message': 'Task deleted successfully',
        'task_id': task_id
    })

@app.route('/api/export/inventory', methods=['GET'])
def export_inventory_csv():
    """GET /api/export/inventory - Export inventory data as CSV
    ---
    tags:
      - Export
    produces:
      - text/csv
    parameters:
      - name: threshold
        in: query
        type: integer
        required: false
        default: 10
        description: Stock threshold for low inventory alerts
      - name: platform
        in: query
        type: string
        required: false
        default: both
        description: Filter by platform (1688, amazon, or both)
        enum:
          - 1688
          - amazon
          - both
    responses:
      200:
        description: CSV file download
        schema:
          type: file
          description: CSV file containing inventory data
        headers:
          Content-Disposition:
            type: string
            description: Attachment filename
    """
    threshold = request.args.get('threshold', 10, type=int)
    platform = request.args.get('platform', 'both')

    alerts = []
    try:
        result = AsyncRunner.run_async(call_mcp_tool('get_low_stock_alerts', {
            'threshold': threshold,
            'platform': platform,
            'response_format': 'json'
        }))

        if result.get('success'):
            data = json.loads(result['data'])
            raw_alerts = data.get('alerts', [])

            for alert in raw_alerts:
                if 'error' in alert:
                    continue
                alerts.append({
                    'product_name': alert.get('product_name', 'Unknown'),
                    'sku': alert.get('sku', 'N/A'),
                    'platform': alert.get('platform', 'Unknown'),
                    'current_stock': alert.get('current_stock', 0),
                    'threshold': alert.get('threshold', threshold),
                    'shortage': alert.get('shortage', 0),
                    'severity': alert.get('severity', 'unknown')
                })
    except Exception:
        pass

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=['product_name', 'sku', 'platform', 'current_stock', 'threshold', 'shortage', 'severity'])
    writer.writeheader()
    writer.writerows(alerts)

    log_audit('system', AuditAction.EXPORT.value, ResourceType.INVENTORY.value,
              details={'threshold': threshold, 'platform': platform, 'record_count': len(alerts)})

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename=inventory_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        }
    )

@app.route('/api/export/orders', methods=['GET'])
def export_orders_csv():
    """GET /api/export/orders - Export orders as CSV"""
    days = request.args.get('days', 7, type=int)
    status = request.args.get('status', None)

    orders = []
    try:
        result = AsyncRunner.run_async(call_mcp_tool('get_orders_amazon', {
            'days': days,
            'status': status,
            'limit': 100,
            'response_format': 'json'
        }))

        if result.get('success'):
            data = json.loads(result['data'])
            orders = data.get('orders', [])
    except Exception:
        pass

    output = io.StringIO()
    fieldnames = ['order_id', 'purchase_date', 'status', 'total_amount', 'currency', 'fulfillment_channel', 'number_of_items']
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(orders)

    log_audit('system', AuditAction.EXPORT.value, ResourceType.ORDER.value,
              details={'days': days, 'status_filter': status, 'record_count': len(orders)})

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename=orders_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        }
    )

@app.route('/api/export/reviews', methods=['GET'])
@rate_limit('FREE')
def export_reviews_csv():
    """GET /api/export/reviews - Export reviews as CSV"""
    days = request.args.get('days', 7, type=int)
    min_rating = request.args.get('min_rating', 0, type=int)

    alerts = []
    try:
        result = AsyncRunner.run_async(call_mcp_tool('get_review_alerts', {
            'days': days,
            'include_supplier_flags': True,
            'response_format': 'json'
        }))

        if result.get('success'):
            data = json.loads(result['data'])
            alerts = data.get('alerts', [])

            if min_rating > 0:
                alerts = [a for a in alerts if a.get('rating', 5) <= min_rating]
    except Exception:
        pass

    output = io.StringIO()
    fieldnames = ['sku', 'rating', 'review_date', 'alert_type', 'priority', 'review_summary', 'action_required']
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(alerts)

    log_audit('system', AuditAction.EXPORT.value, ResourceType.REVIEW.value,
              details={'days': days, 'min_rating': min_rating, 'record_count': len(alerts)})

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename=reviews_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        }
    )

@app.route('/api/export/competitors', methods=['GET'])
def export_competitors_csv():
    """GET /api/export/competitors - Export competitor data as CSV"""
    keyword = request.args.get('keyword', 'default')
    limit = request.args.get('limit', 10, type=int)

    competitors = []
    try:
        result = AsyncRunner.run_async(call_mcp_tool('get_competitor_prices', {
            'sku': keyword,
            'limit': limit,
            'response_format': 'json'
        }))

        if result.get('success'):
            data = json.loads(result['data'])
            competitors = data.get('competitors', [])
    except Exception:
        pass

    output = io.StringIO()
    fieldnames = ['asin', 'title', 'price', 'category', 'rating', 'review_count']
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(competitors)

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename=competitors_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        }
    )

@app.route('/api/export/analytics', methods=['GET'])
@rate_limit('FREE')
def export_analytics_csv():
    """GET /api/export/analytics - Export analytics summary as CSV"""
    days = request.args.get('days', 30, type=int)

    analytics_data = {
        'report_date': datetime.now().strftime('%Y-%m-%d'),
        'period_days': days,
        'low_stock_count': 0,
        'pending_orders_count': 0,
        'negative_reviews_count': 0,
        'todays_revenue': 0.0
    }

    try:
        low_stock_result = AsyncRunner.run_async(call_mcp_tool('get_low_stock_alerts', {
            'response_format': 'json'
        }))
        if low_stock_result.get('success'):
            data = json.loads(low_stock_result['data'])
            analytics_data['low_stock_count'] = data.get('total_alerts', 0)
    except Exception:
        pass

    try:
        orders_result = AsyncRunner.run_async(call_mcp_tool('get_orders_amazon', {
            'days': 1,
            'response_format': 'json'
        }))
        if orders_result.get('success'):
            data = json.loads(orders_result['data'])
            orders = data.get('orders', [])
            analytics_data['pending_orders_count'] = sum(1 for o in orders if o.get('status') == 'Pending')
            for order in orders:
                try:
                    analytics_data['todays_revenue'] += float(order.get('total_amount', 0))
                except (ValueError, TypeError):
                    pass
    except Exception:
        pass

    try:
        reviews_result = AsyncRunner.run_async(call_mcp_tool('get_review_alerts', {
            'days': 7,
            'include_supplier_flags': True,
            'response_format': 'json'
        }))
        if reviews_result.get('success'):
            data = json.loads(reviews_result['data'])
            analytics_data['negative_reviews_count'] = data.get('total_alerts', 0)
    except Exception:
        pass

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=['report_date', 'period_days', 'low_stock_count', 'pending_orders_count', 'negative_reviews_count', 'todays_revenue'])
    writer.writeheader()
    writer.writerow(analytics_data)

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename=analytics_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        }
    )

@app.route('/api/export/report', methods=['GET'])
@rate_limit('FREE')
def export_report_pdf():
    """GET /api/export/report - Generate analytics report as PDF"""
    days = request.args.get('days', 30, type=int)
    lang = request.args.get('lang', 'en')

    metrics = {
        'low_stock_count': 0,
        'critical_low_stock': 0,
        'pending_orders': 0,
        'total_revenue': 0.0,
        'review_alerts': 0,
        'critical_reviews': 0
    }

    try:
        low_stock_result = AsyncRunner.run_async(call_mcp_tool('get_low_stock_alerts', {
            'response_format': 'json'
        }))
        if low_stock_result.get('success'):
            data = json.loads(low_stock_result['data'])
            metrics['low_stock_count'] = data.get('total_alerts', 0)
            metrics['critical_low_stock'] = data.get('critical_count', 0)
    except Exception:
        pass

    try:
        orders_result = AsyncRunner.run_async(call_mcp_tool('get_orders_amazon', {
            'days': days,
            'limit': 100,
            'response_format': 'json'
        }))
        if orders_result.get('success'):
            data = json.loads(orders_result['data'])
            orders = data.get('orders', [])
            metrics['pending_orders'] = sum(1 for o in orders if o.get('status') == 'Pending')
            for order in orders:
                try:
                    metrics['total_revenue'] += float(order.get('total_amount', 0))
                except (ValueError, TypeError):
                    pass
    except Exception:
        pass

    try:
        reviews_result = AsyncRunner.run_async(call_mcp_tool('get_review_alerts', {
            'days': 7,
            'include_supplier_flags': True,
            'response_format': 'json'
        }))
        if reviews_result.get('success'):
            data = json.loads(reviews_result['data'])
            metrics['review_alerts'] = data.get('total_alerts', 0)
            priority_breakdown = data.get('priority_breakdown', {})
            metrics['critical_reviews'] = priority_breakdown.get('critical', 0)
    except Exception:
        pass

    try:
        from fpdf import FPDF

        pdf = FPDF()
        pdf.add_page()

        pdf.set_font('Helvetica', 'B', 20)
        title_text = 'Cross-Border Seller Report' if lang == 'en' else '跨境卖家分析报告'
        pdf.cell(0, 15, title_text, ln=True, align='C')

        pdf.set_font('Helvetica', '', 12)
        pdf.cell(0, 8, f"Report Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True, align='C')
        pdf.cell(0, 8, f"Period: Last {days} days" if lang == 'en' else f"时间段: 最近 {days} 天", ln=True, align='C')
        pdf.ln(10)

        pdf.set_font('Helvetica', 'B', 16)
        section_title = 'Key Metrics' if lang == 'en' else '关键指标'
        pdf.cell(0, 10, section_title, ln=True)
        pdf.ln(5)

        pdf.set_font('Helvetica', '', 12)
        metrics_text = [
            ('Low Stock Alerts:', metrics['low_stock_count'], 'Critical:', metrics['critical_low_stock']),
            ('Pending Orders:', metrics['pending_orders'], 'Total Revenue:', f"${metrics['total_revenue']:.2f}"),
            ('Review Alerts:', metrics['review_alerts'], 'Critical Reviews:', metrics['critical_reviews']),
        ]

        for row in metrics_text:
            pdf.cell(50, 8, str(row[0]), border=0)
            pdf.cell(30, 8, str(row[1]), border=0)
            pdf.cell(50, 8, str(row[2]), border=0)
            pdf.cell(30, 8, str(row[3]), border=0)
            pdf.ln(8)

        pdf.ln(15)
        pdf.set_font('Helvetica', 'B', 16)
        summary_title = 'Summary' if lang == 'en' else '概要'
        pdf.cell(0, 10, summary_title, ln=True)
        pdf.ln(5)

        pdf.set_font('Helvetica', '', 11)
        if metrics['low_stock_count'] > 0 or metrics['review_alerts'] > 0:
            alert_text = 'Attention Required' if lang == 'en' else '需要关注'
            pdf.set_font('Helvetica', 'B', 12)
            pdf.cell(0, 8, alert_text, ln=True)
            pdf.set_font('Helvetica', '', 11)

            if metrics['low_stock_count'] > 0:
                stock_msg = f"- {metrics['low_stock_count']} low stock alerts" if lang == 'en' else f"- {metrics['low_stock_count']} 个库存预警"
                pdf.cell(0, 7, stock_msg, ln=True)
            if metrics['review_alerts'] > 0:
                review_msg = f"- {metrics['review_alerts']} review alerts" if lang == 'en' else f"- {metrics['review_alerts']} 条评论警报"
                pdf.cell(0, 7, review_msg, ln=True)
        else:
            good_text = 'All systems operating normally' if lang == 'en' else '系统运行正常'
            pdf.cell(0, 8, good_text, ln=True)

        pdf.ln(20)
        pdf.set_font('Helvetica', 'I', 9)
        footer_text = 'Generated by Cross-Border Seller AI Assistant' if lang == 'en' else '由跨境卖家AI助手生成'
        pdf.cell(0, 10, footer_text, ln=True, align='C')

        response = Response(bytes(pdf.output()))
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=analytics_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
        return response

    except ImportError:
        return jsonify({
            'success': False,
            'error': 'PDF library not available',
            'message': 'Please install fpdf2: pip install fpdf2'
        }), 500

@app.route('/api/history/<metric>', methods=['GET'])
def api_get_history(metric):
    """GET /api/history/<metric> - Get historical data for a metric"""
    from database import get_snapshots

    days = request.args.get('days', 30, type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    if metric not in ['inventory', 'orders', 'reviews', 'competitors']:
        return jsonify({
            'success': False,
            'error': f'Invalid metric: {metric}',
            'valid_metrics': ['inventory', 'orders', 'reviews', 'competitors']
        }), 400

    try:
        snapshots = get_snapshots(metric, start_date, end_date)
        response_data = {
            'success': True,
            'metric': metric,
            'count': len(snapshots),
            'snapshots': snapshots
        }

        etag = generate_etag(response_data)
        if request.headers.get('If-None-Match') == etag:
            return '', 304

        response = make_response(jsonify(response_data))
        response.headers['ETag'] = etag
        return add_etag_and_cache(response, max_age=120)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/trends/<metric>', methods=['GET'])
def api_get_trends(metric):
    """GET /api/trends/<metric> - Get trend analysis for a metric"""
    from analytics_engine import analyzer

    days = request.args.get('days', 30, type=int)

    try:
        trend_result = analyzer.calculate_trends(metric, days)
        return jsonify({
            'success': True,
            'metric': metric,
            'direction': trend_result.direction,
            'change_percent': trend_result.change_percent,
            'avg_value': trend_result.avg_value,
            'volatility': trend_result.volatility,
            'values': trend_result.values,
            'dates': trend_result.dates
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/forecast/<sku>', methods=['GET'])
def api_get_forecast(sku):
    """GET /api/forecast/<sku> - Get stockout prediction for a SKU"""
    from analytics_engine import analyzer

    current_stock = request.args.get('current_stock', type=int)
    sales_velocity = request.args.get('sales_velocity', type=float)
    lead_time_days = request.args.get('lead_time_days', 14, type=int)

    if current_stock is None or sales_velocity is None:
        return jsonify({'success': False, 'error': 'Missing required parameters: current_stock and sales_velocity'}), 400

    try:
        prediction = analyzer.predict_stockout(sku, current_stock, sales_velocity, lead_time_days)
        return jsonify({
            'success': True,
            'sku': prediction.sku,
            'current_stock': prediction.current_stock,
            'days_until_stockout': prediction.days_until_stockout,
            'recommended_reorder': prediction.recommended_reorder,
            'risk_level': prediction.risk_level,
            'confidence': prediction.confidence
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/snapshot', methods=['POST'])
def api_take_snapshot():
    """POST /api/snapshot - Take a manual snapshot"""
    from database import save_snapshot

    if not request.is_json:
        return jsonify({'success': False, 'error': 'Request must be JSON'}), 400

    data = request.json
    snapshot_type = data.get('snapshot_type')
    snapshot_data = data.get('data', {})

    if snapshot_type not in ['inventory', 'orders', 'reviews', 'competitors']:
        return jsonify({'success': False, 'error': 'Invalid snapshot_type'}), 400

    try:
        snapshot_id = save_snapshot(snapshot_type, snapshot_data)
        return jsonify({'success': True, 'snapshot_id': snapshot_id, 'snapshot_type': snapshot_type}), 201
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/analytics/summary', methods=['GET'])
def api_analytics_summary():
    """GET /api/analytics/summary - Get comparative analytics summary
    ---
    tags:
      - Analytics
    responses:
      200:
        description: Comparative analytics data and inventory health score
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            comparative_stats:
              type: object
              description: Comparative statistics across products/platforms
            health_score:
              type: object
              description: Inventory health score metrics
      500:
        description: Error generating analytics
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: false
            error:
              type: string
    """
    from analytics_engine import analyzer

    try:
        stats = analyzer.get_comparative_stats()
        health = analyzer.get_inventory_health_score()
        response_data = {'success': True, 'comparative_stats': stats, 'health_score': health}

        etag = generate_etag(response_data)
        if request.headers.get('If-None-Match') == etag:
            return '', 304

        response = make_response(jsonify(response_data))
        response.headers['ETag'] = etag
        return add_etag_and_cache(response, max_age=60)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/analytics/forecast', methods=['GET'])
def api_analytics_forecast():
    """GET /api/analytics/forecast - Generate forecast"""
    from analytics_engine import analyzer

    metric = request.args.get('metric', 'low_stock_count')
    days_ahead = request.args.get('days_ahead', 7, type=int)

    try:
        forecast = analyzer.generate_forecast(metric, days_ahead)
        return jsonify({'success': True, 'forecast': forecast})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def api_health():
    """Health check endpoint
    ---
    tags:
      - Health
    responses:
      200:
        description: Service is healthy
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            status:
              type: string
              example: healthy
            timestamp:
              type: string
              format: date-time
            version:
              type: string
              example: "1.0.0"
            available_tools:
              type: integer
              description: Number of registered MCP tools
            task_queue:
              type: object
              properties:
                total_tasks:
                  type: integer
                active_tasks:
                  type: integer
    """
    response_data = {
        'success': True,
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0',
        'available_tools': len(TOOL_REGISTRY),
        'task_queue': {
            'total_tasks': len(TASK_QUEUE),
            'active_tasks': len(get_active_tasks())
        }
    }

    etag = generate_etag(response_data)
    if request.headers.get('If-None-Match') == etag:
        return '', 304

    response = make_response(jsonify(response_data))
    response.headers['ETag'] = etag
    return add_etag_and_cache(response, max_age=30)

@app.route('/api/inventory/forecast', methods=['GET'])
def api_inventory_forecast():
    """GET /api/inventory/forecast - Get inventory stockout predictions"""
    from analytics_engine import analyzer

    threshold = request.args.get('threshold', 14, type=int)
    lead_time = request.args.get('lead_time', 14, type=int)

    try:
        risk_products = analyzer.identify_risk_products(threshold_days=threshold)

        for product in risk_products:
            dos = analyzer.calculate_days_of_supply(product['sku'])
            product['days_of_supply'] = dos.get('days_of_supply', float('inf'))

            reorder = analyzer.calculate_reorder_quantity(
                product['sku'],
                sales_velocity=product.get('days_until_stockout', 1) / (dos.get('days_of_supply', 30) or 30),
                lead_time=lead_time,
                target_days=30
            )
            product['reorder_quantity'] = reorder.get('reorder_quantity', 0)
            product['reorder_urgency'] = reorder.get('urgency', 'none')

        return jsonify({
            'success': True,
            'forecast': risk_products,
            'summary': {
                'total_at_risk': len(risk_products),
                'critical_count': sum(1 for p in risk_products if p['risk_level'] == 'critical'),
                'high_risk_count': sum(1 for p in risk_products if p['risk_level'] == 'high'),
                'medium_risk_count': sum(1 for p in risk_products if p['risk_level'] == 'medium'),
                'threshold_days': threshold
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/inventory/reorder/<sku>', methods=['GET'])
def api_inventory_reorder(sku):
    """GET /api/inventory/reorder/<sku> - Get reorder recommendation for a SKU"""
    from analytics_engine import analyzer

    lead_time = request.args.get('lead_time', 14, type=int)
    target_days = request.args.get('target_days', 30, type=int)

    try:
        dos = analyzer.calculate_days_of_supply(sku)
        sales_velocity = dos.get('avg_daily_demand', 0)

        reorder = analyzer.calculate_reorder_quantity(
            sku,
            sales_velocity=sales_velocity,
            lead_time=lead_time,
            target_days=target_days
        )

        return jsonify({
            'success': True,
            'reorder': reorder,
            'days_of_supply': dos
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/inventory/health', methods=['GET'])
def api_inventory_health():
    """GET /api/inventory/health - Get overall inventory health score"""
    from analytics_engine import analyzer

    try:
        health_score = analyzer.get_inventory_health_score()

        risk_products = analyzer.identify_risk_products(threshold_days=14)

        response_data = {
            'success': True,
            'health': health_score,
            'risk_summary': {
                'products_at_risk': len(risk_products),
                'critical': sum(1 for p in risk_products if p['risk_level'] == 'critical'),
                'high': sum(1 for p in risk_products if p['risk_level'] == 'high'),
                'medium': sum(1 for p in risk_products if p['risk_level'] == 'medium'),
                'low': sum(1 for p in risk_products if p['risk_level'] == 'low')
            }
        }

        etag = generate_etag(response_data)
        if request.headers.get('If-None-Match') == etag:
            return '', 304

        response = make_response(jsonify(response_data))
        response.headers['ETag'] = etag
        return add_etag_and_cache(response, max_age=60)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/competitor/trends/<asin>', methods=['GET'])
def api_competitor_trends(asin):
    """GET /api/competitor/trends/<asin> - Get price trends for a competitor ASIN"""
    from analytics_engine import competitor_analyzer

    try:
        days = request.args.get('days', 30, type=int)
        competitor_analyzer.track_price_changes(asin, days=days)
        trend_data = competitor_analyzer.identify_price_trends(asin)
        prediction = competitor_analyzer.predict_price_movements(asin)

        return jsonify({
            'success': True,
            'asin': asin,
            'trend': trend_data,
            'prediction': {
                'direction': prediction.direction,
                'confidence': prediction.confidence,
                'predicted_price_7d': prediction.predicted_price_7d,
                'predicted_price_14d': prediction.predicted_price_14d,
                'predicted_price_30d': prediction.predicted_price_30d,
                'factors': prediction.factors
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/competitor/alerts', methods=['GET'])
def api_competitor_alerts():
    """GET /api/competitor/alerts - Get significant competitor movement alerts"""
    from analytics_engine import competitor_analyzer

    try:
        asins_param = request.args.get('asins', '')
        asins = [a.strip() for a in asins_param.split(',') if a.strip()]

        if not asins:
            asins = request.args.getlist('asin')

        if not asins:
            return jsonify({
                'success': True,
                'alerts': [],
                'count': 0
            })

        alerts = competitor_analyzer.get_price_alerts(asins)

        movements = competitor_analyzer.detect_competitive_movements(asins)

        return jsonify({
            'success': True,
            'alerts': alerts,
            'movements': movements,
            'count': len(alerts)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/competitor/market-position/<asin>', methods=['GET'])
def api_competitor_market_position(asin):
    """GET /api/competitor/market-position/<asin> - Get market position analysis"""
    from analytics_engine import competitor_analyzer

    try:
        competitors_param = request.args.get('competitors', '')
        competitors = []

        if competitors_param:
            try:
                competitors = json.loads(competitors_param)
            except json.JSONDecodeError:
                pass

        if not competitors:
            search_term = request.args.get('search_term', asin)
            result = AsyncRunner.run_async(call_mcp_tool('get_competitor_prices', {
                'sku': search_term,
                'limit': 10,
                'response_format': 'json'
            }))

            if result.get('success'):
                data = json.loads(result['data'])
                competitors = data.get('competitors', [])

        market_position = competitor_analyzer.calculate_market_position(asin, competitors)
        market_shifts = competitor_analyzer.detect_market_share_shifts(asin, competitors)

        return jsonify({
            'success': True,
            'asin': asin,
            'position': {
                'current_price': market_position.current_price,
                'price_rank': market_position.price_rank,
                'total_competitors': market_position.total_competitors,
                'percentile': market_position.percentile,
                'price_distance_from_lowest': market_position.price_distance_from_lowest,
                'price_distance_from_highest': market_position.price_distance_from_highest,
                'relative_position': market_position.relative_position
            },
            'market_shifts': market_shifts
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/price-recommendation/<sku>', methods=['GET'])
def api_price_recommendation(sku):
    """GET /api/price-recommendation/<sku> - Get AI-powered price recommendation for a SKU"""
    from price_optimizer import optimizer

    strategy = request.args.get('strategy', 'balanced')
    target_margin = request.args.get('target_margin', type=float)
    custom_cost = request.args.get('cost', type=float)

    try:
        recommendation = optimizer.get_price_recommendation(
            sku=sku,
            strategy=strategy,
            custom_cost=custom_cost,
            target_margin=target_margin
        )

        return jsonify({
            'success': True,
            'recommendation': recommendation
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/price-analysis/<asin>', methods=['GET'])
def api_price_analysis(asin):
    """GET /api/price-analysis/<asin> - Analyze competitor prices for an ASIN"""
    from price_optimizer import optimizer

    limit = request.args.get('limit', 10, type=int)

    try:
        analysis = optimizer.analyze_competition(asin, limit=limit)

        return jsonify({
            'success': True,
            'analysis': analysis
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/competitive-threats', methods=['GET'])
def api_competitive_threats():
    """GET /api/competitive-threats - Detect competitive threats"""
    from price_optimizer import optimizer

    asin = request.args.get('asin')
    current_price = request.args.get('current_price', type=float)
    threshold = request.args.get('threshold', 15.0, type=float)

    if not asin:
        return jsonify({'success': False, 'error': 'ASIN is required'}), 400

    try:
        threats = optimizer.detect_competitive_threats(
            asin=asin,
            current_price=current_price,
            threshold_percent=threshold
        )

        return jsonify({
            'success': True,
            'asin': asin,
            'threats': [threat.__dict__ for threat in threats],
            'threat_count': len(threats),
            'critical_count': sum(1 for t in threats if t.threat_level == 'critical'),
            'high_count': sum(1 for t in threats if t.threat_level == 'high')
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/price-sensitivity', methods=['GET'])
def api_price_sensitivity():
    """GET /api/price-sensitivity - Analyze price sensitivity"""
    from price_optimizer import optimizer

    demand = request.args.get('demand', 50, type=float)
    elasticity = request.args.get('elasticity', -1.5, type=float)
    current_price = request.args.get('current_price', type=float)

    try:
        analysis = optimizer.analyze_price_sensitivity(
            demand=demand,
            elasticity=elasticity,
            current_price=current_price
        )

        return jsonify({
            'success': True,
            'sensitivity': analysis
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/calculate-optimal-price', methods=['POST'])
def api_calculate_optimal_price():
    """POST /api/calculate-optimal-price - Calculate optimal price"""
    from price_optimizer import optimizer

    data = request.get_json() or {}
    cost = data.get('cost', 0)
    competitor_prices = data.get('competitor_prices', [])
    target_margin = data.get('target_margin', 25)
    strategy = data.get('strategy', 'balanced')

    if not cost:
        return jsonify({'success': False, 'error': 'Cost is required'}), 400

    try:
        result = optimizer.calculate_optimal_price(
            cost=cost,
            competitor_prices=competitor_prices,
            target_margin=target_margin,
            strategy=strategy
        )

        return jsonify({
            'success': True,
            'calculation': result
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

SCHEDULES_FILE = 'schedules.json'
SCHEDULES_LOCK = threading.Lock()

def load_schedules():
    try:
        if os.path.exists(SCHEDULES_FILE):
            with open(SCHEDULES_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return []

def save_schedules(schedules):
    with SCHEDULES_LOCK:
        try:
            with open(SCHEDULES_FILE, 'w') as f:
                json.dump(schedules, f, indent=2, default=str)
        except Exception as e:
            print(f"Error saving schedules: {e}")

def get_schedule(schedule_id):
    schedules = load_schedules()
    for schedule in schedules:
        if schedule.get('id') == schedule_id:
            return schedule
    return None

def create_schedule(data):
    schedules = load_schedules()
    schedule_id = f"sched_{uuid.uuid4().hex[:12]}"
    now = datetime.now().isoformat()

    schedule = {
        'id': schedule_id,
        'name': data.get('name'),
        'task_type': data.get('task_type'),
        'schedule_type': data.get('schedule_type'),
        'enabled': data.get('enabled', True),
        'notify_on_success': data.get('notify_on_success', True),
        'notify_on_failure': data.get('notify_on_failure', True),
        'created_at': now,
        'updated_at': now,
        'last_run': None,
        'next_run': None,
        'run_count': 0
    }

    if data.get('schedule_type') == 'interval':
        schedule['interval_value'] = data.get('interval_value', 1)
        schedule['interval_unit'] = data.get('interval_unit', 'hours')
        schedule['schedule_display'] = f"{schedule['interval_value']} {schedule['interval_unit']}"
        schedule['next_run'] = calculate_next_run_interval(schedule)
    else:
        schedule['cron_minute'] = data.get('cron_minute', '*')
        schedule['cron_hour'] = data.get('cron_hour', '*')
        schedule['cron_day'] = data.get('cron_day', '*')
        schedule['cron_month'] = data.get('cron_month', '*')
        schedule['cron_weekday'] = data.get('cron_weekday', '*')
        schedule['schedule_display'] = f"{schedule['cron_minute']} {schedule['cron_hour']} {schedule['cron_day']} {schedule['cron_month']} {schedule['cron_weekday']}"
        schedule['next_run'] = calculate_next_run_cron(schedule)

    schedules.append(schedule)
    save_schedules(schedules)
    return schedule

def update_schedule(schedule_id, data):
    schedules = load_schedules()
    for i, schedule in enumerate(schedules):
        if schedule.get('id') == schedule_id:
            schedule['name'] = data.get('name', schedule['name'])
            schedule['task_type'] = data.get('task_type', schedule['task_type'])
            schedule['schedule_type'] = data.get('schedule_type', schedule['schedule_type'])
            schedule['enabled'] = data.get('enabled', schedule['enabled'])
            schedule['notify_on_success'] = data.get('notify_on_success', schedule.get('notify_on_success', True))
            schedule['notify_on_failure'] = data.get('notify_on_failure', schedule.get('notify_on_failure', True))
            schedule['updated_at'] = datetime.now().isoformat()

            if data.get('schedule_type') == 'interval':
                schedule['interval_value'] = data.get('interval_value', schedule.get('interval_value', 1))
                schedule['interval_unit'] = data.get('interval_unit', schedule.get('interval_unit', 'hours'))
                schedule['schedule_display'] = f"{schedule['interval_value']} {schedule['interval_unit']}"
                schedule['next_run'] = calculate_next_run_interval(schedule)
                for key in ['cron_minute', 'cron_hour', 'cron_day', 'cron_month', 'cron_weekday']:
                    if key in schedule:
                        del schedule[key]
            else:
                schedule['cron_minute'] = data.get('cron_minute', schedule.get('cron_minute', '*'))
                schedule['cron_hour'] = data.get('cron_hour', schedule.get('cron_hour', '*'))
                schedule['cron_day'] = data.get('cron_day', schedule.get('cron_day', '*'))
                schedule['cron_month'] = data.get('cron_month', schedule.get('cron_month', '*'))
                schedule['cron_weekday'] = data.get('cron_weekday', schedule.get('cron_weekday', '*'))
                schedule['schedule_display'] = f"{schedule['cron_minute']} {schedule['cron_hour']} {schedule['cron_day']} {schedule['cron_month']} {schedule['cron_weekday']}"
                schedule['next_run'] = calculate_next_run_cron(schedule)
                for key in ['interval_value', 'interval_unit']:
                    if key in schedule:
                        del schedule[key]

            schedules[i] = schedule
            save_schedules(schedules)
            return schedule
    return None

def delete_schedule(schedule_id):
    schedules = load_schedules()
    new_schedules = [s for s in schedules if s.get('id') != schedule_id]
    if len(new_schedules) < len(schedules):
        save_schedules(new_schedules)
        return True
    return False

def toggle_schedule(schedule_id):
    schedules = load_schedules()
    for schedule in schedules:
        if schedule.get('id') == schedule_id:
            schedule['enabled'] = not schedule.get('enabled', True)
            schedule['updated_at'] = datetime.now().isoformat()
            save_schedules(schedules)
            return schedule
    return None

def calculate_next_run_interval(schedule):
    now = datetime.now()
    value = schedule.get('interval_value', 1)
    unit = schedule.get('interval_unit', 'hours')

    if unit == 'minutes':
        delta = timedelta(minutes=value)
    elif unit == 'hours':
        delta = timedelta(hours=value)
    elif unit == 'days':
        delta = timedelta(days=value)
    else:
        delta = timedelta(hours=value)

    next_run = now + delta
    return next_run.strftime('%Y-%m-%d %H:%M')

def calculate_next_run_cron(schedule):
    now = datetime.now()
    minute = schedule.get('cron_minute', '*')
    hour = schedule.get('cron_hour', '*')

    if minute == '*' and hour == '*':
        return (now + timedelta(hours=1)).strftime('%Y-%m-%d %H:00')

    try:
        target_hour = int(hour) if hour != '*' else now.hour
        target_minute = int(minute) if minute != '*' else 0
        next_run = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
        return next_run.strftime('%Y-%m-%d %H:%M')
    except (ValueError, TypeError):
        return (now + timedelta(hours=1)).strftime('%Y-%m-%d %H:00')

TASK_TEMPLATES = [
    {'id': 'sync_inventory', 'name': 'Sync Inventory', 'name_cn': '同步库存', 'description': 'Sync 1688 and Amazon inventory', 'description_cn': '同步1688和Amazon库存', 'icon': '📦', 'color': 'from-blue-500 to-cyan-500'},
    {'id': 'check_alerts', 'name': 'Check Alerts', 'name_cn': '检查警报', 'description': 'Check inventory and review alerts', 'description_cn': '检查库存和评论警报', 'icon': '⚠️', 'color': 'from-orange-500 to-red-500'},
    {'id': 'sync_prices', 'name': 'Sync Prices', 'name_cn': '同步价格', 'description': 'Sync 1688 cost and Amazon prices', 'description_cn': '同步1688成本和Amazon价格', 'icon': '💰', 'color': 'from-green-500 to-emerald-500'},
    {'id': 'fetch_orders', 'name': 'Fetch Orders', 'name_cn': '获取订单', 'description': 'Get latest orders from Amazon', 'description_cn': '从Amazon获取最新订单', 'icon': '📋', 'color': 'from-purple-500 to-indigo-500'}
]

@app.route('/schedule')
@login_required
@role_required('manager')
def schedule_list():
    lang = request.args.get('lang', 'cn')
    schedules = load_schedules()
    for schedule in schedules:
        if schedule.get('task_type'):
            for template in TASK_TEMPLATES:
                if template['id'] == schedule['task_type']:
                    schedule['icon'] = template['icon']
                    break

    active_count = sum(1 for s in schedules if s.get('enabled', True))
    paused_count = sum(1 for s in schedules if not s.get('enabled', True))
    total_runs = sum(s.get('run_count', 0) for s in schedules)

    task_templates = []
    for template in TASK_TEMPLATES:
        task_templates.append({
            'id': template['id'],
            'name': template[f'name_{lang}'],
            'description': template[f'description_{lang}'],
            'icon': template['icon'],
            'color': template['color']
        })

    return render_template('schedule.html', lang=lang, get_text=lambda key: get_text(lang, key), schedules=schedules, task_templates=task_templates, active_count=active_count, paused_count=paused_count, total_runs=total_runs, request=request)

@app.route('/schedule/new', methods=['GET', 'POST'])
def schedule_new():
    lang = request.args.get('lang', 'cn')

    if request.method == 'POST':
        data = request.json or {}
        schedule = create_schedule(data)
        return jsonify({'success': True, 'schedule': schedule})

    task_type = request.args.get('task_type', '')
    task_templates = [{'id': t['id'], 'name': t[f'name_{lang}'], 'description': t[f'description_{lang}'], 'icon': t['icon'], 'color': t['color']} for t in TASK_TEMPLATES]

    return render_template('schedule_edit.html', lang=lang, get_text=lambda key: get_text(lang, key), schedule=None, task_templates=task_templates, request=request)

@app.route('/schedule/<schedule_id>/edit', methods=['GET', 'POST'])
def schedule_edit(schedule_id):
    lang = request.args.get('lang', 'cn')
    schedule = get_schedule(schedule_id)
    if schedule is None:
        return render_template('schedule.html', lang=lang, get_text=lambda key: get_text(lang, key), error='Schedule not found', request=request)

    if request.method == 'POST':
        data = request.json or {}
        updated = update_schedule(schedule_id, data)
        return jsonify({'success': True, 'schedule': updated})

    task_templates = [{'id': t['id'], 'name': t[f'name_{lang}'], 'description': t[f'description_{lang}'], 'icon': t['icon'], 'color': t['color']} for t in TASK_TEMPLATES]
    return render_template('schedule_edit.html', lang=lang, get_text=lambda key: get_text(lang, key), schedule=schedule, task_templates=task_templates, request=request)

@app.route('/schedule/<schedule_id>/delete', methods=['POST'])
def schedule_delete(schedule_id):
    success = delete_schedule(schedule_id)
    return jsonify({'success': success, 'error': None if success else 'Schedule not found'})

@app.route('/schedule/<schedule_id>/toggle', methods=['POST'])
def schedule_toggle(schedule_id):
    schedule = toggle_schedule(schedule_id)
    if schedule:
        return jsonify({'success': True, 'schedule': schedule})
    return jsonify({'success': False, 'error': 'Schedule not found'})

@app.route('/api/schedules', methods=['GET'])
@rate_limit('PRO')
def api_list_schedules():
    schedules = load_schedules()
    return jsonify({'success': True, 'schedules': schedules, 'total': len(schedules)})

@app.route('/api/schedules/<schedule_id>', methods=['GET'])
@rate_limit('PRO')
def api_get_schedule(schedule_id):
    schedule = get_schedule(schedule_id)
    if schedule:
        return jsonify({'success': True, 'schedule': schedule})
    return jsonify({'success': False, 'error': 'Schedule not found'}), 404

@app.route('/notifications')
@login_required
def notifications_page():
    lang = request.args.get('lang', 'en')
    notif_service = get_notification_service()
    prefs = notif_service.get_preferences()

    preferences = {
        'email_enabled': prefs.email_enabled,
        'email_address': prefs.email_address,
        'slack_enabled': prefs.slack_enabled,
        'slack_webhook_url': prefs.slack_webhook_url,
        'wechat_enabled': prefs.wechat_enabled,
        'wechat_webhook_url': prefs.wechat_webhook_url,
        'dingtalk_enabled': prefs.dingtalk_enabled,
        'dingtalk_webhook_url': prefs.dingtalk_webhook_url,
        'smtp_host': prefs.smtp_host,
        'smtp_port': prefs.smtp_port,
        'smtp_username': prefs.smtp_username,
        'smtp_password': prefs.smtp_password,
        'notify_low_stock': prefs.notify_low_stock,
        'notify_reviews': prefs.notify_reviews,
        'notify_tasks': prefs.notify_tasks,
        'frequency': prefs.frequency
    }

    queue = notif_service.get_queue()
    history = notif_service.get_history(limit=20)

    return render_template('notifications.html',
                         lang=lang,
                         get_text=lambda key: get_text(lang, key),
                         preferences=preferences,
                         queue=queue,
                         history=history)

@app.route('/api/notifications', methods=['GET'])
def api_get_notifications():
    """GET /api/notifications - Get notification preferences and recent notifications
    ---
    tags:
      - Notifications
    responses:
      200:
        description: Notification preferences and recent history
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            preferences:
              type: object
              properties:
                email_enabled:
                  type: boolean
                email_address:
                  type: string
                slack_enabled:
                  type: boolean
                slack_webhook_url:
                  type: string
                wechat_enabled:
                  type: boolean
                wechat_webhook_url:
                  type: string
                dingtalk_enabled:
                  type: boolean
                dingtalk_webhook_url:
                  type: string
                notify_low_stock:
                  type: boolean
                notify_reviews:
                  type: boolean
                notify_tasks:
                  type: boolean
                frequency:
                  type: string
                  enum: [immediate, hourly, daily]
            queue_count:
              type: integer
            recent_notifications:
              type: array
              items:
                type: object
    """
    notif_service = get_notification_service()
    prefs = notif_service.get_preferences()

    return jsonify({
        'success': True,
        'preferences': {
            'email_enabled': prefs.email_enabled,
            'email_address': prefs.email_address,
            'slack_enabled': prefs.slack_enabled,
            'slack_webhook_url': prefs.slack_webhook_url,
            'wechat_enabled': prefs.wechat_enabled,
            'wechat_webhook_url': prefs.wechat_webhook_url,
            'dingtalk_enabled': prefs.dingtalk_enabled,
            'dingtalk_webhook_url': prefs.dingtalk_webhook_url,
            'notify_low_stock': prefs.notify_low_stock,
            'notify_reviews': prefs.notify_reviews,
            'notify_tasks': prefs.notify_tasks,
            'frequency': prefs.frequency
        },
        'queue_count': len(notif_service.get_queue()),
        'recent_notifications': notif_service.get_history(limit=10)
    })

@app.route('/api/notifications/preferences', methods=['POST'])
def api_save_preferences():
    data = request.get_json()

    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400

    prefs = NotificationPreference(
        email_enabled=data.get('email_enabled', False),
        slack_enabled=data.get('slack_enabled', False),
        wechat_enabled=data.get('wechat_enabled', False),
        dingtalk_enabled=data.get('dingtalk_enabled', False),
        email_address=data.get('email_address', ''),
        slack_webhook_url=data.get('slack_webhook_url', ''),
        wechat_webhook_url=data.get('wechat_webhook_url', ''),
        dingtalk_webhook_url=data.get('dingtalk_webhook_url', ''),
        smtp_host=data.get('smtp_host', 'smtp.gmail.com'),
        smtp_port=int(data.get('smtp_port', 587)),
        smtp_username=data.get('smtp_username', ''),
        smtp_password=data.get('smtp_password', ''),
        from_email=data.get('email_address', ''),
        notify_low_stock=data.get('notify_low_stock', True),
        notify_reviews=data.get('notify_reviews', True),
        notify_tasks=data.get('notify_tasks', True),
        frequency=data.get('frequency', 'immediate')
    )

    notif_service = get_notification_service()
    notif_service.update_preferences(prefs)

    return jsonify({'success': True, 'message': 'Preferences saved successfully'})

@app.route('/api/notifications/test', methods=['POST'])
def api_send_test():
    lang = request.args.get('lang', 'en')
    notif_service = get_notification_service()
    results = notif_service.send_test_notification(lang)

    email_ok = results.get('email', {}).get('success', False)
    slack_ok = results.get('slack', {}).get('success', False)
    dingtalk_ok = results.get('dingtalk', {}).get('success', False)

    if email_ok and slack_ok and dingtalk_ok:
        message = 'Test notification sent successfully!' if lang != 'cn' else '测试通知发送成功！'
    elif email_ok and dingtalk_ok:
        message = 'Test sent via Email and DingTalk (Slack failed)' if lang != 'cn' else '测试邮件和钉钉已发送（Slack失败）'
    elif email_ok and slack_ok:
        message = 'Test sent via Email and Slack (DingTalk failed)' if lang != 'cn' else '测试邮件和Slack已发送（钉钉失败）'
    elif slack_ok and dingtalk_ok:
        message = 'Test sent via Slack and DingTalk (Email failed)' if lang != 'cn' else '测试Slack和钉钉已发送（邮件失败）'
    elif email_ok:
        message = 'Test email sent' if lang != 'cn' else '测试邮件已发送'
    elif slack_ok:
        message = 'Test Slack sent' if lang != 'cn' else '测试Slack已发送'
    elif dingtalk_ok:
        message = 'Test DingTalk sent' if lang != 'cn' else '测试钉钉已发送'
    else:
        message = 'Failed to send test notification' if lang != 'cn' else '发送测试通知失败'

    return jsonify({
        'success': email_ok or slack_ok or dingtalk_ok,
        'message': message,
        'results': results
    })

@app.route('/api/notifications/test/wechat', methods=['POST'])
def api_send_wechat_test():
    lang = request.args.get('lang', 'en')
    notif_service = get_notification_service()
    prefs = notif_service.get_preferences()

    if not prefs.wechat_enabled or not prefs.wechat_webhook_url:
        message = 'WeChat Work not configured' if lang != 'cn' else '企业微信未配置'
        return jsonify({'success': False, 'message': message})

    template = NotificationTemplates.test_notification(lang)
    wechat_content = template['wechat_en'] if lang != 'cn' else template['wechat_cn']

    success = notif_service.send_wechat_notification(prefs.wechat_webhook_url, wechat_content)

    if success:
        message = 'WeChat Work test sent successfully!' if lang != 'cn' else '企业微信测试发送成功！'
    else:
        message = 'Failed to send WeChat Work test' if lang != 'cn' else '企业微信测试发送失败'

    return jsonify({'success': success, 'message': message})

@app.route('/api/notifications/test/dingtalk', methods=['POST'])
def api_send_dingtalk_test():
    lang = request.args.get('lang', 'en')
    notif_service = get_notification_service()
    prefs = notif_service.get_preferences()

    if not prefs.dingtalk_enabled or not prefs.dingtalk_webhook_url:
        message = 'DingTalk not configured' if lang != 'cn' else '钉钉未配置'
        return jsonify({'success': False, 'message': message})

    template = NotificationTemplates.test_notification(lang)
    dingtalk_content = template['dingtalk_en'] if lang != 'cn' else template['dingtalk_cn']

    success = notif_service.send_dingtalk_notification(prefs.dingtalk_webhook_url, dingtalk_content)

    if success:
        message = 'DingTalk test sent successfully!' if lang != 'cn' else '钉钉测试发送成功！'
    else:
        message = 'Failed to send DingTalk test' if lang != 'cn' else '钉钉测试发送失败'

    return jsonify({'success': success, 'message': message})

@app.route('/audit-logs')
def audit_logs_page():
    """Audit Logs page"""
    lang = request.args.get('lang', 'cn')
    user_filter = request.args.get('user', '')
    action_filter = request.args.get('action', '')
    resource_filter = request.args.get('resource', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    page = request.args.get('page', 1, type=int)
    per_page = 50

    logs = []
    total_count = 0
    total_pages = 0

    try:
        start_iso = None
        end_iso = None
        if date_from:
            start_iso = datetime.strptime(date_from, '%Y-%m-%d').isoformat()
        if date_to:
            end_iso = datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59).isoformat()

        total_count = AuditLogger.get_log_count(
            user_id=user_filter if user_filter else None,
            action=action_filter if action_filter else None,
            resource_type=resource_filter if resource_filter else None,
            start_date=start_iso,
            end_date=end_iso
        )

        total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1
        offset = (page - 1) * per_page

        logs = AuditLogger.get_logs(
            user_id=user_filter if user_filter else None,
            action=action_filter if action_filter else None,
            resource_type=resource_filter if resource_filter else None,
            start_date=start_iso,
            end_date=end_iso,
            limit=per_page,
            offset=offset
        )

        for log in logs:
            if log.get('timestamp'):
                try:
                    dt = datetime.fromisoformat(log['timestamp'])
                    log['formatted_time'] = dt.strftime('%Y-%m-%d %H:%M:%S')
                    log['relative_time'] = get_relative_time(dt.strftime('%Y-%m-%d %H:%M:%S'))
                except:
                    log['formatted_time'] = log['timestamp']
                    log['relative_time'] = 'unknown'

    except Exception:
        logs = []

    action_choices = [a.value for a in AuditAction]
    resource_choices = [r.value for r in ResourceType]

    return render_template('admin/audit_logs.html',
                          lang=lang,
                          get_text=lambda key: get_text(lang, key),
                          logs=logs,
                          total_count=total_count,
                          page=page,
                          total_pages=total_pages,
                          user_filter=user_filter,
                          action_filter=action_filter,
                          resource_filter=resource_filter,
                          date_from=date_from,
                          date_to=date_to,
                          action_choices=action_choices,
                          resource_choices=resource_choices,
                          request=request)

@app.route('/api/audit-logs', methods=['GET'])
def api_get_audit_logs():
    """GET /api/audit-logs - Get audit logs with pagination and filters"""
    user_id = request.args.get('user_id')
    action = request.args.get('action')
    resource_type = request.args.get('resource_type')
    resource_id = request.args.get('resource_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    limit = request.args.get('limit', 100, type=int)
    offset = request.args.get('offset', 0, type=int)

    try:
        logs = AuditLogger.get_logs(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset
        )
        total = AuditLogger.get_log_count(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            start_date=start_date,
            end_date=end_date
        )

        return jsonify({
            'success': True,
            'logs': logs,
            'total': total,
            'limit': limit,
            'offset': offset
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/audit-logs/export', methods=['GET'])
def api_export_audit_logs():
    """GET /api/audit-logs/export - Export audit logs as CSV or JSON"""
    export_format = request.args.get('format', 'csv')
    user_id = request.args.get('user_id')
    action = request.args.get('action')
    resource_type = request.args.get('resource_type')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    try:
        filename = AuditLogger.export_logs(
            format=export_format,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            start_date=start_date,
            end_date=end_date
        )

        log_audit('system', AuditAction.EXPORT.value, ResourceType.EXPORT.value,
                  details={'format': export_format, 'filename': filename})

        return jsonify({
            'success': True,
            'filename': filename,
            'download_url': f'/exports/{filename}'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/audit-logs/statistics', methods=['GET'])
def api_audit_statistics():
    """GET /api/audit-logs/statistics - Get audit log statistics"""
    days = request.args.get('days', 30, type=int)

    try:
        stats = AuditLogger.get_action_statistics(days=days)
        return jsonify({
            'success': True,
            'statistics': stats
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/audit-logs/user/<user_id>', methods=['GET'])
def api_user_activity(user_id):
    """GET /api/audit-logs/user/<user_id> - Get user activity summary"""
    days = request.args.get('days', 30, type=int)

    try:
        activity = AuditLogger.get_user_activity(user_id, days=days)
        return jsonify({
            'success': True,
            'activity': activity
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/audit-logs/resource/<resource_type>/<resource_id>', methods=['GET'])
def api_resource_history(resource_type, resource_id):
    """GET /api/audit-logs/resource/<resource_type>/<resource_id> - Get resource change history"""
    limit = request.args.get('limit', 50, type=int)

    try:
        history = AuditLogger.get_resource_history(resource_type, resource_id, limit=limit)
        return jsonify({
            'success': True,
            'resource_type': resource_type,
            'resource_id': resource_id,
            'history': history
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/audit-logs/cleanup', methods=['POST'])
@permission_required('admin')
def api_cleanup_audit_logs():
    """POST /api/audit-logs/cleanup - Clean up old audit logs"""
    data = request.get_json() or {}
    days_to_keep = data.get('days_to_keep', 90)

    try:
        deleted_count = AuditLogger.cleanup_old_logs(days_to_keep=days_to_keep)
        user_id = getattr(g, 'current_user_id', 'system')
        log_audit(user_id, AuditAction.DELETE.value, ResourceType.AUDIT.value,
                  details={'deleted_count': deleted_count, 'days_to_keep': days_to_keep})
        return jsonify({
            'success': True,
            'deleted_count': deleted_count,
            'message': f'Cleaned up {deleted_count} old audit logs'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    import threading
    import time

    from analytics_engine import take_daily_snapshot

    admin_result = auth_service.register_user('admin@demo.com', 'admin123', 'admin')
    if admin_result.get('success'):
        print("✅ Demo admin user created: admin@demo.com/admin123")
    manager_result = auth_service.register_user('manager@demo.com', 'manager123', 'manager')
    if manager_result.get('success'):
        print("✅ Demo manager user created: manager@demo.com/manager123")
    viewer_result = auth_service.register_user('viewer@demo.com', 'viewer123', 'viewer')
    if viewer_result.get('success'):
        print("✅ Demo viewer user created: viewer@demo.com/viewer123")

    def run_daily_snapshot():
        last_snapshot_date = None
        while True:
            try:
                current_date = datetime.now().strftime('%Y-%m-%d')
                if last_snapshot_date != current_date:
                    snapshot_ids = take_daily_snapshot()
                    print(f"📊 Daily snapshots created: {snapshot_ids}")
                    last_snapshot_date = current_date
            except Exception as e:
                print(f"Snapshot error: {e}")
            time.sleep(3600)

    snapshot_thread = threading.Thread(target=run_daily_snapshot, daemon=True)
    snapshot_thread.start()
    print("📊 Daily snapshot scheduler started")

    print("="*60)
    print("🚀 Cross-Border Seller Web UI + REST API")
    print("跨境卖家Web界面 + REST API - 启动中...")
    print("="*60)
    print("")
    print("📱 Web UI: http://localhost:5000")
    print("")
    print("🔧 REST API Endpoints:")
    print("   GET  /api/tools              - List all tools")
    print("   GET  /api/tools/<name>       - Get tool info")
    print("   POST /api/tools/<name>        - Call tool")
    print("   POST /api/tools              - Call tool (body)")
    print("   GET  /api/tasks              - List all tasks")
    print("   POST /api/tasks              - Submit background task")
    print("   GET  /api/tasks/<id>         - Get task status")
    print("   DELETE /api/tasks/<id>       - Delete task")
    print("   GET  /api/health             - Health check")
    print("   GET  /api/export/inventory    - Export inventory (CSV)")
    print("   GET  /api/export/orders       - Export orders (CSV)")
    print("   GET  /api/export/reviews      - Export reviews (CSV)")
    print("   GET  /api/export/competitors  - Export competitors (CSV)")
    print("   GET  /api/export/analytics    - Export analytics (CSV)")
    print("   GET  /api/export/report       - Export analytics report (PDF)")
    print("   GET  /api/history/<metric>    - Get historical data")
    print("   GET  /api/trends/<metric>     - Get trend analysis")
    print("   GET  /api/forecast/<sku>      - Get stockout prediction")
    print("   GET  /api/analytics/summary   - Get analytics summary")
    print("   POST /api/snapshot            - Take manual snapshot")
    print("   GET  /analytics              - Analytics page")
    print("")
    print("🌐 Language support: 中文 (Chinese) + English")
    print("")
    print("🔐 Default credentials: admin/admin123, manager/manager123, viewer/viewer123")
    print("")
    print("="*60)

TASK_QUEUE = {}
TASK_LOCK = threading.Lock()
TASK_EXECUTOR = ThreadPoolExecutor(max_workers=4)

def generate_task_id():
    return f"task_{uuid.uuid4().hex[:12]}"

def create_task(tool_name: str, parameters: dict) -> dict:
    task_id = generate_task_id()
    now = datetime.now()
    task = {
        'task_id': task_id,
        'tool_name': tool_name,
        'parameters': parameters,
        'status': 'pending',
        'result': None,
        'error': None,
        'created_at': now.isoformat(),
        'started_at': None,
        'completed_at': None,
        'progress': 0,
        'message': 'Task queued'
    }
    with TASK_LOCK:
        TASK_QUEUE[task_id] = task
    return task

def execute_background_task(task_id: str):
    task = None
    with TASK_LOCK:
        if task_id in TASK_QUEUE:
            task = TASK_QUEUE[task_id]
            task['status'] = 'running'
            task['started_at'] = datetime.now().isoformat()
            task['progress'] = 10
            task['message'] = 'Starting task execution'

    if task is None:
        return

    try:
        with TASK_LOCK:
            TASK_QUEUE[task_id]['progress'] = 30
            TASK_QUEUE[task_id]['message'] = 'Calling MCP tool'

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(call_mcp_tool(task['tool_name'], task['parameters']))
        finally:
            loop.close()

        with TASK_LOCK:
            if result.get('success'):
                TASK_QUEUE[task_id]['status'] = 'completed'
                TASK_QUEUE[task_id]['result'] = result.get('data')
                TASK_QUEUE[task_id]['message'] = 'Task completed successfully'
            else:
                TASK_QUEUE[task_id]['status'] = 'failed'
                TASK_QUEUE[task_id]['error'] = result.get('error', 'Unknown error')
                TASK_QUEUE[task_id]['message'] = 'Task failed'
            TASK_QUEUE[task_id]['completed_at'] = datetime.now().isoformat()
            TASK_QUEUE[task_id]['progress'] = 100

    except Exception as e:
        with TASK_LOCK:
            TASK_QUEUE[task_id]['status'] = 'failed'
            TASK_QUEUE[task_id]['error'] = str(e)
            TASK_QUEUE[task_id]['completed_at'] = datetime.now().isoformat()
            TASK_QUEUE[task_id]['message'] = f'Task error: {e!s}'

def submit_background_task(tool_name: str, parameters: dict) -> dict:
    task = create_task(tool_name, parameters)
    TASK_EXECUTOR.submit(execute_background_task, task['task_id'])
    return task

def get_task(task_id: str) -> dict | None:
    with TASK_LOCK:
        return TASK_QUEUE.get(task_id)

def get_all_tasks(status: str = None, limit: int = 100) -> list:
    with TASK_LOCK:
        tasks = list(TASK_QUEUE.values())
    if status:
        tasks = [t for t in tasks if t['status'] == status]
    tasks.sort(key=lambda x: x['created_at'], reverse=True)
    return tasks[:limit]

def get_active_tasks() -> list:
    return get_all_tasks(status='running') + get_all_tasks(status='pending')

def aggregate_low_stock_by_date(alerts: list[dict], dates: list[str]) -> dict[str, list]:
    critical_counts = dict.fromkeys(dates, 0)
    warning_counts = dict.fromkeys(dates, 0)

    for alert in alerts:
        if 'severity' in alert:
            severity = alert.get('severity', 'low')
            for i, date_str in enumerate(dates):
                if severity == 'critical':
                    critical_counts[date_str] += 1
                elif severity == 'warning':
                    warning_counts[date_str] += 1

    return {
        'labels': dates,
        'critical': [critical_counts[d] for d in dates],
        'warning': [warning_counts[d] for d in dates],
        'total_critical': sum(critical_counts.values()),
        'total_warning': sum(warning_counts.values())
    }

def aggregate_reviews_by_date(reviews: list[dict], dates: list[str]) -> dict[str, list]:
    rating_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    daily_counts = {d: {1: 0, 2: 0, 3: 0, 4: 0, 5: 0} for d in dates}

    for review in reviews:
        rating = review.get('rating', 0)
        if rating in rating_counts:
            rating_counts[rating] += 1
            review_date = review.get('review_date', '') or review.get('date', '')[:10]
            if review_date in daily_counts:
                daily_counts[review_date][rating] += 1

    daily_data = []
    for date_str in dates:
        daily_data.append({
            'date': date_str,
            '1': daily_counts[date_str][1],
            '2': daily_counts[date_str][2],
            '3': daily_counts[date_str][3],
            '4': daily_counts[date_str][4],
            '5': daily_counts[date_str][5]
        })

    return {
        'labels': dates,
        'rating_counts': rating_counts,
        'daily_data': daily_data,
        'total_reviews': sum(rating_counts.values()),
        'avg_rating': round(sum(r * c for r, c in rating_counts.items()) / sum(rating_counts.values()), 1) if sum(rating_counts.values()) > 0 else 0
    }

def generate_mock_historical_data(days: int) -> dict[str, Any]:
    dates = generate_date_range(days)
    base_orders = random.randint(5, 20)
    base_revenue = random.uniform(200, 500)

    order_counts = []
    revenues = []
    for i, date in enumerate(dates):
        day_factor = 1 + 0.3 * math.sin(i / len(dates) * 2 * math.pi)
        weekend_factor = 1.3 if datetime.strptime(date, '%Y-%m-%d').weekday() >= 5 else 1.0
        orders = int(base_orders * day_factor * weekend_factor * random.uniform(0.8, 1.2))
        revenue = orders * base_revenue * random.uniform(0.9, 1.1)
        order_counts.append(orders)
        revenues.append(round(revenue, 2))

    status_distribution = {
        'Delivered': random.randint(50, 100),
        'Shipped': random.randint(10, 30),
        'Pending': random.randint(5, 15),
        'Cancelled': random.randint(0, 5)
    }

    rating_distribution = {
        5: random.randint(40, 80),
        4: random.randint(15, 35),
        3: random.randint(5, 15),
        2: random.randint(2, 8),
        1: random.randint(1, 5)
    }

    return {
        'labels': dates,
        'order_counts': order_counts,
        'revenues': revenues,
        'status_distribution': status_distribution,
        'rating_distribution': rating_distribution,
        'total_orders': sum(order_counts),
        'total_revenue': round(sum(revenues), 2),
        'avg_daily_orders': round(sum(order_counts) / len(dates), 1),
        'avg_order_value': round(sum(revenues) / sum(order_counts), 2) if sum(order_counts) > 0 else 0,
        'is_mock_data': True
    }

@app.route('/admin')
@role_required('admin')
def admin_dashboard():
    lang = request.args.get('lang', 'cn')
    user = session.get('user')

    users = auth_service.get_all_users()
    recent_logs = audit_logger.get_recent_logs(limit=20)

    stats = {
        'total_users': len(users),
        'active_users': len([u for u in users if u.get('is_active', True)]),
        'active_sessions': 1,
        'api_usage_today': random.randint(100, 1000)
    }

    return render_template('admin.html',
                         lang=lang,
                         get_text=lambda key: get_text(lang, key),
                         stats=stats,
                         recent_logs=recent_logs,
                         request=request)

@app.route('/admin/users')
@role_required('admin')
def admin_users():
    lang = request.args.get('lang', 'cn')
    user = session.get('user')

    users = auth_service.get_all_users()
    search = request.args.get('search', '')
    role_filter = request.args.get('role', '')

    if search:
        users = [u for u in users if search.lower() in u.get('username', '').lower() or search.lower() in u.get('email', '').lower()]
    if role_filter:
        users = [u for u in users if u.get('role') == role_filter]

    return render_template('admin/users.html',
                         lang=lang,
                         get_text=lambda key: get_text(lang, key),
                         users=users,
                         search=search,
                         role_filter=role_filter,
                         roles=['admin', 'manager', 'viewer'],
                         request=request)

@app.route('/admin/users/create', methods=['POST'])
@role_required('admin')
def admin_create_user():
    lang = request.args.get('lang', 'cn')
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    role = request.form.get('role', 'viewer')

    result = auth_service.register_user(email, password, role)
    if result.get('success'):
        current_user = session.get('user')
        audit_logger.log(current_user['id'], current_user['username'], 'create_user', 'user', result['user_id'], {'email': email, 'role': role})
        flash(get_text(lang, 'user_created'), 'success')
    else:
        flash(result.get('error', get_text(lang, 'save_failed')), 'error')

    return redirect(url_for('admin_users', lang=lang))

@app.route('/admin/users/<user_id>/edit', methods=['POST'])
@role_required('admin')
def admin_edit_user(user_id):
    lang = request.args.get('lang', 'cn')
    updates = {}

    if request.form.get('username'):
        updates['username'] = request.form.get('username')
    if request.form.get('email'):
        updates['email'] = request.form.get('email')
    if request.form.get('role'):
        updates['role'] = request.form.get('role')
    if request.form.get('is_active'):
        updates['is_active'] = request.form.get('is_active') == 'true'
    if request.form.get('password'):
        updates['password'] = request.form.get('password')

    if auth_service.update_user(user_id, updates):
        current_user = session.get('user')
        audit_logger.log(current_user['id'], current_user['username'], 'update_user', 'user', user_id, updates)
        flash(get_text(lang, 'user_updated'), 'success')
    else:
        flash(get_text(lang, 'save_failed'), 'error')

    return redirect(url_for('admin_users', lang=lang))

@app.route('/admin/users/<user_id>/delete', methods=['POST'])
@role_required('admin')
def admin_delete_user(user_id):
    lang = request.args.get('lang', 'cn')

    if auth_service.delete_user(user_id):
        current_user = session.get('user')
        audit_logger.log(current_user['id'], current_user['username'], 'delete_user', 'user', user_id)
        flash(get_text(lang, 'user_deleted'), 'success')
    else:
        flash(get_text(lang, 'save_failed'), 'error')

    return redirect(url_for('admin_users', lang=lang))

@app.route('/admin/roles')
@role_required('admin')
def admin_roles():
    lang = request.args.get('lang', 'cn')
    user = session.get('user')

    roles_data = []
    for role in ['admin', 'manager', 'viewer']:
        roles_data.append({
            'name': role,
            'permissions': get_user_permissions(role)
        })

    all_permissions = [
        'read', 'write', 'delete', 'admin_access',
        'manage_users', 'manage_roles', 'view_audit_logs',
        'manage_settings', 'manage_inventory', 'manage_tasks',
        'manage_schedules', 'view_analytics', 'manage_notifications'
    ]

    return render_template('admin/roles.html',
                         lang=lang,
                         get_text=lambda key: get_text(lang, key),
                         roles_data=roles_data,
                         all_permissions=all_permissions,
                         request=request)

@app.route('/admin/roles/<role>/update', methods=['POST'])
@role_required('admin')
def admin_update_role(role):
    lang = request.args.get('lang', 'cn')
    permissions = request.form.getlist('permissions')

    flash(get_text(lang, 'user_updated'), 'success')

    return redirect(url_for('admin_roles', lang=lang))


@app.route('/api/api-keys', methods=['GET'])
@login_required
def api_list_keys():
    """List all API keys for the current user"""
    user_id = g.current_user['user_id']
    keys = list_user_api_keys(user_id)
    return jsonify({'success': True, 'keys': keys})


@app.route('/api/api-keys', methods=['POST'])
@login_required
def api_create_key():
    """Create a new API key for the current user"""
    user_id = g.current_user['user_id']
    data = request.get_json() or {}
    name = data.get('name', 'API Key')
    rate_limit = data.get('rate_limit', 60)

    result = create_api_key_for_user(user_id, name, rate_limit)

    if result:
        return jsonify({
            'success': True,
            'key_id': result['key_id'],
            'api_key': result['api_key'],
            'name': result['name'],
            'rate_limit': result['rate_limit'],
            'created_at': result['created_at'],
            'message': 'Store this API key securely. It will not be shown again.'
        }), 201
    else:
        return jsonify({'success': False, 'error': 'User not found'}), 404


@app.route('/api/api-keys/<key_id>', methods=['DELETE'])
@login_required
def api_revoke_key(key_id):
    """Revoke an API key"""
    user_id = g.current_user['user_id']

    if revoke_user_api_key(key_id, user_id):
        return jsonify({'success': True, 'message': 'API key revoked'})
    else:
        return jsonify({'success': False, 'error': 'API key not found'}), 404


@app.route('/admin/api-keys')
@role_required('admin')
def admin_api_keys():
    """Admin page to manage all API keys"""
    lang = request.args.get('lang', 'cn')
    users = auth_service.get_all_users()
    all_keys = []

    for user in users:
        user_keys = list_user_api_keys(user['user_id'])
        for key in user_keys:
            key['user_email'] = user['email']
            key['user_role'] = user['role']
            all_keys.append(key)

    return render_template('admin/api_keys.html',
                         lang=lang,
                         get_text=lambda key: get_text(lang, key),
                         keys=all_keys,
                         request=request)

@app.route('/admin/audit-logs')
@role_required('admin')
def admin_audit_logs():
    lang = request.args.get('lang', 'cn')
    user = session.get('user')

    logs = audit_logger.get_logs(limit=100)

    return render_template('admin/audit_logs.html',
                         lang=lang,
                         get_text=lambda key: get_text(lang, key),
                         logs=logs,
                         request=request)

@app.after_request
def add_rate_limit_headers_to_response(response):
    if hasattr(g, 'rate_limit_info'):
        response.headers['X-RateLimit-Limit'] = str(g.rate_limit_info.get('limit', 0))
        response.headers['X-RateLimit-Remaining'] = str(g.rate_limit_info.get('remaining', 0))
        response.headers['X-RateLimit-Reset'] = str(g.rate_limit_info.get('reset', 0))
    return response

app.run(host='0.0.0.0', port=5000, debug=True)
