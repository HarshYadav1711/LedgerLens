import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Job, JobStatus
from app.schemas import (
    JobCreatedResponse,
    JobListItem,
    JobListResponse,
    JobResultsResponse,
    JobStatusResponse,
)
from app.services.cleaning import CsvValidationError, validate_csv_content
from app.services.results import assemble_results_for_job, assemble_status_response
from app.workers.processing import process_job

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])


def _ensure_upload_dir() -> Path:
    upload_dir = Path(get_settings().upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


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
    except CsvValidationError as exc:
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
    return assemble_status_response(job)


@router.get("/{job_id}/results", response_model=JobResultsResponse)
def get_job_results(job_id: int, db: Session = Depends(get_db)) -> JobResultsResponse:
    job = _get_job_or_404(job_id, db)

    if job.status != JobStatus.completed:
        raise HTTPException(
            status_code=409,
            detail=f"Job {job_id} is not completed (current status: {job.status.value})",
        )

    if job.summary is None:
        raise HTTPException(
            status_code=500,
            detail=f"Job {job_id} is completed but has no persisted summary",
        )

    return assemble_results_for_job(db, job)
