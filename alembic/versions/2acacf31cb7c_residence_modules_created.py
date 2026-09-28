"""residence modules created

Revision ID: 2acacf31cb7c
Revises: b6188159b5a9
Create Date: 2026-09-26 15:49:02.804777

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2acacf31cb7c'
down_revision: Union[str, Sequence[str], None] = 'b6188159b5a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "buildings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("society_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["society_id"], ["societies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_buildings_id", "buildings", ["id"])
    op.create_index("ix_buildings_society_id", "buildings", ["society_id"])

    op.create_table(
        "flats",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("society_id", sa.Integer(), nullable=False),
        sa.Column("building_id", sa.Integer(), nullable=False),
        sa.Column("number", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["building_id"], ["buildings.id"]),
        sa.ForeignKeyConstraint(["society_id"], ["societies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_flats_id", "flats", ["id"])
    op.create_index("ix_flats_society_id", "flats", ["society_id"])
    op.create_index("ix_flats_building_id", "flats", ["building_id"])

    op.create_table(
        "residents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("society_id", sa.Integer(), nullable=False),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("emergency_name", sa.String(length=150), nullable=True),
        sa.Column("emergency_phone", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["society_id"], ["societies.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_residents_id", "residents", ["id"])
    op.create_index("ix_residents_society_id", "residents", ["society_id"])

    op.create_table(
        "occupancies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("society_id", sa.Integer(), nullable=False),
        sa.Column("resident_id", sa.Integer(), nullable=False),
        sa.Column("flat_id", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["flat_id"], ["flats.id"]),
        sa.ForeignKeyConstraint(["resident_id"], ["residents.id"]),
        sa.ForeignKeyConstraint(["society_id"], ["societies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_occupancies_id", "occupancies", ["id"])
    op.create_index("ix_occupancies_society_id", "occupancies", ["society_id"])
    op.create_index("ix_occupancies_resident_id", "occupancies", ["resident_id"])
    op.create_index("ix_occupancies_flat_id", "occupancies", ["flat_id"])

    op.create_table(
        "household_members",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("occupancy_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("relation", sa.String(length=50), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["occupancy_id"], ["occupancies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_household_members_id", "household_members", ["id"])
    op.create_index("ix_household_members_occupancy_id", "household_members", ["occupancy_id"])


def downgrade() -> None:
    op.drop_table("household_members")
    op.drop_table("occupancies")
    op.drop_table("residents")
    op.drop_table("flats")
    op.drop_table("buildings")