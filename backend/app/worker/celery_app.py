"""Celery application configuration with Redis broker."""

from celery import Celery

from app.config import settings

celery_app = Celery(
    "avelon_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    task_soft_time_limit=600,   # 10 min soft limit
    task_time_limit=660,        # 11 min hard limit
    task_default_retry_delay=30,
    task_max_retries=3,
    result_expires=86400,       # 24 hours
)
