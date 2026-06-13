from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import JobStatus


class Job(Base):
    """Processing job created from an uploaded CSV file."""

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=JobStatus.pending,
        index=True,
    )
    row_count_raw: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    row_count_clean: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction",
        back_populates="job",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    summary: Mapped["JobSummary | None"] = relationship(
        "JobSummary",
        back_populates="job",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Job id={self.id} status={self.status.value} filename={self.filename!r}>"
