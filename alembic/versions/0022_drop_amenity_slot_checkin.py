"""Drop derived amenity_booking_slots and unused amenity_checkins."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0022_drop_amenity_slot_checkin"
down_revision: Union[str, None] = "0021_parking_occupancy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_index(inspector: sa.Inspector, table: str, index_name: str) -> bool:
    return any(i["name"] == index_name for i in inspector.get_indexes(table))


def _drop_fks_for_column(inspector: sa.Inspector, table: str, column: str) -> None:
    for fk in inspector.get_foreign_keys(table):
        if column in (fk.get("constrained_columns") or []) and fk.get("name"):
            op.drop_constraint(fk["name"], table, type_="foreignkey")


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "amenity_bookings" in tables:
        columns = {c["name"] for c in inspector.get_columns("amenity_bookings")}
        if "slot_id" in columns:
            _drop_fks_for_column(inspector, "amenity_bookings", "slot_id")
            inspector = sa.inspect(conn)
            for idx in inspector.get_indexes("amenity_bookings"):
                if "slot_id" in (idx.get("column_names") or []) and idx.get("name"):
                    op.drop_index(idx["name"], table_name="amenity_bookings")
            op.drop_column("amenity_bookings", "slot_id")

    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())
    if "amenity_checkins" in tables:
        op.drop_table("amenity_checkins")

    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())
    if "amenity_booking_slots" in tables:
        op.drop_table("amenity_booking_slots")


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "amenity_booking_slots" not in tables:
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
    if "amenity_booking_slots" in inspector.get_table_names():
        for name, cols in (
            ("ix_amenity_slots_amenity_id", ["amenity_id"]),
            ("ix_amenity_slots_society_id", ["society_id"]),
            ("ix_amenity_slots_date", ["date"]),
            ("ix_amenity_slots_is_blocked", ["is_blocked"]),
        ):
            if not _has_index(inspector, "amenity_booking_slots", name):
                op.create_index(name, "amenity_booking_slots", cols)

    inspector = sa.inspect(conn)
    if "amenity_bookings" in inspector.get_table_names():
        columns = {c["name"] for c in inspector.get_columns("amenity_bookings")}
        if "slot_id" not in columns:
            op.add_column(
                "amenity_bookings",
                sa.Column("slot_id", postgresql.UUID(as_uuid=True), nullable=True),
            )
        inspector = sa.inspect(conn)
        fk_names = {fk["name"] for fk in inspector.get_foreign_keys("amenity_bookings")}
        if "fk_amenity_bookings_slot_id" not in fk_names:
            op.create_foreign_key(
                "fk_amenity_bookings_slot_id",
                "amenity_bookings",
                "amenity_booking_slots",
                ["slot_id"],
                ["id"],
                ondelete="SET NULL",
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
                "performed_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
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
        op.create_index("ix_amenity_checkins_booking_id", "amenity_checkins", ["booking_id"])
        op.create_index("ix_amenity_checkins_society_id", "amenity_checkins", ["society_id"])
        op.create_index("ix_amenity_checkins_action", "amenity_checkins", ["action"])
