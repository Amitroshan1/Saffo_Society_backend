"""drop duplicate move-out tables

Revision ID: d3a7f6e12c84
Revises: b8e4c1a90f27
Create Date: 2026-09-30 11:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d3a7f6e12c84"
down_revision: Union[str, Sequence[str], None] = "b8e4c1a90f27"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TZ = sa.DateTime(timezone=True)

MOVE_OUT_INDEXES = ["id", "society_id", "resident_id", "flat_no", "move_out_date", "allowed_by"]
MOVE_OUT_FILE_INDEXES = ["id", "society_id", "move_out_id", "uploaded_by"]


def _drop_indexes(table: str, columns: list[str]) -> None:
    for column in columns:
        op.drop_index(op.f(f"ix_{table}_{column}"), table_name=table)


def _create_indexes(table: str, columns: list[str]) -> None:
    for column in columns:
        op.create_index(op.f(f"ix_{table}_{column}"), table, [column], unique=False)


def upgrade() -> None:
    _drop_indexes("move_out_files", MOVE_OUT_FILE_INDEXES)
    op.drop_table("move_out_files")
    _drop_indexes("guard_move_out", MOVE_OUT_INDEXES)
    op.drop_table("guard_move_out")


def downgrade() -> None:
    op.create_table(
        "guard_move_out",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("society_id", sa.Integer(), nullable=False),
        sa.Column("resident_id", sa.Integer(), nullable=False),
        sa.Column("resident_name", sa.String(length=150), nullable=False),
        sa.Column("flat_no", sa.String(length=50), nullable=False),
        sa.Column("building_no", sa.String(length=80), nullable=False),
        sa.Column("wing_no", sa.String(length=30), nullable=True),
        sa.Column("move_out_date", sa.Date(), nullable=False),
        sa.Column("leave_license", sa.Boolean(), nullable=False),
        sa.Column("tenant_id_proof", sa.Boolean(), nullable=False),
        sa.Column("owner_confirmation", sa.Boolean(), nullable=False),
        sa.Column("dues_clearance", sa.Boolean(), nullable=False),
        sa.Column("allowed_at", TZ, nullable=True),
        sa.Column("allowed_by", sa.Integer(), nullable=True),
        sa.Column("created_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    _create_indexes("guard_move_out", MOVE_OUT_INDEXES)
    op.create_table(
        "move_out_files",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("society_id", sa.Integer(), nullable=False),
        sa.Column("move_out_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.ForeignKeyConstraint(["move_out_id"], ["guard_move_out.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    _create_indexes("move_out_files", MOVE_OUT_FILE_INDEXES)
