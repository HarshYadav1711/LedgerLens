import logging
import uuid
from collections import defaultdict
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Job, JobStatus, JobSummary, Transaction
from app.schemas import (
    CategoryBreakdownItem,
    JobCreatedResponse,
    JobListItem,
    JobListResponse,
    JobResultsResponse,
    JobStatusResponse,
    JobStatusSummary,
    TransactionOut,
)
from app.services.cleaning import validate_csv_content
from app.workers.processing import process_job

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])


def _ensure_upload_dir() -> Path:
    upload_dir = Path(get_settings().upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def _summary_from_model(summary: JobSummary | None) -> JobStatusSummary | None:
    if summary is None:
        return None
    return JobStatusSummary(
        total_spend_inr=summary.total_spend_inr,
        total_spend_usd=summary.total_spend_usd,
        top_merchants=summary.top_merchants,
        anomaly_count=summary.anomaly_count,
        narrative=summary.narrative,
        risk_level=summary.risk_level,
    )


def _category_breakdown(transactions: list[Transaction]) -> list[CategoryBreakdownItem]:
    totals: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)

    for txn in transactions:
        category = txn.llm_category or txn.category or "Uncategorised"
        counts[category] += 1
        if txn.amount is not None:
            totals[category] += float(txn.amount)

    return [
        CategoryBreakdownItem(
            category=category,
            count=counts[category],
            total_amount=round(totals[category], 2),
        )
        for category in sorted(counts)
    ]


def _get_job_or_404(job_id: int, db: Session) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return job


@router.get("", response_model=JobListResponse)
def list_jobs(
    status: JobStatus | None = Query(default=None, description="Filter by job status"),
    db: Session = Depends(get_db),
) -> JobListResponse:
    query = db.query(Job).order_by(Job.created_at.desc())
    if status is not None:
        query = query.filter(Job.status == status)

    jobs = query.all()
    items = [
        JobListItem(
            job_id=job.id,
            filename=job.filename,
            status=job.status,
            row_count_raw=job.row_count_raw,
            row_count_clean=job.row_count_clean,
            created_at=job.created_at,
        )
        for job in jobs
    ]
    return JobListResponse(jobs=items, total=len(items))


@router.post("/upload", response_model=JobCreatedResponse, status_code=202)
async def upload_job(
    file: UploadFile = File(..., description="CSV file of transactions"),
    db: Session = Depends(get_db),
) -> JobCreatedResponse:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    try:
        _, rows = validate_csv_content(content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    job = Job(
        filename=file.filename,
        status=JobStatus.pending,
        row_count_raw=len(rows),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    upload_dir = _ensure_upload_dir()
    stored_name = f"{job.id}_{uuid.uuid4().hex}.csv"
    file_path = upload_dir / stored_name
    file_path.write_bytes(content)

    process_job.delay(job.id, str(file_path))
    logger.info("Enqueued job_id=%d filename=%s rows=%d", job.id, file.filename, len(rows))

    return JobCreatedResponse(job_id=job.id, status=job.status)


@router.get("/{job_id}/status", response_model=JobStatusResponse)
def get_job_status(job_id: int, db: Session = Depends(get_db)) -> JobStatusResponse:
    job = _get_job_or_404(job_id, db)

    summary = _summary_from_model(job.summary) if job.status == JobStatus.completed else None

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


@router.get("/{job_id}/results", response_model=JobResultsResponse)
def get_job_results(job_id: int, db: Session = Depends(get_db)) -> JobResultsResponse:
    job = _get_job_or_404(job_id, db)

    if job.status != JobStatus.completed:
        raise HTTPException(
            status_code=409,
            detail=f"Job {job_id} is not completed (current status: {job.status.value})",
        )

    transactions = (
        db.query(Transaction)
        .filter(Transaction.job_id == job_id)
        .order_by(Transaction.id)
        .all()
    )
    txn_out = [TransactionOut.model_validate(txn) for txn in transactions]
    anomalies = [txn for txn in txn_out if txn.is_anomaly]

    return JobResultsResponse(
        job_id=job.id,
        status=job.status,
        transactions=txn_out,
        anomalies=anomalies,
        category_breakdown=_category_breakdown(transactions),
        summary=_summary_from_model(job.summary),
    )
