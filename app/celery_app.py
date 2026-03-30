import os
from celery import Celery
from .config import settings

celery_app = Celery(
    'wecom_ops_console',
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=['app.tasks']
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=False,
    beat_schedule={
        'sync-celery-jobs': {
            'task': 'app.tasks.sync_celery_jobs',
            'schedule': 60.0,
        },
    }
)
