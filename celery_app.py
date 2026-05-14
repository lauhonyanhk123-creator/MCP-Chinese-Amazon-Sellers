"""
Celery Application Configuration
Background task scheduling for cross-border seller operations
"""
import os

from celery import Celery
from kombu import Exchange, Queue

REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
BROKER_URL = os.getenv('CELERY_BROKER_URL', REDIS_URL)
RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', REDIS_URL)

def create_celery_app():
    """Create and configure Celery application"""
    app = Celery(
        'cross_border_seller',
        broker=BROKER_URL,
        backend=RESULT_BACKEND,
        include=['tasks']
    )

    app.conf.update(
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='UTC',
        enable_utc=True,
        task_track_started=True,
        task_time_limit=3600,
        task_soft_time_limit=3000,
        worker_prefetch_multiplier=1,
        worker_max_tasks_per_child=100,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        task_ignore_result=False,
        result_expires=86400,
        task_default_queue='default',
        task_default_exchange='tasks',
        task_default_routing_key='task',
        task_routes={
            'tasks.sync_inventory_task': {'queue': 'inventory'},
            'tasks.check_low_stock_task': {'queue': 'inventory'},
            'tasks.sync_prices_task': {'queue': 'pricing'},
            'tasks.fetch_reviews_task': {'queue': 'reviews'},
            'tasks.generate_daily_report_task': {'queue': 'reports'},
        },
        task_annotations={
            '*': {
                'rate_limit': '10/m',
                'max_retries': 3,
            }
        },
        task_default_retry_delay=60,
        task_max_retries=3,
    )

    app.conf.task_queues = (
        Queue('default', Exchange('tasks'), routing_key='task'),
        Queue('inventory', Exchange('inventory'), routing_key='inventory'),
        Queue('pricing', Exchange('pricing'), routing_key='pricing'),
        Queue('reviews', Exchange('reviews'), routing_key='reviews'),
        Queue('reports', Exchange('reports'), routing_key='reports'),
    )

    class Config:
        BROKER_URL = BROKER_URL
        RESULT_BACKEND = RESULT_BACKEND
        REDIS_URL = REDIS_URL
        SQLITE_DB = 'seller_data.db'

    app.config_from_object(Config)

    return app

celery_app = create_celery_app()

if __name__ == '__main__':
    celery_app.start()
