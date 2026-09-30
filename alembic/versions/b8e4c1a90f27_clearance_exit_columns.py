"""add clearance gate-exit columns

Revision ID: b8e4c1a90f27
Revises: a7c3e91f4b20
Create Date: 2026-09-30 11:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8e4c1a90f27"
down_revision: Union[str, Sequence[str], None] = "a7c3e91f4b20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "clearances",
        sa.Column("allowed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("clearances", sa.Column("allowed_by", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_clearances_allowed_by"), "clearances", ["allowed_by"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_clearances_allowed_by"), table_name="clearances")
    op.drop_column("clearances", "allowed_by")
    op.drop_column("clearances", "allowed_at")
