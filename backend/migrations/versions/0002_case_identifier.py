"""Add user-facing case identifiers.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("cases", sa.Column("case_identifier", sa.String(100), nullable=True))
    op.execute("UPDATE cases SET case_identifier = id::text WHERE case_identifier IS NULL")
    op.alter_column("cases", "case_identifier", nullable=False)
    op.create_unique_constraint("uq_cases_case_identifier", "cases", ["case_identifier"])


def downgrade() -> None:
    op.drop_constraint("uq_cases_case_identifier", "cases", type_="unique")
    op.drop_column("cases", "case_identifier")
