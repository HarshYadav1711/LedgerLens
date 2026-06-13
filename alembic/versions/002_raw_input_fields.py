"""Add raw CSV fields to transactions for traceability.

Revision ID: 002_raw_input_fields
Revises: 001_initial_schema
Create Date: 2026-06-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_raw_input_fields"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("transactions", sa.Column("raw_date", sa.String(length=64), nullable=True))
    op.add_column("transactions", sa.Column("raw_amount", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("transactions", "raw_amount")
    op.drop_column("transactions", "raw_date")
