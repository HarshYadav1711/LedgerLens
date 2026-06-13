import logging

from app.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.processing.ping")
def ping() -> str:
    """Health-check task to verify worker connectivity."""
    logger.info("Worker ping received")
    return "pong"


@celery_app.task(name="app.workers.processing.process_job", bind=True)
def process_job(self, job_id: int, file_path: str) -> None:
    """Run the full transaction processing pipeline for a job.

    Pipeline (to be implemented):
      1. Clean CSV data
      2. Detect anomalies
      3. Batch-classify missing categories via Ollama
      4. Generate narrative summary via Ollama
    """
    logger.info("process_job placeholder called for job_id=%s path=%s", job_id, file_path)
