"""
Celery Tasks for Cross-Border Seller Operations
Background tasks that wrap MCP tools for scheduled execution
"""
import asyncio
import json
import logging
import traceback
from datetime import datetime
from typing import Any

from celery_app import celery_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_async_coro(coro):
    """Helper to run async coroutines in sync context"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def save_task_result(task_name: str, task_id: str, status: str, result: Any = None, error: str = None):
    """Store task results in database for persistence"""
    try:
        import sqlite3
        from pathlib import Path

        DB_PATH = Path(__file__).parent / "seller_data.db"
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS celery_task_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_name TEXT,
                celery_task_id TEXT,
                status TEXT,
                result TEXT,
                error TEXT,
                created_at TEXT,
                completed_at TEXT
            )
        ''')

        now = datetime.now().isoformat()
        result_json = json.dumps(result) if result is not None else None

        cursor.execute('''
            INSERT INTO celery_task_results
            (task_name, celery_task_id, status, result, error, created_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (task_name, task_id, status, result_json, error, now, now))

        conn.commit()
        conn.close()
        logger.info(f"Task result saved: {task_name} - {status}")
    except Exception as e:
        logger.error(f"Failed to save task result: {e}")


@celery_app.task(bind=True, name='tasks.sync_inventory_task', max_retries=3, default_retry_delay=60)
def sync_inventory_task(self, sku: str | None = None) -> dict[str, Any]:
    """
    Sync inventory from 1688 to Amazon
    Compares stock levels and flags mismatches
    """
    task_id = self.request.id
    logger.info(f"[{task_id}] Starting inventory sync task")

    try:
        from server import ResponseFormat, SyncInventoryInput, sync_inventory

        if sku:
            input_params = SyncInventoryInput(
                sku=sku,
                response_format=ResponseFormat.JSON
            )
            result = run_async_coro(sync_inventory(input_params))
        else:
            from server import GetStaleProductsInput, ResponseFormat, list_all_products
            products_result = run_async_coro(list_all_products(GetStaleProductsInput(hours=24, response_format=ResponseFormat.JSON)))
            products_data = json.loads(products_result)
            skus = [p.get('sku') for p in products_data.get('products', [])[:10]]
            results = []
            for product_sku in skus:
                try:
                    input_params = SyncInventoryInput(
                        sku=product_sku,
                        response_format=ResponseFormat.JSON
                    )
                    result = run_async_coro(sync_inventory(input_params))
                    results.append({'sku': product_sku, 'result': result})
                except Exception as e:
                    results.append({'sku': product_sku, 'error': str(e)})
            result = {'synced_products': results}

        save_task_result('sync_inventory_task', task_id, 'completed', result)
        logger.info(f"[{task_id}] Inventory sync completed successfully")
        return {'success': True, 'task_id': task_id, 'result': result}

    except Exception as e:
        error_msg = f"Inventory sync failed: {e!s}"
        logger.error(f"[{task_id}] {error_msg}")
        logger.error(traceback.format_exc())
        save_task_result('sync_inventory_task', task_id, 'failed', error=error_msg)

        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        return {'success': False, 'task_id': task_id, 'error': error_msg}


@celery_app.task(bind=True, name='tasks.check_low_stock_task', max_retries=3, default_retry_delay=60)
def check_low_stock_task(self, threshold: int = 10, platform: str = 'both') -> dict[str, Any]:
    """
    Check for low stock alerts
    Returns all SKUs where stock is below threshold
    """
    task_id = self.request.id
    logger.info(f"[{task_id}] Starting low stock check (threshold: {threshold}, platform: {platform})")

    try:
        from server import GetLowStockAlertsInput, ResponseFormat, get_low_stock_alerts

        input_params = GetLowStockAlertsInput(
            threshold=threshold,
            platform=platform,
            response_format=ResponseFormat.JSON
        )
        result = run_async_coro(get_low_stock_alerts(input_params))

        save_task_result('check_low_stock_task', task_id, 'completed', result)
        logger.info(f"[{task_id}] Low stock check completed successfully")
        return {'success': True, 'task_id': task_id, 'result': result}

    except Exception as e:
        error_msg = f"Low stock check failed: {e!s}"
        logger.error(f"[{task_id}] {error_msg}")
        logger.error(traceback.format_exc())
        save_task_result('check_low_stock_task', task_id, 'failed', error=error_msg)

        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        return {'success': False, 'task_id': task_id, 'error': error_msg}


@celery_app.task(bind=True, name='tasks.sync_prices_task', max_retries=3, default_retry_delay=60)
def sync_prices_task(self, sku: str | None = None, target_margin: float = 25.0) -> dict[str, Any]:
    """
    Sync prices between 1688 and Amazon
    Compares cost-based pricing against current Amazon prices
    """
    task_id = self.request.id
    logger.info(f"[{task_id}] Starting price sync task (sku: {sku}, margin: {target_margin}%)")

    try:
        from server import ResponseFormat, SyncPriceInput, sync_price

        if sku:
            input_params = SyncPriceInput(
                sku=sku,
                target_margin_percent=target_margin,
                shipping_cost_usd=2.0,
                response_format=ResponseFormat.JSON
            )
            result = run_async_coro(sync_price(input_params))
        else:
            from server import GetStaleProductsInput, ResponseFormat, list_all_products
            products_result = run_async_coro(list_all_products(GetStaleProductsInput(hours=24, response_format=ResponseFormat.JSON)))
            products_data = json.loads(products_result)
            skus = [p.get('sku') for p in products_data.get('products', [])[:10]]
            results = []
            for product_sku in skus:
                try:
                    input_params = SyncPriceInput(
                        sku=product_sku,
                        target_margin_percent=target_margin,
                        shipping_cost_usd=2.0,
                        response_format=ResponseFormat.JSON
                    )
                    result = run_async_coro(sync_price(input_params))
                    results.append({'sku': product_sku, 'result': result})
                except Exception as e:
                    results.append({'sku': product_sku, 'error': str(e)})
            result = {'synced_products': results}

        save_task_result('sync_prices_task', task_id, 'completed', result)
        logger.info(f"[{task_id}] Price sync completed successfully")
        return {'success': True, 'task_id': task_id, 'result': result}

    except Exception as e:
        error_msg = f"Price sync failed: {e!s}"
        logger.error(f"[{task_id}] {error_msg}")
        logger.error(traceback.format_exc())
        save_task_result('sync_prices_task', task_id, 'failed', error=error_msg)

        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        return {'success': False, 'task_id': task_id, 'error': error_msg}


@celery_app.task(bind=True, name='tasks.fetch_reviews_task', max_retries=3, default_retry_delay=60)
def fetch_reviews_task(self, days: int = 7, include_supplier_flags: bool = True) -> dict[str, Any]:
    """
    Fetch latest product reviews from Amazon
    Returns reviews that need attention
    """
    task_id = self.request.id
    logger.info(f"[{task_id}] Starting reviews fetch (days: {days})")

    try:
        from server import GetReviewAlertsInput, ResponseFormat, get_review_alerts

        input_params = GetReviewAlertsInput(
            days=days,
            include_supplier_flags=include_supplier_flags,
            response_format=ResponseFormat.JSON
        )
        result = run_async_coro(get_review_alerts(input_params))

        save_task_result('fetch_reviews_task', task_id, 'completed', result)
        logger.info(f"[{task_id}] Reviews fetch completed successfully")
        return {'success': True, 'task_id': task_id, 'result': result}

    except Exception as e:
        error_msg = f"Reviews fetch failed: {e!s}"
        logger.error(f"[{task_id}] {error_msg}")
        logger.error(traceback.format_exc())
        save_task_result('fetch_reviews_task', task_id, 'failed', error=error_msg)

        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        return {'success': False, 'task_id': task_id, 'error': error_msg}


@celery_app.task(bind=True, name='tasks.generate_daily_report_task', max_retries=3, default_retry_delay=60)
def generate_daily_report_task(self, days: int = 1) -> dict[str, Any]:
    """
    Generate daily summary report
    Aggregates inventory, orders, reviews, and revenue data
    """
    task_id = self.request.id
    logger.info(f"[{task_id}] Starting daily report generation (days: {days})")

    try:
        report_data = {
            'generated_at': datetime.now().isoformat(),
            'period_days': days,
            'sections': {}
        }

        from server import (
            GetLowStockAlertsInput,
            GetOrdersAmazonInput,
            GetReviewAlertsInput,
            ResponseFormat,
            get_low_stock_alerts,
            get_orders_amazon,
            get_review_alerts,
        )

        try:
            low_stock_params = GetLowStockAlertsInput(
                threshold=10,
                platform='both',
                response_format=ResponseFormat.JSON
            )
            low_stock_result = run_async_coro(get_low_stock_alerts(low_stock_params))
            report_data['sections']['low_stock'] = json.loads(low_stock_result)
        except Exception as e:
            report_data['sections']['low_stock'] = {'error': str(e)}

        try:
            orders_params = GetOrdersAmazonInput(
                days=days,
                limit=100,
                response_format=ResponseFormat.JSON
            )
            orders_result = run_async_coro(get_orders_amazon(orders_params))
            report_data['sections']['orders'] = json.loads(orders_result)
        except Exception as e:
            report_data['sections']['orders'] = {'error': str(e)}

        try:
            reviews_params = GetReviewAlertsInput(
                days=days,
                include_supplier_flags=True,
                response_format=ResponseFormat.JSON
            )
            reviews_result = run_async_coro(get_review_alerts(reviews_params))
            report_data['sections']['reviews'] = json.loads(reviews_result)
        except Exception as e:
            report_data['sections']['reviews'] = {'error': str(e)}

        report_data['summary'] = {
            'low_stock_count': report_data['sections'].get('low_stock', {}).get('total_alerts', 0),
            'orders_count': len(report_data['sections'].get('orders', {}).get('orders', [])),
            'reviews_alerts': report_data['sections'].get('reviews', {}).get('total_alerts', 0)
        }

        save_task_result('generate_daily_report_task', task_id, 'completed', report_data)
        logger.info(f"[{task_id}] Daily report generated successfully")
        return {'success': True, 'task_id': task_id, 'result': report_data}

    except Exception as e:
        error_msg = f"Daily report generation failed: {e!s}"
        logger.error(f"[{task_id}] {error_msg}")
        logger.error(traceback.format_exc())
        save_task_result('generate_daily_report_task', task_id, 'failed', error=error_msg)

        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        return {'success': False, 'task_id': task_id, 'error': error_msg}


@celery_app.task(name='tasks.get_task_status')
def get_task_status(task_id: str) -> dict[str, Any]:
    """Get status of a Celery task"""
    task = celery_app.AsyncResult(task_id)
    return {
        'task_id': task_id,
        'status': task.status,
        'result': task.result if task.ready() else None,
        'info': str(task.info) if task.info else None
    }


@celery_app.task(name='tasks.list_scheduled_tasks')
def list_scheduled_tasks() -> list[dict[str, Any]]:
    """List all registered periodic tasks"""
    from celery_app import celery_app
    inspect = celery_app.control.inspect()

    registered = inspect.registered() or {}
    active = inspect.active() or {}
    scheduled = inspect.scheduled() or {}

    return {
        'registered_tasks': list(registered.keys()) if registered else [],
        'active_tasks': active,
        'scheduled_tasks': scheduled
    }


celery_app.conf.beat_schedule = {
    'check-low-stock-every-hour': {
        'task': 'tasks.check_low_stock_task',
        'schedule': 3600.0,
        'args': (10, 'both'),
    },
    'sync-inventory-every-6-hours': {
        'task': 'tasks.sync_inventory_task',
        'schedule': 21600.0,
        'args': (),
    },
    'sync-prices-every-4-hours': {
        'task': 'tasks.sync_prices_task',
        'schedule': 14400.0,
        'args': (None, 25.0),
    },
    'fetch-reviews-every-2-hours': {
        'task': 'tasks.fetch_reviews_task',
        'schedule': 7200.0,
        'args': (7, True),
    },
    'generate-daily-report-midnight': {
        'task': 'tasks.generate_daily_report_task',
        'schedule': 86400.0,
        'args': (1,),
    },
}
