from celery import Celery

from app.config import get_settings
from app.utils.logging import configure_logging

settings = get_settings()
configure_logging()

celery_app = Celery(
    "ledgerlens",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
)

celery_app.autodiscover_tasks(["app.workers"])
import app.workers.processing  # noqa: E402, F401
