"""Add buildings table."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_buildings"
down_revision: Union[str, None] = "0002_societies"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_index(inspector: sa.Inspector, table: str, index_name: str) -> bool:
    return any(i["name"] == index_name for i in inspector.get_indexes(table))


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "buildings" not in tables:
        op.create_table(
            "buildings",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("display_name", sa.String(length=200), nullable=True),
            sa.Column("code", sa.String(length=32), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("building_type", sa.String(length=50), nullable=True),
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
            sa.Column("address_line1", sa.String(length=255), nullable=True),
            sa.Column("address_line2", sa.String(length=255), nullable=True),
            sa.Column("emergency_contact_name", sa.String(length=120), nullable=True),
            sa.Column("emergency_contact_phone", sa.String(length=20), nullable=True),
            sa.Column("total_floors", sa.Integer(), nullable=True),
            sa.Column("total_units", sa.Integer(), nullable=True),
            sa.Column("planned_units", sa.Integer(), nullable=True),
            sa.Column("occupied_units", sa.Integer(), nullable=True),
            sa.Column("vacant_units", sa.Integer(), nullable=True),
            sa.Column("built_year", sa.Integer(), nullable=True),
            sa.Column("has_lift", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column(
                "has_parking", sa.Boolean(), nullable=False, server_default=sa.text("false")
            ),
            sa.Column("image_url", sa.String(length=500), nullable=True),
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
                name="fk_buildings_society_id",
            ),
        )

    if not _has_index(inspector, "buildings", "ix_buildings_society_id"):
        op.create_index("ix_buildings_society_id", "buildings", ["society_id"])
    if not _has_index(inspector, "buildings", "ix_buildings_is_active"):
        op.create_index("ix_buildings_is_active", "buildings", ["is_active"])
    if not _has_index(inspector, "buildings", "ix_buildings_status"):
        op.create_index("ix_buildings_status", "buildings", ["status"])
    if not _has_index(inspector, "buildings", "ix_buildings_society_name"):
        op.create_index("ix_buildings_society_name", "buildings", ["society_id", "name"])
    if not _has_index(inspector, "buildings", "uq_buildings_society_code"):
        op.create_index(
            "uq_buildings_society_code", "buildings", ["society_id", "code"], unique=True
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "buildings" in inspector.get_table_names():
        if _has_index(inspector, "buildings", "uq_buildings_society_code"):
            op.drop_index("uq_buildings_society_code", table_name="buildings")
        if _has_index(inspector, "buildings", "ix_buildings_society_name"):
            op.drop_index("ix_buildings_society_name", table_name="buildings")
        if _has_index(inspector, "buildings", "ix_buildings_status"):
            op.drop_index("ix_buildings_status", table_name="buildings")
        if _has_index(inspector, "buildings", "ix_buildings_is_active"):
            op.drop_index("ix_buildings_is_active", table_name="buildings")
        if _has_index(inspector, "buildings", "ix_buildings_society_id"):
            op.drop_index("ix_buildings_society_id", table_name="buildings")
        op.drop_table("buildings")
