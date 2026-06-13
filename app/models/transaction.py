from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Transaction(Base):
    """Cleaned and enriched transaction row belonging to a job."""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    txn_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    merchant: Mapped[str | None] = mapped_column(String(512), nullable=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    account_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_anomaly: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    anomaly_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    llm_raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_failed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    job: Mapped["Job"] = relationship("Job", back_populates="transactions")

    def __repr__(self) -> str:
        return f"<Transaction id={self.id} job_id={self.job_id} txn_id={self.txn_id!r}>"
