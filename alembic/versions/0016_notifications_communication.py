"""Create notifications & communication tables (Phase 15)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016_notifications_communication"
down_revision: Union[str, None] = "0015_parking_management"
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

    if "notification_templates" not in inspector.get_table_names():
        op.create_table(
            "notification_templates",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("code", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("category", sa.String(length=64), nullable=False),
            sa.Column("channel", sa.String(length=32), nullable=False),
            sa.Column("subject_template", sa.String(length=500), nullable=True),
            sa.Column("body_template", sa.Text(), nullable=False),
            sa.Column(
                "priority", sa.String(length=16), nullable=False, server_default="normal"
            ),
            sa.Column(
                "is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")
            ),
            *_common_audit_columns(),
            sa.ForeignKeyConstraint(
                ["society_id"],
                ["societies.id"],
                ondelete="RESTRICT",
                name="fk_notification_templates_society_id",
            ),
            sa.UniqueConstraint(
                "society_id", "code", name="uq_notification_templates_society_code"
            ),
        )

    inspector = sa.inspect(conn)
    _create_indexes(
        inspector,
        "notification_templates",
        (
            ("ix_notification_templates_society_id", ["society_id"]),
            ("ix_notification_templates_category", ["category"]),
            ("ix_notification_templates_channel", ["channel"]),
            ("ix_notification_templates_is_active", ["is_active"]),
        ),
    )

    inspector = sa.inspect(conn)
    if "notifications" not in inspector.get_table_names():
        op.create_table(
            "notifications",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("source_module", sa.String(length=64), nullable=False),
            sa.Column("source_event", sa.String(length=100), nullable=True),
            sa.Column("category", sa.String(length=64), nullable=False),
            sa.Column(
                "priority", sa.String(length=16), nullable=False, server_default="normal"
            ),
            sa.Column("title", sa.String(length=300), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column(
                "payload_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("target_type", sa.String(length=32), nullable=False),
            sa.Column("target_role", sa.String(length=32), nullable=True),
            sa.Column("building_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("wing_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("flat_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("resident_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column(
                "status", sa.String(length=16), nullable=False, server_default="pending"
            ),
            sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
            *_common_audit_columns(),
            sa.ForeignKeyConstraint(
                ["society_id"],
                ["societies.id"],
                ondelete="RESTRICT",
                name="fk_notifications_society_id",
            ),
            sa.ForeignKeyConstraint(
                ["template_id"],
                ["notification_templates.id"],
                ondelete="SET NULL",
                name="fk_notifications_template_id",
            ),
        )

    inspector = sa.inspect(conn)
    _create_indexes(
        inspector,
        "notifications",
        (
            ("ix_notifications_society_id", ["society_id"]),
            ("ix_notifications_status", ["status"]),
            ("ix_notifications_category", ["category"]),
            ("ix_notifications_user_id", ["user_id"]),
            ("ix_notifications_resident_id", ["resident_id"]),
            ("ix_notifications_source_module", ["source_module"]),
            ("ix_notifications_scheduled_for", ["scheduled_for"]),
            ("ix_notifications_priority", ["priority"]),
        ),
    )

    inspector = sa.inspect(conn)
    if "notification_deliveries" not in inspector.get_table_names():
        op.create_table(
            "notification_deliveries",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("notification_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("channel", sa.String(length=32), nullable=False),
            sa.Column("recipient_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("recipient_resident_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("recipient_address", sa.String(length=255), nullable=True),
            sa.Column(
                "status", sa.String(length=16), nullable=False, server_default="queued"
            ),
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error_message", sa.String(length=1000), nullable=True),
            sa.Column(
                "provider_response",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
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
                name="fk_notification_deliveries_society_id",
            ),
            sa.ForeignKeyConstraint(
                ["notification_id"],
                ["notifications.id"],
                ondelete="CASCADE",
                name="fk_notification_deliveries_notification_id",
            ),
            sa.ForeignKeyConstraint(
                ["recipient_user_id"],
                ["users.id"],
                ondelete="SET NULL",
                name="fk_notification_deliveries_recipient_user_id",
            ),
            sa.ForeignKeyConstraint(
                ["recipient_resident_id"],
                ["residents.id"],
                ondelete="SET NULL",
                name="fk_notification_deliveries_recipient_resident_id",
            ),
        )

    inspector = sa.inspect(conn)
    _create_indexes(
        inspector,
        "notification_deliveries",
        (
            ("ix_notification_deliveries_society_id", ["society_id"]),
            ("ix_notification_deliveries_notification_id", ["notification_id"]),
            ("ix_notification_deliveries_status", ["status"]),
            ("ix_notification_deliveries_channel", ["channel"]),
            ("ix_notification_deliveries_recipient_user_id", ["recipient_user_id"]),
        ),
    )

    inspector = sa.inspect(conn)
    if "notification_preferences" not in inspector.get_table_names():
        op.create_table(
            "notification_preferences",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("resident_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column(
                "email_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")
            ),
            sa.Column(
                "sms_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")
            ),
            sa.Column(
                "push_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")
            ),
            sa.Column(
                "marketing_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column(
                "system_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")
            ),
            sa.Column(
                "emergency_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            *_common_audit_columns(),
            sa.ForeignKeyConstraint(
                ["society_id"],
                ["societies.id"],
                ondelete="RESTRICT",
                name="fk_notification_preferences_society_id",
            ),
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["users.id"],
                ondelete="RESTRICT",
                name="fk_notification_preferences_user_id",
            ),
            sa.ForeignKeyConstraint(
                ["resident_id"],
                ["residents.id"],
                ondelete="SET NULL",
                name="fk_notification_preferences_resident_id",
            ),
            sa.UniqueConstraint(
                "society_id", "user_id", name="uq_notification_preferences_society_user"
            ),
        )

    inspector = sa.inspect(conn)
    _create_indexes(
        inspector,
        "notification_preferences",
        (
            ("ix_notification_preferences_society_id", ["society_id"]),
            ("ix_notification_preferences_user_id", ["user_id"]),
        ),
    )

    inspector = sa.inspect(conn)
    if "scheduled_notifications" not in inspector.get_table_names():
        op.create_table(
            "scheduled_notifications",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("title", sa.String(length=300), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column(
                "channels",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[\"in_app\"]'::jsonb"),
            ),
            sa.Column("target_type", sa.String(length=32), nullable=False),
            sa.Column("target_role", sa.String(length=32), nullable=True),
            sa.Column("building_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("wing_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("flat_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column(
                "resident_ids",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
            sa.Column(
                "priority", sa.String(length=16), nullable=False, server_default="normal"
            ),
            sa.Column(
                "category", sa.String(length=64), nullable=False, server_default="system"
            ),
            sa.Column("schedule_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("recurrence", sa.String(length=32), nullable=True),
            sa.Column(
                "status", sa.String(length=16), nullable=False, server_default="scheduled"
            ),
            sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_notification_id", postgresql.UUID(as_uuid=True), nullable=True),
            *_common_audit_columns(),
            sa.ForeignKeyConstraint(
                ["society_id"],
                ["societies.id"],
                ondelete="RESTRICT",
                name="fk_scheduled_notifications_society_id",
            ),
            sa.ForeignKeyConstraint(
                ["template_id"],
                ["notification_templates.id"],
                ondelete="SET NULL",
                name="fk_scheduled_notifications_template_id",
            ),
        )

    inspector = sa.inspect(conn)
    _create_indexes(
        inspector,
        "scheduled_notifications",
        (
            ("ix_scheduled_notifications_society_id", ["society_id"]),
            ("ix_scheduled_notifications_status", ["status"]),
            ("ix_scheduled_notifications_schedule_at", ["schedule_at"]),
            ("ix_scheduled_notifications_next_run_at", ["next_run_at"]),
        ),
    )


def downgrade() -> None:
    op.drop_table("scheduled_notifications")
    op.drop_table("notification_preferences")
    op.drop_table("notification_deliveries")
    op.drop_table("notifications")
    op.drop_table("notification_templates")
