"""Initial schema: jobs, transactions, job_summaries.

Revision ID: 001_initial_schema
Revises: 000_bootstrap
Create Date: 2026-06-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_initial_schema"
down_revision: Union[str, None] = "000_bootstrap"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

job_status = postgresql.ENUM(
    "pending",
    "processing",
    "completed",
    "failed",
    name="job_status",
    create_type=False,
)


def upgrade() -> None:
    job_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("status", job_status, nullable=False, server_default="pending"),
        sa.Column("row_count_raw", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("row_count_clean", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_created_at", "jobs", ["created_at"])

    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("txn_id", sa.String(length=128), nullable=True),
        sa.Column("date", sa.String(length=32), nullable=True),
        sa.Column("merchant", sa.String(length=512), nullable=True),
        sa.Column("amount", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column("category", sa.String(length=128), nullable=True),
        sa.Column("account_id", sa.String(length=128), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_anomaly", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("anomaly_reason", sa.Text(), nullable=True),
        sa.Column("llm_category", sa.String(length=128), nullable=True),
        sa.Column("llm_raw_response", sa.Text(), nullable=True),
        sa.Column("llm_failed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_transactions_job_id", "transactions", ["job_id"])
    op.create_index("ix_transactions_account_id", "transactions", ["account_id"])
    op.create_index("ix_transactions_is_anomaly", "transactions", ["is_anomaly"])

    op.create_table(
        "job_summaries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("total_spend_inr", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_spend_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column(
            "top_merchants",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("anomaly_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("narrative", sa.Text(), nullable=False, server_default=""),
        sa.Column("risk_level", sa.String(length=16), nullable=False, server_default="low"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", name="uq_job_summaries_job_id"),
    )
    op.create_index("ix_job_summaries_job_id", "job_summaries", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_job_summaries_job_id", table_name="job_summaries")
    op.drop_table("job_summaries")
    op.drop_index("ix_transactions_is_anomaly", table_name="transactions")
    op.drop_index("ix_transactions_account_id", table_name="transactions")
    op.drop_index("ix_transactions_job_id", table_name="transactions")
    op.drop_table("transactions")
    op.drop_index("ix_jobs_created_at", table_name="jobs")
    op.drop_index("ix_jobs_status", table_name="jobs")
    op.drop_table("jobs")
    job_status.drop(op.get_bind(), checkfirst=True)
