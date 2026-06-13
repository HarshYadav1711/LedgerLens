from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class JobSummary(Base):
    """Structured aggregate output for a completed job."""

    __tablename__ = "job_summaries"
    __table_args__ = (UniqueConstraint("job_id", name="uq_job_summaries_job_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    total_spend_inr: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_spend_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    top_merchants: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    anomaly_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    narrative: Mapped[str] = mapped_column(Text, nullable=False, default="")
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False, default="low")

    job: Mapped["Job"] = relationship("Job", back_populates="summary")

    def __repr__(self) -> str:
        return f"<JobSummary id={self.id} job_id={self.job_id} risk_level={self.risk_level!r}>"
