"""Create gates, staff, shifts, staff_attendance tables (Phase 7)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_staff_gate_ops"
down_revision: Union[str, None] = "0008_visitors_visits"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_index(inspector: sa.Inspector, table: str, index_name: str) -> bool:
    return any(i["name"] == index_name for i in inspector.get_indexes(table))


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "gates" not in tables:
        op.create_table(
            "gates",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("building_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("code", sa.String(length=32), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("gate_type", sa.String(length=32), nullable=False),
            sa.Column("location_description", sa.String(length=500), nullable=True),
            sa.Column("sequence", sa.Integer(), nullable=False, server_default="0"),
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
                ["society_id"], ["societies.id"], ondelete="RESTRICT", name="fk_gates_society_id"
            ),
            sa.ForeignKeyConstraint(
                ["building_id"], ["buildings.id"], ondelete="RESTRICT", name="fk_gates_building_id"
            ),
        )

    if "staff" not in tables:
        op.create_table(
            "staff",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("code", sa.String(length=32), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("phone", sa.String(length=20), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=True),
            sa.Column("photo_url", sa.String(length=500), nullable=True),
            sa.Column("staff_role", sa.String(length=32), nullable=False),
            sa.Column("department", sa.String(length=64), nullable=True),
            sa.Column("employment_type", sa.String(length=32), nullable=True),
            sa.Column("assigned_building_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("assigned_gate_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("joining_date", sa.Date(), nullable=True),
            sa.Column("leaving_date", sa.Date(), nullable=True),
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
                ["society_id"], ["societies.id"], ondelete="RESTRICT", name="fk_staff_society_id"
            ),
            sa.ForeignKeyConstraint(
                ["user_id"], ["users.id"], ondelete="SET NULL", name="fk_staff_user_id"
            ),
            sa.ForeignKeyConstraint(
                ["assigned_building_id"],
                ["buildings.id"],
                ondelete="SET NULL",
                name="fk_staff_assigned_building_id",
            ),
            sa.ForeignKeyConstraint(
                ["assigned_gate_id"],
                ["gates.id"],
                ondelete="SET NULL",
                name="fk_staff_assigned_gate_id",
            ),
        )

    if "shifts" not in tables:
        op.create_table(
            "shifts",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("staff_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("gate_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("building_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("shift_date", sa.Date(), nullable=False),
            sa.Column("shift_type", sa.String(length=32), nullable=False, server_default="custom"),
            sa.Column("scheduled_start", sa.DateTime(timezone=True), nullable=False),
            sa.Column("scheduled_end", sa.DateTime(timezone=True), nullable=False),
            sa.Column("actual_start", sa.DateTime(timezone=True), nullable=True),
            sa.Column("actual_end", sa.DateTime(timezone=True), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="scheduled"),
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
            sa.CheckConstraint(
                "scheduled_end > scheduled_start",
                name="ck_shifts_end_after_start",
            ),
            sa.ForeignKeyConstraint(
                ["society_id"], ["societies.id"], ondelete="RESTRICT", name="fk_shifts_society_id"
            ),
            sa.ForeignKeyConstraint(
                ["staff_id"], ["staff.id"], ondelete="RESTRICT", name="fk_shifts_staff_id"
            ),
            sa.ForeignKeyConstraint(
                ["gate_id"], ["gates.id"], ondelete="SET NULL", name="fk_shifts_gate_id"
            ),
            sa.ForeignKeyConstraint(
                ["building_id"], ["buildings.id"], ondelete="SET NULL", name="fk_shifts_building_id"
            ),
        )

    if "staff_attendance" not in tables:
        op.create_table(
            "staff_attendance",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("staff_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("shift_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("gate_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="checked_in"),
            sa.Column("check_in_time", sa.DateTime(timezone=True), nullable=False),
            sa.Column("check_out_time", sa.DateTime(timezone=True), nullable=True),
            sa.Column("recorded_by", postgresql.UUID(as_uuid=True), nullable=True),
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
            sa.CheckConstraint(
                "check_out_time IS NULL OR check_out_time >= check_in_time",
                name="ck_staff_attendance_checkout_after_checkin",
            ),
            sa.ForeignKeyConstraint(
                ["society_id"],
                ["societies.id"],
                ondelete="RESTRICT",
                name="fk_staff_attendance_society_id",
            ),
            sa.ForeignKeyConstraint(
                ["staff_id"], ["staff.id"], ondelete="RESTRICT", name="fk_staff_attendance_staff_id"
            ),
            sa.ForeignKeyConstraint(
                ["shift_id"], ["shifts.id"], ondelete="SET NULL", name="fk_staff_attendance_shift_id"
            ),
            sa.ForeignKeyConstraint(
                ["gate_id"], ["gates.id"], ondelete="SET NULL", name="fk_staff_attendance_gate_id"
            ),
        )

    inspector = sa.inspect(conn)

    gate_indexes = (
        ("ix_gates_society_id", ["society_id"], False),
        ("ix_gates_building_id", ["building_id"], False),
        ("ix_gates_is_active", ["is_active"], False),
        ("uq_gates_society_code", ["society_id", "code"], True),
        ("ix_gates_society_sequence", ["society_id", "sequence"], False),
    )
    for idx_name, cols, unique in gate_indexes:
        if "gates" in inspector.get_table_names() and not _has_index(inspector, "gates", idx_name):
            op.create_index(idx_name, "gates", cols, unique=unique)

    staff_indexes = (
        ("ix_staff_society_id", ["society_id"], False),
        ("ix_staff_user_id", ["user_id"], False),
        ("ix_staff_is_active", ["is_active"], False),
        ("ix_staff_society_name", ["society_id", "name"], False),
        ("ix_staff_society_phone", ["society_id", "phone"], False),
        ("ix_staff_staff_role", ["staff_role"], False),
        ("uq_staff_society_code", ["society_id", "code"], True),
    )
    for idx_name, cols, unique in staff_indexes:
        if "staff" in inspector.get_table_names() and not _has_index(inspector, "staff", idx_name):
            op.create_index(idx_name, "staff", cols, unique=unique)

    if "staff" in inspector.get_table_names() and not _has_index(
        inspector, "staff", "uq_staff_user_id_not_null"
    ):
        op.execute(
            """
            CREATE UNIQUE INDEX uq_staff_user_id_not_null
            ON staff (user_id)
            WHERE user_id IS NOT NULL
            """
        )

    shift_indexes = (
        ("ix_shifts_society_id", ["society_id"]),
        ("ix_shifts_staff_id", ["staff_id"]),
        ("ix_shifts_gate_id", ["gate_id"]),
        ("ix_shifts_status", ["status"]),
        ("ix_shifts_shift_date", ["shift_date"]),
        ("ix_shifts_society_date_status", ["society_id", "shift_date", "status"]),
        ("ix_shifts_staff_date", ["staff_id", "shift_date"]),
    )
    for idx_name, cols in shift_indexes:
        if "shifts" in inspector.get_table_names() and not _has_index(inspector, "shifts", idx_name):
            op.create_index(idx_name, "shifts", cols)

    if "shifts" in inspector.get_table_names() and not _has_index(
        inspector, "shifts", "uq_shifts_staff_active"
    ):
        op.execute(
            """
            CREATE UNIQUE INDEX uq_shifts_staff_active
            ON shifts (staff_id)
            WHERE status = 'active'
            """
        )

    attendance_indexes = (
        ("ix_staff_attendance_society_id", ["society_id"]),
        ("ix_staff_attendance_staff_id", ["staff_id"]),
        ("ix_staff_attendance_shift_id", ["shift_id"]),
        ("ix_staff_attendance_gate_id", ["gate_id"]),
        ("ix_staff_attendance_check_in_time", ["check_in_time"]),
        ("ix_staff_attendance_staff_status", ["staff_id", "status"]),
    )
    for idx_name, cols in attendance_indexes:
        if "staff_attendance" in inspector.get_table_names() and not _has_index(
            inspector, "staff_attendance", idx_name
        ):
            op.create_index(idx_name, "staff_attendance", cols)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "staff_attendance" in tables:
        for idx in (
            "ix_staff_attendance_staff_status",
            "ix_staff_attendance_check_in_time",
            "ix_staff_attendance_gate_id",
            "ix_staff_attendance_shift_id",
            "ix_staff_attendance_staff_id",
            "ix_staff_attendance_society_id",
        ):
            if _has_index(inspector, "staff_attendance", idx):
                op.drop_index(idx, table_name="staff_attendance")
        op.drop_table("staff_attendance")

    if "shifts" in tables:
        for idx in (
            "uq_shifts_staff_active",
            "ix_shifts_staff_date",
            "ix_shifts_society_date_status",
            "ix_shifts_shift_date",
            "ix_shifts_status",
            "ix_shifts_gate_id",
            "ix_shifts_staff_id",
            "ix_shifts_society_id",
        ):
            if _has_index(inspector, "shifts", idx):
                op.drop_index(idx, table_name="shifts")
        op.drop_table("shifts")

    if "staff" in tables:
        for idx in (
            "uq_staff_user_id_not_null",
            "uq_staff_society_code",
            "ix_staff_staff_role",
            "ix_staff_society_phone",
            "ix_staff_society_name",
            "ix_staff_is_active",
            "ix_staff_user_id",
            "ix_staff_society_id",
        ):
            if _has_index(inspector, "staff", idx):
                op.drop_index(idx, table_name="staff")
        op.drop_table("staff")

    if "gates" in tables:
        for idx in (
            "ix_gates_society_sequence",
            "uq_gates_society_code",
            "ix_gates_is_active",
            "ix_gates_building_id",
            "ix_gates_society_id",
        ):
            if _has_index(inspector, "gates", idx):
                op.drop_index(idx, table_name="gates")
        op.drop_table("gates")
