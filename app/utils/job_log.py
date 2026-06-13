import logging
from typing import Any


class JobLogAdapter(logging.LoggerAdapter):
    """Prefix log records with job_id and pipeline stage."""

    def process(self, msg: str, kwargs: Any) -> tuple[str, Any]:
        extra = self.extra or {}
        job_id = extra.get("job_id", "-")
        stage = extra.get("stage", "-")
        return f"job_id={job_id} stage={stage} {msg}", kwargs


def job_logger(logger: logging.Logger, job_id: int, stage: str) -> JobLogAdapter:
    return JobLogAdapter(logger, {"job_id": job_id, "stage": stage})
