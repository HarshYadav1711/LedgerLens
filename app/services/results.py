"""Assemble API responses from persisted job data."""

import logging

from sqlalchemy import case
from sqlalchemy.orm import Session

from app.models import Job, JobStatus, JobSummary, Transaction
from app.schemas.jobs import JobStatusResponse, JobStatusSummary
from app.schemas.results import JobResultsResponse
from app.schemas.transactions import TransactionOut
from app.services.aggregates import (
    compute_anomaly_count,
    compute_category_breakdown,
    compute_top_merchants,
)

logger = logging.getLogger(__name__)


def _summary_to_schema(summary: JobSummary) -> JobStatusSummary:
    return JobStatusSummary.from_stored(
        {
            "total_spend_inr": summary.total_spend_inr,
            "total_spend_usd": summary.total_spend_usd,
            "top_merchants": summary.top_merchants,
            "anomaly_count": summary.anomaly_count,
            "narrative": summary.narrative,
            "risk_level": summary.risk_level,
        }
    )


def _transaction_sort_key(txn: Transaction) -> tuple:
    """Deterministic ordering: txn_id, date, then database id."""
    return (
        txn.txn_id or "",
        txn.date or "",
        txn.id,
    )


def _load_transactions(db: Session, job_id: int) -> list[Transaction]:
    return (
        db.query(Transaction)
        .filter(Transaction.job_id == job_id)
        .order_by(
            case((Transaction.txn_id.is_(None), 1), else_=0),
            Transaction.txn_id,
            case((Transaction.date.is_(None), 1), else_=0),
            Transaction.date,
            Transaction.id,
        )
        .all()
    )


def _sort_transactions(transactions: list[Transaction]) -> list[Transaction]:
    return sorted(transactions, key=_transaction_sort_key)


def assemble_status_response(job: Job) -> JobStatusResponse:
    """Build the status payload; includes compact summary when job is completed."""
    summary = None
    if job.status == JobStatus.completed and job.summary is not None:
        summary = _summary_to_schema(job.summary)

    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        filename=job.filename,
        row_count_raw=job.row_count_raw,
        row_count_clean=job.row_count_clean,
        created_at=job.created_at,
        completed_at=job.completed_at,
        error_message=job.error_message,
        summary=summary,
    )


def assemble_results_response(job: Job, transactions: list[Transaction]) -> JobResultsResponse:
    """Combine transactions, anomalies, breakdown, and stored summary into one response."""
    if job.summary is None:
        raise ValueError(f"Job {job.id} has no persisted summary")

    ordered = _sort_transactions(transactions)
    txn_out = [TransactionOut.model_validate(txn) for txn in ordered]
    anomalies = [txn for txn in txn_out if txn.is_anomaly]
    category_breakdown = compute_category_breakdown(ordered)
    top_merchants = compute_top_merchants(ordered)
    summary = _summary_to_schema(job.summary)

    logger.debug(
        "job_id=%s stage=results_assembly transactions=%d anomalies=%d categories=%d",
        job.id,
        len(txn_out),
        compute_anomaly_count(ordered),
        len(category_breakdown),
    )

    return JobResultsResponse(
        job_id=job.id,
        status=job.status,
        transactions=txn_out,
        anomalies=anomalies,
        category_breakdown=category_breakdown,
        top_merchants=top_merchants,
        summary=summary,
    )


def assemble_results_for_job(db: Session, job: Job) -> JobResultsResponse:
    """Load transactions and assemble the full results response."""
    transactions = _load_transactions(db, job.id)
    return assemble_results_response(job, transactions)
