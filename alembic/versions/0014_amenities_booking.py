"""Create amenities booking system tables (Phase 13)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014_amenities_booking"
down_revision: Union[str, None] = "0013_document_management"
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

    if "amenities" not in inspector.get_table_names():
        op.create_table(
            "amenities",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("slug", sa.String(length=100), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("category", sa.String(length=64), nullable=False),
            sa.Column("location", sa.String(length=200), nullable=True),
            sa.Column("capacity", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("is_paid", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("price_per_slot", sa.Integer(), nullable=True, server_default="0"),
            sa.Column("security_deposit", sa.Integer(), nullable=True, server_default="0"),
            sa.Column("slot_duration_minutes", sa.Integer(), nullable=False, server_default="60"),
            sa.Column("advance_booking_days", sa.Integer(), nullable=False, server_default="30"),
            sa.Column("cancellation_hours", sa.Integer(), nullable=False, server_default="24"),
            sa.Column("max_bookings_per_resident", sa.Integer(), nullable=True, server_default="2"),
            sa.Column(
                "requires_approval", sa.Boolean(), nullable=False, server_default=sa.text("false")
            ),
            sa.Column("operating_hours_start", sa.String(length=5), nullable=True),
            sa.Column("operating_hours_end", sa.String(length=5), nullable=True),
            sa.Column(
                "available_days", sa.String(length=20), nullable=True, server_default="0123456"
            ),
            sa.Column("rules_text", sa.Text(), nullable=True),
            sa.Column("image_url", sa.String(length=500), nullable=True),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
            *_common_audit_columns(),
            sa.ForeignKeyConstraint(
                ["society_id"], ["societies.id"], ondelete="RESTRICT", name="fk_amenities_society_id"
            ),
            sa.UniqueConstraint("society_id", "slug", name="uq_amenities_society_slug"),
        )

    inspector = sa.inspect(conn)
    _create_indexes(
        inspector,
        "amenities",
        (
            ("ix_amenities_society_id", ["society_id"]),
            ("ix_amenities_status", ["status"]),
            ("ix_amenities_category", ["category"]),
            ("ix_amenities_is_active", ["is_active"]),
        ),
    )

    inspector = sa.inspect(conn)
    if "amenity_booking_slots" not in inspector.get_table_names():
        op.create_table(
            "amenity_booking_slots",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("amenity_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("start_time", sa.String(length=5), nullable=False),
            sa.Column("end_time", sa.String(length=5), nullable=False),
            sa.Column("capacity", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("booked_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_blocked", sa.Boolean(), nullable=True, server_default=sa.text("false")),
            sa.Column("block_reason", sa.String(length=200), nullable=True),
            sa.Column(
                "metadata_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
            ),
            sa.ForeignKeyConstraint(
                ["amenity_id"],
                ["amenities.id"],
                ondelete="CASCADE",
                name="fk_amenity_slots_amenity_id",
            ),
            sa.ForeignKeyConstraint(
                ["society_id"],
                ["societies.id"],
                ondelete="RESTRICT",
                name="fk_amenity_slots_society_id",
            ),
            sa.UniqueConstraint(
                "amenity_id", "date", "start_time", name="uq_amenity_slots_amenity_date_start"
            ),
        )

    inspector = sa.inspect(conn)
    _create_indexes(
        inspector,
        "amenity_booking_slots",
        (
            ("ix_amenity_slots_amenity_id", ["amenity_id"]),
            ("ix_amenity_slots_society_id", ["society_id"]),
            ("ix_amenity_slots_date", ["date"]),
            ("ix_amenity_slots_is_blocked", ["is_blocked"]),
        ),
    )

    inspector = sa.inspect(conn)
    if "amenity_bookings" not in inspector.get_table_names():
        op.create_table(
            "amenity_bookings",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("amenity_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("slot_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("resident_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("booking_number", sa.String(length=32), nullable=False),
            sa.Column("booking_date", sa.Date(), nullable=False),
            sa.Column("start_time", sa.String(length=5), nullable=False),
            sa.Column("end_time", sa.String(length=5), nullable=False),
            sa.Column("guest_count", sa.Integer(), nullable=True, server_default="0"),
            sa.Column("purpose", sa.String(length=300), nullable=True),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
            sa.Column("amount", sa.Integer(), nullable=True, server_default="0"),
            sa.Column("security_deposit", sa.Integer(), nullable=True, server_default="0"),
            sa.Column(
                "payment_status", sa.String(length=16), nullable=False, server_default="not_required"
            ),
            sa.Column("payment_reference", sa.String(length=100), nullable=True),
            sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("rejected_reason", sa.String(length=500), nullable=True),
            sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("cancellation_reason", sa.String(length=500), nullable=True),
            sa.Column("checked_in_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("checked_in_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("checked_out_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("checked_out_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("booking_code", sa.String(length=20), nullable=False),
            *_common_audit_columns(),
            sa.ForeignKeyConstraint(
                ["society_id"],
                ["societies.id"],
                ondelete="RESTRICT",
                name="fk_amenity_bookings_society_id",
            ),
            sa.ForeignKeyConstraint(
                ["amenity_id"],
                ["amenities.id"],
                ondelete="RESTRICT",
                name="fk_amenity_bookings_amenity_id",
            ),
            sa.ForeignKeyConstraint(
                ["slot_id"],
                ["amenity_booking_slots.id"],
                ondelete="SET NULL",
                name="fk_amenity_bookings_slot_id",
            ),
            sa.ForeignKeyConstraint(
                ["resident_id"],
                ["residents.id"],
                ondelete="RESTRICT",
                name="fk_amenity_bookings_resident_id",
            ),
            sa.ForeignKeyConstraint(
                ["user_id"], ["users.id"], ondelete="RESTRICT", name="fk_amenity_bookings_user_id"
            ),
            sa.ForeignKeyConstraint(
                ["approved_by"],
                ["users.id"],
                ondelete="SET NULL",
                name="fk_amenity_bookings_approved_by",
            ),
            sa.ForeignKeyConstraint(
                ["checked_in_by"],
                ["users.id"],
                ondelete="SET NULL",
                name="fk_amenity_bookings_checked_in_by",
            ),
            sa.ForeignKeyConstraint(
                ["checked_out_by"],
                ["users.id"],
                ondelete="SET NULL",
                name="fk_amenity_bookings_checked_out_by",
            ),
            sa.UniqueConstraint(
                "society_id", "booking_number", name="uq_amenity_bookings_society_number"
            ),
        )

    inspector = sa.inspect(conn)
    _create_indexes(
        inspector,
        "amenity_bookings",
        (
            ("ix_amenity_bookings_society_id", ["society_id"]),
            ("ix_amenity_bookings_amenity_id", ["amenity_id"]),
            ("ix_amenity_bookings_resident_id", ["resident_id"]),
            ("ix_amenity_bookings_user_id", ["user_id"]),
            ("ix_amenity_bookings_status", ["status"]),
            ("ix_amenity_bookings_booking_date", ["booking_date"]),
            ("ix_amenity_bookings_booking_code", ["booking_code"]),
        ),
    )

    inspector = sa.inspect(conn)
    if "amenity_maintenance_blocks" not in inspector.get_table_names():
        op.create_table(
            "amenity_maintenance_blocks",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("amenity_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("start_date", sa.Date(), nullable=False),
            sa.Column("end_date", sa.Date(), nullable=False),
            sa.Column("reason", sa.String(length=500), nullable=False),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column(
                "metadata_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.text("true")),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
            ),
            sa.ForeignKeyConstraint(
                ["amenity_id"],
                ["amenities.id"],
                ondelete="CASCADE",
                name="fk_amenity_maint_blocks_amenity_id",
            ),
            sa.ForeignKeyConstraint(
                ["society_id"],
                ["societies.id"],
                ondelete="RESTRICT",
                name="fk_amenity_maint_blocks_society_id",
            ),
            sa.ForeignKeyConstraint(
                ["created_by"],
                ["users.id"],
                ondelete="SET NULL",
                name="fk_amenity_maint_blocks_created_by",
            ),
        )

    inspector = sa.inspect(conn)
    _create_indexes(
        inspector,
        "amenity_maintenance_blocks",
        (
            ("ix_amenity_maint_blocks_amenity_id", ["amenity_id"]),
            ("ix_amenity_maint_blocks_society_id", ["society_id"]),
            ("ix_amenity_maint_blocks_start_date", ["start_date"]),
            ("ix_amenity_maint_blocks_end_date", ["end_date"]),
        ),
    )

    inspector = sa.inspect(conn)
    if "amenity_checkins" not in inspector.get_table_names():
        op.create_table(
            "amenity_checkins",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("booking_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("action", sa.String(length=16), nullable=False),
            sa.Column("performed_by", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(
                "performed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
            ),
            sa.Column("notes", sa.String(length=500), nullable=True),
            sa.Column(
                "metadata_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
            ),
            sa.ForeignKeyConstraint(
                ["booking_id"],
                ["amenity_bookings.id"],
                ondelete="CASCADE",
                name="fk_amenity_checkins_booking_id",
            ),
            sa.ForeignKeyConstraint(
                ["society_id"],
                ["societies.id"],
                ondelete="RESTRICT",
                name="fk_amenity_checkins_society_id",
            ),
            sa.ForeignKeyConstraint(
                ["performed_by"],
                ["users.id"],
                ondelete="RESTRICT",
                name="fk_amenity_checkins_performed_by",
            ),
        )

    inspector = sa.inspect(conn)
    _create_indexes(
        inspector,
        "amenity_checkins",
        (
            ("ix_amenity_checkins_booking_id", ["booking_id"]),
            ("ix_amenity_checkins_society_id", ["society_id"]),
            ("ix_amenity_checkins_action", ["action"]),
        ),
    )


def downgrade() -> None:
    op.drop_table("amenity_checkins")
    op.drop_table("amenity_maintenance_blocks")
    op.drop_table("amenity_bookings")
    op.drop_table("amenity_booking_slots")
    op.drop_table("amenities")
