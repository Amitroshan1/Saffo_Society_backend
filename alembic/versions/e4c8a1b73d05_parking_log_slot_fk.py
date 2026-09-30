"""point parking logs at resident slots

Revision ID: e4c8a1b73d05
Revises: d3a7f6e12c84
Create Date: 2026-09-30 16:05:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "e4c8a1b73d05"
down_revision: Union[str, Sequence[str], None] = "d3a7f6e12c84"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_parking_logs_parking_slot",
        "parking_logs",
        "parking_slots",
        ["parking_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_parking_logs_parking_slot", "parking_logs", type_="foreignkey")
