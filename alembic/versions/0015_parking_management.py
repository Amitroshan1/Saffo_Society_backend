"""Create parking management system tables (Phase 14)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015_parking_management"
down_revision: Union[str, None] = "0014_amenities_booking"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_index(inspector: sa.Inspector, table: str, index_name: str) -> bool:
    return any(i["name"] == index_name for i in inspector.get_indexes(table))


def _common_audit_columns():
    return [
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
    ]


def _create_indexes(inspector: sa.Inspector, table: str, indexes: tuple) -> None:
    if table not in inspector.get_table_names():
        return
    for item in indexes:
        if len(item) == 3:
            name, cols, unique = item
        else:
            name, cols = item
            unique = False
        if not _has_index(inspector, table, name):
            op.create_index(name, table, cols, unique=unique)


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if "parking_zones" not in inspector.get_table_names():
        op.create_table(
            "parking_zones",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("code", sa.String(length=32), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column(
                "zone_type", sa.String(length=32), nullable=False, server_default="basement"
            ),
            sa.Column("floor_label", sa.String(length=32), nullable=True),
            sa.Column("building_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("total_slots", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("available_slots", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "is_visitor_allowed",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column("monthly_fee_minor", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("visitor_fee_minor", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "additional_vehicle_fee_minor",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
            *_common_audit_columns(),
            sa.ForeignKeyConstraint(
                ["society_id"],
                ["societies.id"],
                ondelete="RESTRICT",
                name="fk_parking_zones_society_id",
            ),
            sa.ForeignKeyConstraint(
                ["building_id"],
                ["buildings.id"],
                ondelete="SET NULL",
                name="fk_parking_zones_building_id",
            ),
            sa.UniqueConstraint("society_id", "code", name="uq_parking_zones_society_code"),
        )

    inspector = sa.inspect(conn)
    _create_indexes(
        inspector,
        "parking_zones",
        (
            ("ix_parking_zones_society_id", ["society_id"]),
            ("ix_parking_zones_zone_type", ["zone_type"]),
            ("ix_parking_zones_is_active", ["is_active"]),
        ),
    )

    inspector = sa.inspect(conn)
    if "parking_slots" not in inspector.get_table_names():
        op.create_table(
            "parking_slots",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("zone_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("slot_code", sa.String(length=32), nullable=False),
            sa.Column("label", sa.String(length=64), nullable=True),
            sa.Column(
                "slot_category",
                sa.String(length=32),
                nullable=False,
                server_default="standard",
            ),
            sa.Column(
                "vehicle_types_allowed",
                sa.String(length=120),
                nullable=False,
                server_default="car,bike,scooter,ev",
            ),
            sa.Column(
                "status", sa.String(length=16), nullable=False, server_default="available"
            ),
            sa.Column("floor_no", sa.Integer(), nullable=True),
            sa.Column(
                "is_covered", sa.Boolean(), nullable=False, server_default=sa.text("false")
            ),
            sa.Column(
                "is_ev_charging",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column("monthly_fee_minor", sa.Integer(), nullable=True),
            sa.Column("current_allocation_id", postgresql.UUID(as_uuid=True), nullable=True),
            *_common_audit_columns(),
            sa.ForeignKeyConstraint(
                ["society_id"],
                ["societies.id"],
                ondelete="RESTRICT",
                name="fk_parking_slots_society_id",
            ),
            sa.ForeignKeyConstraint(
                ["zone_id"],
                ["parking_zones.id"],
                ondelete="CASCADE",
                name="fk_parking_slots_zone_id",
            ),
            sa.UniqueConstraint(
                "society_id", "slot_code", name="uq_parking_slots_society_slot_code"
            ),
        )

    inspector = sa.inspect(conn)
    _create_indexes(
        inspector,
        "parking_slots",
        (
            ("ix_parking_slots_society_id", ["society_id"]),
            ("ix_parking_slots_zone_id", ["zone_id"]),
            ("ix_parking_slots_status", ["status"]),
            ("ix_parking_slots_slot_category", ["slot_category"]),
        ),
    )

    inspector = sa.inspect(conn)
    if "resident_vehicles" not in inspector.get_table_names():
        op.create_table(
            "resident_vehicles",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("resident_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("vehicle_number", sa.String(length=32), nullable=False),
            sa.Column("vehicle_type", sa.String(length=32), nullable=False),
            sa.Column("make", sa.String(length=64), nullable=True),
            sa.Column("model", sa.String(length=64), nullable=True),
            sa.Column("color", sa.String(length=32), nullable=True),
            sa.Column(
                "is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")
            ),
            sa.Column(
                "is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")
            ),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
            sa.Column("parking_code", sa.String(length=20), nullable=False),
            *_common_audit_columns(),
            sa.ForeignKeyConstraint(
                ["society_id"],
                ["societies.id"],
                ondelete="RESTRICT",
                name="fk_resident_vehicles_society_id",
            ),
            sa.ForeignKeyConstraint(
                ["resident_id"],
                ["residents.id"],
                ondelete="RESTRICT",
                name="fk_resident_vehicles_resident_id",
            ),
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["users.id"],
                ondelete="SET NULL",
                name="fk_resident_vehicles_user_id",
            ),
            sa.UniqueConstraint(
                "society_id",
                "vehicle_number",
                name="uq_resident_vehicles_society_vehicle_number",
            ),
        )

    inspector = sa.inspect(conn)
    _create_indexes(
        inspector,
        "resident_vehicles",
        (
            ("ix_resident_vehicles_society_id", ["society_id"]),
            ("ix_resident_vehicles_resident_id", ["resident_id"]),
            ("ix_resident_vehicles_vehicle_type", ["vehicle_type"]),
            ("ix_resident_vehicles_status", ["status"]),
            ("ix_resident_vehicles_parking_code", ["parking_code"]),
        ),
    )

    inspector = sa.inspect(conn)
    if "parking_allocations" not in inspector.get_table_names():
        op.create_table(
            "parking_allocations",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("slot_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("resident_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("vehicle_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("allocation_number", sa.String(length=32), nullable=False),
            sa.Column(
                "allocation_type",
                sa.String(length=32),
                nullable=False,
                server_default="permanent",
            ),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
            sa.Column("start_date", sa.Date(), nullable=False),
            sa.Column("end_date", sa.Date(), nullable=True),
            sa.Column("monthly_fee_minor", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "payment_status",
                sa.String(length=16),
                nullable=False,
                server_default="not_required",
            ),
            sa.Column("allocated_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("allocated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoke_reason", sa.String(length=500), nullable=True),
            sa.Column(
                "transferred_from_allocation_id",
                postgresql.UUID(as_uuid=True),
                nullable=True,
            ),
            *_common_audit_columns(),
            sa.ForeignKeyConstraint(
                ["society_id"],
                ["societies.id"],
                ondelete="RESTRICT",
                name="fk_parking_allocations_society_id",
            ),
            sa.ForeignKeyConstraint(
                ["slot_id"],
                ["parking_slots.id"],
                ondelete="RESTRICT",
                name="fk_parking_allocations_slot_id",
            ),
            sa.ForeignKeyConstraint(
                ["resident_id"],
                ["residents.id"],
                ondelete="RESTRICT",
                name="fk_parking_allocations_resident_id",
            ),
            sa.ForeignKeyConstraint(
                ["vehicle_id"],
                ["resident_vehicles.id"],
                ondelete="SET NULL",
                name="fk_parking_allocations_vehicle_id",
            ),
            sa.ForeignKeyConstraint(
                ["allocated_by"],
                ["users.id"],
                ondelete="SET NULL",
                name="fk_parking_allocations_allocated_by",
            ),
            sa.UniqueConstraint(
                "society_id",
                "allocation_number",
                name="uq_parking_allocations_society_number",
            ),
        )

    inspector = sa.inspect(conn)
    _create_indexes(
        inspector,
        "parking_allocations",
        (
            ("ix_parking_allocations_society_id", ["society_id"]),
            ("ix_parking_allocations_slot_id", ["slot_id"]),
            ("ix_parking_allocations_resident_id", ["resident_id"]),
            ("ix_parking_allocations_status", ["status"]),
            ("ix_parking_allocations_vehicle_id", ["vehicle_id"]),
        ),
    )

    inspector = sa.inspect(conn)
    if "visitor_parking_logs" not in inspector.get_table_names():
        op.create_table(
            "visitor_parking_logs",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("slot_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("visit_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("visitor_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("resident_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("vehicle_number", sa.String(length=32), nullable=False),
            sa.Column(
                "vehicle_type", sa.String(length=32), nullable=False, server_default="car"
            ),
            sa.Column("parking_code", sa.String(length=20), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
            sa.Column("entry_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("exit_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("entry_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("exit_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("fee_minor", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "payment_status",
                sa.String(length=16),
                nullable=False,
                server_default="not_required",
            ),
            sa.Column("purpose", sa.String(length=300), nullable=True),
            sa.Column(
                "metadata_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("notes", sa.Text(), nullable=True),
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
                name="fk_visitor_parking_logs_society_id",
            ),
            sa.ForeignKeyConstraint(
                ["slot_id"],
                ["parking_slots.id"],
                ondelete="SET NULL",
                name="fk_visitor_parking_logs_slot_id",
            ),
            sa.ForeignKeyConstraint(
                ["visit_id"],
                ["visits.id"],
                ondelete="SET NULL",
                name="fk_visitor_parking_logs_visit_id",
            ),
            sa.ForeignKeyConstraint(
                ["visitor_id"],
                ["visitors.id"],
                ondelete="SET NULL",
                name="fk_visitor_parking_logs_visitor_id",
            ),
            sa.ForeignKeyConstraint(
                ["resident_id"],
                ["residents.id"],
                ondelete="SET NULL",
                name="fk_visitor_parking_logs_resident_id",
            ),
            sa.ForeignKeyConstraint(
                ["entry_by"],
                ["users.id"],
                ondelete="SET NULL",
                name="fk_visitor_parking_logs_entry_by",
            ),
            sa.ForeignKeyConstraint(
                ["exit_by"],
                ["users.id"],
                ondelete="SET NULL",
                name="fk_visitor_parking_logs_exit_by",
            ),
        )

    inspector = sa.inspect(conn)
    _create_indexes(
        inspector,
        "visitor_parking_logs",
        (
            ("ix_visitor_parking_logs_society_id", ["society_id"]),
            ("ix_visitor_parking_logs_slot_id", ["slot_id"]),
            ("ix_visitor_parking_logs_status", ["status"]),
            ("ix_visitor_parking_logs_vehicle_number", ["vehicle_number"]),
            ("ix_visitor_parking_logs_parking_code", ["parking_code"]),
            ("ix_visitor_parking_logs_entry_at", ["entry_at"]),
        ),
    )


def downgrade() -> None:
    op.drop_table("visitor_parking_logs")
    op.drop_table("parking_allocations")
    op.drop_table("resident_vehicles")
    op.drop_table("parking_slots")
    op.drop_table("parking_zones")
