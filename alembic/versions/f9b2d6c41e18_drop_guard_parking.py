"""drop duplicate guard parking table

Revision ID: f9b2d6c41e18
Revises: e4c8a1b73d05
Create Date: 2026-09-30 16:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f9b2d6c41e18"
down_revision: Union[str, Sequence[str], None] = "e4c8a1b73d05"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TZ = sa.DateTime(timezone=True)
PARKING_INDEXES = ["id", "society_id", "slot_number", "building", "slot_type"]


def upgrade() -> None:
    for column in PARKING_INDEXES:
        op.drop_index(op.f(f"ix_parking_{column}"), table_name="parking")
    op.drop_table("parking")


def downgrade() -> None:
    op.create_table(
        "parking",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("society_id", sa.Integer(), nullable=False),
        sa.Column("slot_number", sa.String(length=40), nullable=False),
        sa.Column("building", sa.String(length=80), nullable=False),
        sa.Column("wing_no", sa.String(length=30), nullable=True),
        sa.Column("slot_type", sa.String(length=20), nullable=False),
        sa.Column("resident_id", sa.Integer(), nullable=True),
        sa.Column("resident_name", sa.String(length=150), nullable=True),
        sa.Column("flat_no", sa.String(length=50), nullable=True),
        sa.Column("vehicle_number", sa.String(length=30), nullable=True),
        sa.Column("vehicle_type", sa.String(length=30), nullable=True),
        sa.Column("created_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("society_id", "slot_number", name="uq_parking_society_slot"),
    )
    for column in PARKING_INDEXES:
        op.create_index(op.f(f"ix_parking_{column}"), "parking", [column], unique=False)
