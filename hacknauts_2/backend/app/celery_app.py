from celery import Celery

from .config import settings

celery_app = Celery("scalepilot", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_track_started=True,
    task_soft_time_limit=840,
    task_time_limit=900,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=False,
    broker_connection_timeout=2.0,
    broker_transport_options={
        "max_retries": 1,
        "socket_timeout": 1.5,
        "socket_connect_timeout": 1.5,
    },
)
