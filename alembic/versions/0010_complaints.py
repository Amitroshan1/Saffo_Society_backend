"""Create complaints, complaint_comments, complaint_attachments (Phase 9)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_complaints"
down_revision: Union[str, None] = "0009_staff_gate_ops"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_index(inspector: sa.Inspector, table: str, index_name: str) -> bool:
    return any(i["name"] == index_name for i in inspector.get_indexes(table))


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "complaints" not in tables:
        op.create_table(
            "complaints",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("building_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("wing_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("flat_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("occupancy_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("resident_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("assigned_staff_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("category", sa.String(length=64), nullable=False),
            sa.Column("subcategory", sa.String(length=64), nullable=True),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("priority", sa.String(length=32), nullable=False, server_default="medium"),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
            sa.Column("source", sa.String(length=32), nullable=False, server_default="resident"),
            sa.Column("expected_resolution", sa.DateTime(timezone=True), nullable=True),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
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
                ["society_id"], ["societies.id"], ondelete="RESTRICT", name="fk_complaints_society_id"
            ),
            sa.ForeignKeyConstraint(
                ["building_id"],
                ["buildings.id"],
                ondelete="RESTRICT",
                name="fk_complaints_building_id",
            ),
            sa.ForeignKeyConstraint(
                ["wing_id"], ["wings.id"], ondelete="RESTRICT", name="fk_complaints_wing_id"
            ),
            sa.ForeignKeyConstraint(
                ["flat_id"], ["flats.id"], ondelete="RESTRICT", name="fk_complaints_flat_id"
            ),
            sa.ForeignKeyConstraint(
                ["occupancy_id"],
                ["occupancies.id"],
                ondelete="RESTRICT",
                name="fk_complaints_occupancy_id",
            ),
            sa.ForeignKeyConstraint(
                ["resident_id"],
                ["residents.id"],
                ondelete="RESTRICT",
                name="fk_complaints_resident_id",
            ),
            sa.ForeignKeyConstraint(
                ["assigned_staff_id"],
                ["staff.id"],
                ondelete="SET NULL",
                name="fk_complaints_assigned_staff_id",
            ),
        )

    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if "complaints" in tables:
        for name, cols in (
            ("ix_complaints_society_id", ["society_id"]),
            ("ix_complaints_status", ["status"]),
            ("ix_complaints_priority", ["priority"]),
            ("ix_complaints_assigned_staff_id", ["assigned_staff_id"]),
            ("ix_complaints_resident_id", ["resident_id"]),
            ("ix_complaints_created_at", ["created_at"]),
            ("ix_complaints_society_status", ["society_id", "status"]),
            ("ix_complaints_flat_id", ["flat_id"]),
            ("ix_complaints_occupancy_id", ["occupancy_id"]),
            ("ix_complaints_is_active", ["is_active"]),
        ):
            if not _has_index(inspector, "complaints", name):
                op.create_index(name, "complaints", cols)

    if "complaint_comments" not in tables:
        op.create_table(
            "complaint_comments",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("complaint_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("author_type", sa.String(length=32), nullable=False),
            sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
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
                ["complaint_id"],
                ["complaints.id"],
                ondelete="CASCADE",
                name="fk_complaint_comments_complaint_id",
            ),
        )

    inspector = sa.inspect(conn)
    if "complaint_comments" in inspector.get_table_names():
        for name, cols in (
            ("ix_complaint_comments_complaint_id", ["complaint_id"]),
            ("ix_complaint_comments_created_at", ["created_at"]),
        ):
            if not _has_index(inspector, "complaint_comments", name):
                op.create_index(name, "complaint_comments", cols)

    inspector = sa.inspect(conn)
    if "complaint_attachments" not in inspector.get_table_names():
        op.create_table(
            "complaint_attachments",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("complaint_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("file_name", sa.String(length=255), nullable=False),
            sa.Column("file_url", sa.String(length=500), nullable=False),
            sa.Column("mime_type", sa.String(length=100), nullable=True),
            sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=True),
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
                ["complaint_id"],
                ["complaints.id"],
                ondelete="CASCADE",
                name="fk_complaint_attachments_complaint_id",
            ),
        )

    inspector = sa.inspect(conn)
    if "complaint_attachments" in inspector.get_table_names():
        for name, cols in (
            ("ix_complaint_attachments_complaint_id", ["complaint_id"]),
            ("ix_complaint_attachments_created_at", ["created_at"]),
        ):
            if not _has_index(inspector, "complaint_attachments", name):
                op.create_index(name, "complaint_attachments", cols)


def downgrade() -> None:
    op.drop_table("complaint_attachments")
    op.drop_table("complaint_comments")
    op.drop_table("complaints")
