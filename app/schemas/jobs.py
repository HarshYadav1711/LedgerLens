from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import JobStatus


class JobCreatedResponse(BaseModel):
    job_id: int
    status: JobStatus
    message: str = "Job accepted for processing"


class JobStatusSummary(BaseModel):
    total_spend_inr: float
    total_spend_usd: float
    top_merchants: list[dict[str, Any]]
    anomaly_count: int
    narrative: str
    risk_level: str


class JobStatusResponse(BaseModel):
    job_id: int
    status: JobStatus
    filename: str
    row_count_raw: int
    row_count_clean: int | None = None
    created_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None
    summary: JobStatusSummary | None = None


class JobListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: int = Field(validation_alias="id")
    filename: str
    status: JobStatus
    row_count_raw: int
    row_count_clean: int | None = None
    created_at: datetime


class JobListResponse(BaseModel):
    jobs: list[JobListItem]
    total: int
