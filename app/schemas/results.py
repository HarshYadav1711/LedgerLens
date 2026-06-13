from pydantic import BaseModel

from app.models.enums import JobStatus
from app.schemas.jobs import JobStatusSummary
from app.schemas.transactions import CategoryBreakdownItem, TransactionOut


class JobResultsResponse(BaseModel):
    job_id: int
    status: JobStatus
    transactions: list[TransactionOut]
    anomalies: list[TransactionOut]
    category_breakdown: list[CategoryBreakdownItem]
    summary: JobStatusSummary | None = None
