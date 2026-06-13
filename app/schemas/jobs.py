from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import JobStatus
from app.schemas.transactions import TopMerchantItem


class JobCreatedResponse(BaseModel):
    job_id: int
    status: JobStatus
    message: str = "Job accepted for processing"


class JobStatusSummary(BaseModel):
    """Compact structured summary for completed jobs."""

    total_spend_inr: float
    total_spend_usd: float
    top_merchants: list[TopMerchantItem]
    anomaly_count: int
    narrative: str
    risk_level: str

    @classmethod
    def from_stored(cls, data: dict[str, Any]) -> "JobStatusSummary":
        """Build from a persisted JobSummary row."""
        return cls(
            total_spend_inr=data["total_spend_inr"],
            total_spend_usd=data["total_spend_usd"],
            top_merchants=[
                TopMerchantItem(**item) if isinstance(item, dict) else item
                for item in data["top_merchants"]
            ],
            anomaly_count=data["anomaly_count"],
            narrative=data["narrative"],
            risk_level=data["risk_level"],
        )


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
