"""Add wings table."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_wings"
down_revision: Union[str, None] = "0003_buildings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_index(inspector: sa.Inspector, table: str, index_name: str) -> bool:
    return any(i["name"] == index_name for i in inspector.get_indexes(table))


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "wings" not in tables:
        op.create_table(
            "wings",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("building_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("display_name", sa.String(length=200), nullable=True),
            sa.Column("code", sa.String(length=32), nullable=False),
            sa.Column("short_code", sa.String(length=16), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("wing_type", sa.String(length=50), nullable=True),
            sa.Column(
                "status",
                sa.String(length=32),
                nullable=False,
                server_default="operational",
            ),
            sa.Column(
                "metadata_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("sequence", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("color", sa.String(length=7), nullable=True),
            sa.Column("total_floors", sa.Integer(), nullable=True),
            sa.Column("total_flats", sa.Integer(), nullable=True),
            sa.Column("elevator_count", sa.Integer(), nullable=True),
            sa.Column("emergency_stair_count", sa.Integer(), nullable=True),
            sa.Column("capacity", sa.Integer(), nullable=True),
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
                name="fk_wings_society_id",
            ),
            sa.ForeignKeyConstraint(
                ["building_id"],
                ["buildings.id"],
                ondelete="RESTRICT",
                name="fk_wings_building_id",
            ),
        )

    if not _has_index(inspector, "wings", "ix_wings_society_id"):
        op.create_index("ix_wings_society_id", "wings", ["society_id"])
    if not _has_index(inspector, "wings", "ix_wings_building_id"):
        op.create_index("ix_wings_building_id", "wings", ["building_id"])
    if not _has_index(inspector, "wings", "ix_wings_is_active"):
        op.create_index("ix_wings_is_active", "wings", ["is_active"])
    if not _has_index(inspector, "wings", "ix_wings_status"):
        op.create_index("ix_wings_status", "wings", ["status"])
    if not _has_index(inspector, "wings", "ix_wings_society_name"):
        op.create_index("ix_wings_society_name", "wings", ["society_id", "name"])
    if not _has_index(inspector, "wings", "uq_wings_building_code"):
        op.create_index("uq_wings_building_code", "wings", ["building_id", "code"], unique=True)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "wings" in inspector.get_table_names():
        for idx in (
            "uq_wings_building_code",
            "ix_wings_society_name",
            "ix_wings_status",
            "ix_wings_is_active",
            "ix_wings_building_id",
            "ix_wings_society_id",
        ):
            if _has_index(inspector, "wings", idx):
                op.drop_index(idx, table_name="wings")
        op.drop_table("wings")
