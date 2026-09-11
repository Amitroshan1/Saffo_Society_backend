"""Create visitors and visits tables (Phase 6)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_visitors_visits"
down_revision: Union[str, None] = "0007_occupancy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_index(inspector: sa.Inspector, table: str, index_name: str) -> bool:
    return any(i["name"] == index_name for i in inspector.get_indexes(table))


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "visitors" not in tables:
        op.create_table(
            "visitors",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("phone", sa.String(length=20), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=True),
            sa.Column("photo_url", sa.String(length=500), nullable=True),
            sa.Column("government_id_type", sa.String(length=50), nullable=True),
            sa.Column("government_id_number", sa.String(length=100), nullable=True),
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
                name="fk_visitors_society_id",
            ),
        )

    if "visits" not in tables:
        op.create_table(
            "visits",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("building_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("wing_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("flat_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("occupancy_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("visitor_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("purpose", sa.String(length=200), nullable=False),
            sa.Column("visitor_type", sa.String(length=32), nullable=False),
            sa.Column("pass_type", sa.String(length=32), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="scheduled"),
            sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expected_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("check_in_time", sa.DateTime(timezone=True), nullable=True),
            sa.Column("check_out_time", sa.DateTime(timezone=True), nullable=True),
            sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("gate_in_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("gate_out_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("vehicle_number", sa.String(length=30), nullable=True),
            sa.Column("number_of_people", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("qr_code", sa.String(length=255), nullable=True),
            sa.Column("otp", sa.String(length=20), nullable=True),
            sa.Column("is_preapproved", sa.Boolean(), nullable=False, server_default=sa.text("false")),
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
                "check_out_time IS NULL OR check_in_time IS NULL OR check_out_time >= check_in_time",
                name="ck_visits_checkout_after_checkin",
            ),
            sa.CheckConstraint("number_of_people >= 1", name="ck_visits_number_of_people_positive"),
            sa.ForeignKeyConstraint(
                ["society_id"],
                ["societies.id"],
                ondelete="RESTRICT",
                name="fk_visits_society_id",
            ),
            sa.ForeignKeyConstraint(
                ["building_id"],
                ["buildings.id"],
                ondelete="RESTRICT",
                name="fk_visits_building_id",
            ),
            sa.ForeignKeyConstraint(
                ["wing_id"],
                ["wings.id"],
                ondelete="RESTRICT",
                name="fk_visits_wing_id",
            ),
            sa.ForeignKeyConstraint(
                ["flat_id"],
                ["flats.id"],
                ondelete="RESTRICT",
                name="fk_visits_flat_id",
            ),
            sa.ForeignKeyConstraint(
                ["occupancy_id"],
                ["occupancies.id"],
                ondelete="RESTRICT",
                name="fk_visits_occupancy_id",
            ),
            sa.ForeignKeyConstraint(
                ["visitor_id"],
                ["visitors.id"],
                ondelete="RESTRICT",
                name="fk_visits_visitor_id",
            ),
        )

    inspector = sa.inspect(conn)

    visitor_indexes = (
        ("ix_visitors_society_id", ["society_id"]),
        ("ix_visitors_phone", ["phone"]),
        ("ix_visitors_is_active", ["is_active"]),
        ("ix_visitors_society_name", ["society_id", "name"]),
        ("ix_visitors_society_govt_id", ["society_id", "government_id_type", "government_id_number"]),
    )
    for idx_name, cols in visitor_indexes:
        if "visitors" in inspector.get_table_names() and not _has_index(inspector, "visitors", idx_name):
            op.create_index(idx_name, "visitors", cols)

    visit_indexes = (
        ("ix_visits_society_id", ["society_id"]),
        ("ix_visits_building_id", ["building_id"]),
        ("ix_visits_wing_id", ["wing_id"]),
        ("ix_visits_flat_id", ["flat_id"]),
        ("ix_visits_occupancy_id", ["occupancy_id"]),
        ("ix_visits_visitor_id", ["visitor_id"]),
        ("ix_visits_status", ["status"]),
        ("ix_visits_visitor_type", ["visitor_type"]),
        ("ix_visits_expected_at", ["expected_at"]),
        ("ix_visits_check_in_time", ["check_in_time"]),
        ("ix_visits_society_status_expected", ["society_id", "status", "expected_at"]),
        ("ix_visits_society_created_at", ["society_id", "created_at"]),
    )
    for idx_name, cols in visit_indexes:
        if "visits" in inspector.get_table_names() and not _has_index(inspector, "visits", idx_name):
            op.create_index(idx_name, "visits", cols)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "visits" in tables:
        for idx in (
            "ix_visits_society_created_at",
            "ix_visits_society_status_expected",
            "ix_visits_check_in_time",
            "ix_visits_expected_at",
            "ix_visits_visitor_type",
            "ix_visits_status",
            "ix_visits_visitor_id",
            "ix_visits_occupancy_id",
            "ix_visits_flat_id",
            "ix_visits_wing_id",
            "ix_visits_building_id",
            "ix_visits_society_id",
        ):
            if _has_index(inspector, "visits", idx):
                op.drop_index(idx, table_name="visits")
        op.drop_table("visits")

    if "visitors" in tables:
        for idx in (
            "ix_visitors_society_govt_id",
            "ix_visitors_society_name",
            "ix_visitors_is_active",
            "ix_visitors_phone",
            "ix_visitors_society_id",
        ):
            if _has_index(inspector, "visitors", idx):
                op.drop_index(idx, table_name="visitors")
        op.drop_table("visitors")
