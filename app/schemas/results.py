from pydantic import BaseModel

from app.models.enums import JobStatus
from app.schemas.jobs import JobStatusSummary
from app.schemas.transactions import CategoryBreakdownItem, TopMerchantItem, TransactionOut


class JobResultsResponse(BaseModel):
    """Full structured output for a completed job."""

    job_id: int
    status: JobStatus
    transactions: list[TransactionOut]
    anomalies: list[TransactionOut]
    category_breakdown: list[CategoryBreakdownItem]
    top_merchants: list[TopMerchantItem]
    summary: JobStatusSummary
