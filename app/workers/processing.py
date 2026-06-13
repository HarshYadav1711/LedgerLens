import logging
from pathlib import Path

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import Job, JobStatus, JobSummary, Transaction
from app.services.anomaly import detect_anomalies
from app.services.classification import classify_missing_categories
from app.services.cleaning import clean_rows, validate_csv_content
from app.services.job_lifecycle import transition_job
from app.services.summary import build_summary
from app.utils.job_log import job_logger

logger = logging.getLogger(__name__)

STAGES = ("cleaning", "anomaly_detection", "classification", "summary", "persist")


def _persist_transactions(db, job_id: int, rows: list) -> None:
    db.query(Transaction).filter(Transaction.job_id == job_id).delete()
    for row in rows:
        db.add(
            Transaction(
                job_id=job_id,
                txn_id=row.get("txn_id"),
                date=row.get("date"),
                merchant=row.get("merchant"),
                amount=row.get("amount"),
                currency=row.get("currency"),
                status=row.get("status"),
                category=row.get("category"),
                account_id=row.get("account_id"),
                notes=row.get("notes"),
                raw_date=row.get("raw_date"),
                raw_amount=row.get("raw_amount"),
                is_anomaly=row.get("is_anomaly", False),
                anomaly_reason=row.get("anomaly_reason"),
                llm_category=row.get("llm_category"),
                llm_raw_response=row.get("llm_raw_response"),
                llm_failed=row.get("llm_failed", False),
            )
        )


def _persist_summary(db, job_id: int, summary_data: dict) -> None:
    existing = db.query(JobSummary).filter(JobSummary.job_id == job_id).first()
    if existing is not None:
        db.delete(existing)

    db.add(
        JobSummary(
            job_id=job_id,
            total_spend_inr=summary_data["total_spend_inr"],
            total_spend_usd=summary_data["total_spend_usd"],
            top_merchants=summary_data["top_merchants"],
            anomaly_count=summary_data["anomaly_count"],
            narrative=summary_data["narrative"],
            risk_level=summary_data["risk_level"],
        )
    )


@celery_app.task(name="app.workers.processing.ping")
def ping() -> str:
    """Health-check task to verify worker connectivity."""
    logger.info("Worker ping received")
    return "pong"


@celery_app.task(name="app.workers.processing.process_job", bind=True, max_retries=0)
def process_job(self, job_id: int, file_path: str) -> None:
    """Run the full transaction processing pipeline for a job."""
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if job is None:
            logger.error("job_id=%s stage=init message=job_not_found", job_id)
            return

        transition_job(db, job, JobStatus.processing)
        log = job_logger(logger, job_id, "init")
        log.info("processing_started file=%s", file_path)

        content = Path(file_path).read_bytes()
        _, raw_rows = validate_csv_content(content)

        log = job_logger(logger, job_id, STAGES[0])
        log.info("raw_rows=%d", len(raw_rows))
        cleaned = clean_rows(raw_rows)

        log = job_logger(logger, job_id, STAGES[1])
        log.info("cleaned_rows=%d", len(cleaned))
        cleaned = detect_anomalies(cleaned)

        log = job_logger(logger, job_id, STAGES[2])
        cleaned = classify_missing_categories(cleaned, job_id=job_id)

        log = job_logger(logger, job_id, STAGES[3])
        summary_data = build_summary(cleaned)

        log = job_logger(logger, job_id, STAGES[4])
        _persist_transactions(db, job_id, cleaned)
        _persist_summary(db, job_id, summary_data)

        transition_job(
            db,
            job,
            JobStatus.completed,
            row_count_clean=len(cleaned),
        )

        llm_failed_count = sum(1 for row in cleaned if row.get("llm_failed"))
        log = job_logger(logger, job_id, "complete")
        log.info(
            "transactions=%d anomalies=%d llm_failed=%d",
            len(cleaned),
            summary_data["anomaly_count"],
            llm_failed_count,
        )

    except Exception as exc:
        logger.exception("job_id=%s stage=error message=%s", job_id, exc)
        db.rollback()
        job = db.get(Job, job_id)
        if job is not None:
            transition_job(db, job, JobStatus.failed, error_message=str(exc))
    finally:
        db.close()
