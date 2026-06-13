import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Job
from app.models.enums import JobStatus

logger = logging.getLogger(__name__)


def transition_job(
    db: Session,
    job: Job,
    new_status: JobStatus,
    *,
    error_message: str | None = None,
    row_count_clean: int | None = None,
) -> None:
    """Apply a job status transition and log it for traceability."""
    previous = job.status
    job.status = new_status

    if error_message is not None:
        job.error_message = error_message
    elif new_status not in {JobStatus.failed}:
        job.error_message = None

    if row_count_clean is not None:
        job.row_count_clean = row_count_clean

    if new_status in {JobStatus.completed, JobStatus.failed}:
        job.completed_at = datetime.now(timezone.utc)

    db.commit()
    logger.info(
        "job_id=%s status_transition %s->%s",
        job.id,
        previous.value,
        new_status.value,
    )
