"""Bootstrap revision — no schema changes yet.

Revision ID: 000_bootstrap
Revises:
Create Date: 2026-06-14
"""

from typing import Sequence, Union

revision: str = "000_bootstrap"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
