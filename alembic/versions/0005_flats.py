"""Add flats table."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_flats"
down_revision: Union[str, None] = "0004_wings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_index(inspector: sa.Inspector, table: str, index_name: str) -> bool:
    return any(i["name"] == index_name for i in inspector.get_indexes(table))


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "flats" not in tables:
        op.create_table(
            "flats",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("building_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("wing_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("flat_no", sa.String(length=50), nullable=False),
            sa.Column("floor_no", sa.String(length=20), nullable=False),
            sa.Column("flat_type", sa.String(length=50), nullable=True),
            sa.Column("usage_type", sa.String(length=50), nullable=True),
            sa.Column(
                "status",
                sa.String(length=32),
                nullable=False,
                server_default="vacant",
            ),
            sa.Column("ownership_type", sa.String(length=32), nullable=True),
            sa.Column("area_sqft", sa.Float(), nullable=True),
            sa.Column("area_type", sa.String(length=20), nullable=True),
            sa.Column("intercom", sa.String(length=20), nullable=True),
            sa.Column(
                "metadata_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("sequence", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("color", sa.String(length=7), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["society_id"],
                ["societies.id"],
                ondelete="RESTRICT",
                name="fk_flats_society_id",
            ),
            sa.ForeignKeyConstraint(
                ["building_id"],
                ["buildings.id"],
                ondelete="RESTRICT",
                name="fk_flats_building_id",
            ),
            sa.ForeignKeyConstraint(
                ["wing_id"],
                ["wings.id"],
                ondelete="RESTRICT",
                name="fk_flats_wing_id",
            ),
        )

    if not _has_index(inspector, "flats", "ix_flats_society_id"):
        op.create_index("ix_flats_society_id", "flats", ["society_id"])
    if not _has_index(inspector, "flats", "ix_flats_building_id"):
        op.create_index("ix_flats_building_id", "flats", ["building_id"])
    if not _has_index(inspector, "flats", "ix_flats_wing_id"):
        op.create_index("ix_flats_wing_id", "flats", ["wing_id"])
    if not _has_index(inspector, "flats", "ix_flats_is_active"):
        op.create_index("ix_flats_is_active", "flats", ["is_active"])
    if not _has_index(inspector, "flats", "ix_flats_status"):
        op.create_index("ix_flats_status", "flats", ["status"])
    if not _has_index(inspector, "flats", "ix_flats_floor_no"):
        op.create_index("ix_flats_floor_no", "flats", ["floor_no"])
    if not _has_index(inspector, "flats", "ix_flats_society_flat_no"):
        op.create_index("ix_flats_society_flat_no", "flats", ["society_id", "flat_no"])
    if not _has_index(inspector, "flats", "uq_flats_wing_flat_no"):
        op.create_index("uq_flats_wing_flat_no", "flats", ["wing_id", "flat_no"], unique=True)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "flats" in inspector.get_table_names():
        for idx in (
            "uq_flats_wing_flat_no",
            "ix_flats_society_flat_no",
            "ix_flats_floor_no",
            "ix_flats_status",
            "ix_flats_is_active",
            "ix_flats_wing_id",
            "ix_flats_building_id",
            "ix_flats_society_id",
        ):
            if _has_index(inspector, "flats", idx):
                op.drop_index(idx, table_name="flats")
        op.drop_table("flats")
