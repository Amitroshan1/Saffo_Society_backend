"""Persist parking occupancy entry/exit timestamps and resident movement logs."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0021_parking_occupancy"
down_revision: Union[str, None] = "0020_gate_geofence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_index(inspector: sa.Inspector, table: str, index_name: str) -> bool:
    return any(i["name"] == index_name for i in inspector.get_indexes(table))


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "parking_slots" in tables:
        columns = {c["name"] for c in inspector.get_columns("parking_slots")}
        if "occupancy_entry_at" not in columns:
            op.add_column(
                "parking_slots",
                sa.Column("occupancy_entry_at", sa.DateTime(timezone=True), nullable=True),
            )
        if "occupancy_exit_at" not in columns:
            op.add_column(
                "parking_slots",
                sa.Column("occupancy_exit_at", sa.DateTime(timezone=True), nullable=True),
            )
        if "occupancy_entry_by" not in columns:
            op.add_column(
                "parking_slots",
                sa.Column("occupancy_entry_by", postgresql.UUID(as_uuid=True), nullable=True),
            )
        if "occupancy_exit_by" not in columns:
            op.add_column(
                "parking_slots",
                sa.Column("occupancy_exit_by", postgresql.UUID(as_uuid=True), nullable=True),
            )

        inspector = sa.inspect(conn)
        fks = {fk["name"] for fk in inspector.get_foreign_keys("parking_slots")}
        if "fk_parking_slots_occupancy_entry_by" not in fks:
            op.create_foreign_key(
                "fk_parking_slots_occupancy_entry_by",
                "parking_slots",
                "users",
                ["occupancy_entry_by"],
                ["id"],
                ondelete="SET NULL",
            )
        if "fk_parking_slots_occupancy_exit_by" not in fks:
            op.create_foreign_key(
                "fk_parking_slots_occupancy_exit_by",
                "parking_slots",
                "users",
                ["occupancy_exit_by"],
                ["id"],
                ondelete="SET NULL",
            )

    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())
    if "parking_vehicle_logs" not in tables:
        op.create_table(
            "parking_vehicle_logs",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("slot_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("vehicle_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("vehicle_number", sa.String(length=32), nullable=True),
            sa.Column("vehicle_type", sa.String(length=32), nullable=True),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
            sa.Column("entry_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("exit_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("entry_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("exit_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column(
                "metadata_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
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
                name="fk_parking_vehicle_logs_society_id",
            ),
            sa.ForeignKeyConstraint(
                ["slot_id"],
                ["parking_slots.id"],
                ondelete="SET NULL",
                name="fk_parking_vehicle_logs_slot_id",
            ),
            sa.ForeignKeyConstraint(
                ["vehicle_id"],
                ["resident_vehicles.id"],
                ondelete="SET NULL",
                name="fk_parking_vehicle_logs_vehicle_id",
            ),
            sa.ForeignKeyConstraint(
                ["entry_by"],
                ["users.id"],
                ondelete="SET NULL",
                name="fk_parking_vehicle_logs_entry_by",
            ),
            sa.ForeignKeyConstraint(
                ["exit_by"],
                ["users.id"],
                ondelete="SET NULL",
                name="fk_parking_vehicle_logs_exit_by",
            ),
        )

    inspector = sa.inspect(conn)
    for name, cols in (
        ("ix_parking_vehicle_logs_society_id", ["society_id"]),
        ("ix_parking_vehicle_logs_slot_id", ["slot_id"]),
        ("ix_parking_vehicle_logs_status", ["status"]),
        ("ix_parking_vehicle_logs_vehicle_number", ["vehicle_number"]),
        ("ix_parking_vehicle_logs_entry_at", ["entry_at"]),
    ):
        if "parking_vehicle_logs" in inspector.get_table_names() and not _has_index(
            inspector, "parking_vehicle_logs", name
        ):
            op.create_index(name, "parking_vehicle_logs", cols)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "parking_vehicle_logs" in tables:
        inspector = sa.inspect(conn)
        for name in (
            "ix_parking_vehicle_logs_entry_at",
            "ix_parking_vehicle_logs_vehicle_number",
            "ix_parking_vehicle_logs_status",
            "ix_parking_vehicle_logs_slot_id",
            "ix_parking_vehicle_logs_society_id",
        ):
            if _has_index(inspector, "parking_vehicle_logs", name):
                op.drop_index(name, table_name="parking_vehicle_logs")
        op.drop_table("parking_vehicle_logs")

    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())
    if "parking_slots" not in tables:
        return

    fks = {fk["name"] for fk in inspector.get_foreign_keys("parking_slots")}
    if "fk_parking_slots_occupancy_exit_by" in fks:
        op.drop_constraint("fk_parking_slots_occupancy_exit_by", "parking_slots", type_="foreignkey")
    if "fk_parking_slots_occupancy_entry_by" in fks:
        op.drop_constraint(
            "fk_parking_slots_occupancy_entry_by", "parking_slots", type_="foreignkey"
        )

    columns = {c["name"] for c in inspector.get_columns("parking_slots")}
    for col in (
        "occupancy_exit_by",
        "occupancy_entry_by",
        "occupancy_exit_at",
        "occupancy_entry_at",
    ):
        if col in columns:
            op.drop_column("parking_slots", col)
