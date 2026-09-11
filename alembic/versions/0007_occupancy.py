"""Create residents and occupancies tables (Phase 5)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_occupancy"
down_revision: Union[str, None] = "0006_users_flat_fk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_index(inspector: sa.Inspector, table: str, index_name: str) -> bool:
    return any(i["name"] == index_name for i in inspector.get_indexes(table))


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "residents" not in tables:
        op.create_table(
            "residents",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("code", sa.String(length=32), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=True),
            sa.Column("phone", sa.String(length=20), nullable=True),
            sa.Column("gender", sa.String(length=32), nullable=True),
            sa.Column("dob", sa.Date(), nullable=True),
            sa.Column(
                "metadata_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
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
                name="fk_residents_society_id",
            ),
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["users.id"],
                ondelete="SET NULL",
                name="fk_residents_user_id",
            ),
        )

    if "occupancies" not in tables:
        op.create_table(
            "occupancies",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("building_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("wing_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("flat_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("resident_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("role", sa.String(length=32), nullable=False),
            sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column(
                "status",
                sa.String(length=32),
                nullable=False,
                server_default="active",
            ),
            sa.Column("move_in_date", sa.Date(), nullable=False),
            sa.Column("move_out_date", sa.Date(), nullable=True),
            sa.Column("ended_reason", sa.String(length=64), nullable=True),
            sa.Column(
                "metadata_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
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
                name="fk_occupancies_society_id",
            ),
            sa.ForeignKeyConstraint(
                ["building_id"],
                ["buildings.id"],
                ondelete="RESTRICT",
                name="fk_occupancies_building_id",
            ),
            sa.ForeignKeyConstraint(
                ["wing_id"],
                ["wings.id"],
                ondelete="RESTRICT",
                name="fk_occupancies_wing_id",
            ),
            sa.ForeignKeyConstraint(
                ["flat_id"],
                ["flats.id"],
                ondelete="RESTRICT",
                name="fk_occupancies_flat_id",
            ),
            sa.ForeignKeyConstraint(
                ["resident_id"],
                ["residents.id"],
                ondelete="RESTRICT",
                name="fk_occupancies_resident_id",
            ),
        )

    inspector = sa.inspect(conn)

    resident_indexes = (
        ("ix_residents_society_id", ["society_id"]),
        ("ix_residents_user_id", ["user_id"]),
        ("ix_residents_is_active", ["is_active"]),
        ("ix_residents_society_name", ["society_id", "name"]),
        ("ix_residents_society_phone", ["society_id", "phone"]),
        ("uq_residents_society_code", ["society_id", "code"]),
    )
    for idx_name, cols in resident_indexes:
        if "residents" in inspector.get_table_names() and not _has_index(inspector, "residents", idx_name):
            op.create_index(idx_name, "residents", cols, unique=idx_name.startswith("uq_"))

    occupancy_indexes = (
        ("ix_occupancies_society_id", ["society_id"]),
        ("ix_occupancies_building_id", ["building_id"]),
        ("ix_occupancies_wing_id", ["wing_id"]),
        ("ix_occupancies_flat_id", ["flat_id"]),
        ("ix_occupancies_resident_id", ["resident_id"]),
        ("ix_occupancies_status", ["status"]),
        ("ix_occupancies_role", ["role"]),
        ("ix_occupancies_flat_status", ["flat_id", "status"]),
        ("ix_occupancies_resident_status", ["resident_id", "status"]),
        ("ix_occupancies_society_move_in", ["society_id", "move_in_date"]),
    )
    for idx_name, cols in occupancy_indexes:
        if "occupancies" in inspector.get_table_names() and not _has_index(inspector, "occupancies", idx_name):
            op.create_index(idx_name, "occupancies", cols)

    # Partial unique indexes (PostgreSQL)
    if "residents" in inspector.get_table_names() and not _has_index(
        inspector, "residents", "uq_residents_user_id_not_null"
    ):
        op.execute(
            """
            CREATE UNIQUE INDEX uq_residents_user_id_not_null
            ON residents (user_id)
            WHERE user_id IS NOT NULL
            """
        )

    if "occupancies" in inspector.get_table_names() and not _has_index(
        inspector, "occupancies", "uq_occupancies_flat_primary_active"
    ):
        op.execute(
            """
            CREATE UNIQUE INDEX uq_occupancies_flat_primary_active
            ON occupancies (flat_id)
            WHERE is_primary = true AND status = 'active'
            """
        )

    if "occupancies" in inspector.get_table_names() and not _has_index(
        inspector, "occupancies", "uq_occupancies_flat_resident_active"
    ):
        op.execute(
            """
            CREATE UNIQUE INDEX uq_occupancies_flat_resident_active
            ON occupancies (flat_id, resident_id)
            WHERE status = 'active'
            """
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "occupancies" in tables:
        for idx in (
            "uq_occupancies_flat_resident_active",
            "uq_occupancies_flat_primary_active",
            "ix_occupancies_society_move_in",
            "ix_occupancies_resident_status",
            "ix_occupancies_flat_status",
            "ix_occupancies_role",
            "ix_occupancies_status",
            "ix_occupancies_resident_id",
            "ix_occupancies_flat_id",
            "ix_occupancies_wing_id",
            "ix_occupancies_building_id",
            "ix_occupancies_society_id",
        ):
            if _has_index(inspector, "occupancies", idx):
                op.drop_index(idx, table_name="occupancies")
        op.drop_table("occupancies")

    if "residents" in tables:
        for idx in (
            "uq_residents_user_id_not_null",
            "uq_residents_society_code",
            "ix_residents_society_phone",
            "ix_residents_society_name",
            "ix_residents_is_active",
            "ix_residents_user_id",
            "ix_residents_society_id",
        ):
            if _has_index(inspector, "residents", idx):
                op.drop_index(idx, table_name="residents")
        op.drop_table("residents")
