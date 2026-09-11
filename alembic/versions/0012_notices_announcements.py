"""Create notices & announcements tables (Phase 11)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_notices_announcements"
down_revision: Union[str, None] = "0011_billing_accounting"
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

    if "notices" not in inspector.get_table_names():
        op.create_table(
            "notices",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("notice_number", sa.String(length=32), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("summary", sa.String(length=500), nullable=True),
            sa.Column("body_text", sa.Text(), nullable=False, server_default=""),
            sa.Column("body_html", sa.Text(), nullable=True),
            sa.Column("category", sa.String(length=32), nullable=False, server_default="general"),
            sa.Column("priority", sa.String(length=16), nullable=False, server_default="normal"),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"),
            sa.Column("publish_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("cancel_reason", sa.String(length=500), nullable=True),
            sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("pin_until", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "requires_acknowledgement",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column("acknowledgement_due_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("audience_count_snapshot", sa.Integer(), nullable=True),
            sa.Column("published_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("created_by_staff_id", postgresql.UUID(as_uuid=True), nullable=True),
            *_common_audit_columns(),
            sa.ForeignKeyConstraint(
                ["society_id"], ["societies.id"], ondelete="RESTRICT", name="fk_notices_society_id"
            ),
            sa.ForeignKeyConstraint(
                ["published_by_user_id"],
                ["users.id"],
                ondelete="SET NULL",
                name="fk_notices_published_by_user_id",
            ),
            sa.ForeignKeyConstraint(
                ["created_by_staff_id"],
                ["staff.id"],
                ondelete="SET NULL",
                name="fk_notices_created_by_staff_id",
            ),
            sa.UniqueConstraint("society_id", "notice_number", name="uq_notices_society_number"),
        )

    inspector = sa.inspect(conn)
    _create_indexes(
        inspector,
        "notices",
        (
            ("ix_notices_society_id", ["society_id"]),
            ("ix_notices_society_status", ["society_id", "status"]),
            ("ix_notices_society_category", ["society_id", "category"]),
            ("ix_notices_society_priority", ["society_id", "priority"]),
            ("ix_notices_society_is_pinned", ["society_id", "is_pinned"]),
            ("ix_notices_publish_at", ["publish_at"]),
            ("ix_notices_expires_at", ["expires_at"]),
            ("ix_notices_notice_number", ["notice_number"]),
            ("ix_notices_society_is_active", ["society_id", "is_active"]),
        ),
    )

    inspector = sa.inspect(conn)
    if "notice_targets" not in inspector.get_table_names():
        op.create_table(
            "notice_targets",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("notice_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("target_type", sa.String(length=32), nullable=False),
            sa.Column("building_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("wing_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("flat_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("resident_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("committee_role", sa.String(length=64), nullable=True),
            *_common_audit_columns(),
            sa.ForeignKeyConstraint(
                ["society_id"], ["societies.id"], ondelete="RESTRICT", name="fk_notice_targets_society_id"
            ),
            sa.ForeignKeyConstraint(
                ["notice_id"], ["notices.id"], ondelete="CASCADE", name="fk_notice_targets_notice_id"
            ),
            sa.ForeignKeyConstraint(
                ["building_id"], ["buildings.id"], ondelete="RESTRICT", name="fk_notice_targets_building_id"
            ),
            sa.ForeignKeyConstraint(
                ["wing_id"], ["wings.id"], ondelete="RESTRICT", name="fk_notice_targets_wing_id"
            ),
            sa.ForeignKeyConstraint(
                ["flat_id"], ["flats.id"], ondelete="RESTRICT", name="fk_notice_targets_flat_id"
            ),
            sa.ForeignKeyConstraint(
                ["resident_id"], ["residents.id"], ondelete="RESTRICT", name="fk_notice_targets_resident_id"
            ),
        )

    inspector = sa.inspect(conn)
    _create_indexes(
        inspector,
        "notice_targets",
        (
            ("ix_notice_targets_notice_id", ["notice_id"]),
            ("ix_notice_targets_society_id", ["society_id"]),
            ("ix_notice_targets_target_type", ["target_type"]),
            ("ix_notice_targets_building_id", ["building_id"]),
            ("ix_notice_targets_wing_id", ["wing_id"]),
            ("ix_notice_targets_flat_id", ["flat_id"]),
            ("ix_notice_targets_resident_id", ["resident_id"]),
        ),
    )

    inspector = sa.inspect(conn)
    if "notice_attachments" not in inspector.get_table_names():
        op.create_table(
            "notice_attachments",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("notice_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("file_name", sa.String(length=255), nullable=False),
            sa.Column("file_url", sa.String(length=500), nullable=False),
            sa.Column("mime_type", sa.String(length=100), nullable=True),
            sa.Column("file_size_bytes", sa.Integer(), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
            ),
            sa.ForeignKeyConstraint(
                ["notice_id"], ["notices.id"], ondelete="CASCADE", name="fk_notice_attachments_notice_id"
            ),
        )

    inspector = sa.inspect(conn)
    _create_indexes(
        inspector,
        "notice_attachments",
        (
            ("ix_notice_attachments_notice_id", ["notice_id"]),
            ("ix_notice_attachments_created_at", ["created_at"]),
        ),
    )

    inspector = sa.inspect(conn)
    if "notice_reads" not in inspector.get_table_names():
        op.create_table(
            "notice_reads",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("notice_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("resident_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("first_read_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("read_count", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("read_source", sa.String(length=32), nullable=False, server_default="portal"),
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
                ["society_id"], ["societies.id"], ondelete="RESTRICT", name="fk_notice_reads_society_id"
            ),
            sa.ForeignKeyConstraint(
                ["notice_id"], ["notices.id"], ondelete="CASCADE", name="fk_notice_reads_notice_id"
            ),
            sa.ForeignKeyConstraint(
                ["resident_id"], ["residents.id"], ondelete="RESTRICT", name="fk_notice_reads_resident_id"
            ),
            sa.UniqueConstraint("notice_id", "resident_id", name="uq_notice_reads_notice_resident"),
        )

    inspector = sa.inspect(conn)
    _create_indexes(
        inspector,
        "notice_reads",
        (
            ("ix_notice_reads_society_resident", ["society_id", "resident_id"]),
            ("ix_notice_reads_notice_id", ["notice_id"]),
            ("ix_notice_reads_first_read_at", ["first_read_at"]),
        ),
    )

    inspector = sa.inspect(conn)
    if "notice_acknowledgements" not in inspector.get_table_names():
        op.create_table(
            "notice_acknowledgements",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("notice_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("resident_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("ack_source", sa.String(length=32), nullable=False, server_default="portal"),
            sa.Column("ip_hash", sa.String(length=128), nullable=True),
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
                ["society_id"], ["societies.id"], ondelete="RESTRICT", name="fk_notice_acks_society_id"
            ),
            sa.ForeignKeyConstraint(
                ["notice_id"], ["notices.id"], ondelete="CASCADE", name="fk_notice_acks_notice_id"
            ),
            sa.ForeignKeyConstraint(
                ["resident_id"], ["residents.id"], ondelete="RESTRICT", name="fk_notice_acks_resident_id"
            ),
            sa.UniqueConstraint("notice_id", "resident_id", name="uq_notice_acks_notice_resident"),
        )

    inspector = sa.inspect(conn)
    _create_indexes(
        inspector,
        "notice_acknowledgements",
        (
            ("ix_notice_acks_society_notice", ["society_id", "notice_id"]),
            ("ix_notice_acks_acknowledged_at", ["acknowledged_at"]),
        ),
    )


def downgrade() -> None:
    op.drop_table("notice_acknowledgements")
    op.drop_table("notice_reads")
    op.drop_table("notice_attachments")
    op.drop_table("notice_targets")
    op.drop_table("notices")
