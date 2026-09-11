"""Create platform control-plane tables (Phase 17)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018_platform_control_plane"
down_revision: Union[str, None] = "0017_reports_analytics"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _audit_cols():
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


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    # Widen users.role for platform_* roles (platform_auditor = 17 chars; keep buffer)
    if "users" in tables:
        cols = {c["name"]: c for c in inspector.get_columns("users")}
        role_col = cols.get("role")
        if role_col is not None:
            op.alter_column(
                "users",
                "role",
                existing_type=sa.String(length=20),
                type_=sa.String(length=32),
                existing_nullable=False,
            )

    if "tenants" not in tables:
        op.create_table(
            "tenants",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("code", sa.String(64), nullable=False),
            sa.Column("display_name", sa.String(200), nullable=True),
            sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
            sa.Column("isolation_mode", sa.String(32), nullable=False, server_default="shared"),
            sa.Column("region", sa.String(64), nullable=False, server_default="IN"),
            sa.Column("timezone", sa.String(64), nullable=False, server_default="Asia/Kolkata"),
            sa.Column("admin_email", sa.String(255), nullable=True),
            sa.Column("plan_code", sa.String(64), nullable=True),
            sa.Column(
                "connection_meta",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("provisioned_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("delete_after", sa.DateTime(timezone=True), nullable=True),
            *_audit_cols(),
            sa.ForeignKeyConstraint(["society_id"], ["societies.id"], ondelete="SET NULL"),
            sa.UniqueConstraint("code", name="uq_tenants_code"),
            sa.UniqueConstraint("society_id", name="uq_tenants_society_id"),
        )
        op.create_index("ix_tenants_status", "tenants", ["status"])
        op.create_index("ix_tenants_code", "tenants", ["code"])

    if "subscription_plans" not in tables:
        op.create_table(
            "subscription_plans",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("code", sa.String(64), nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("billing_period", sa.String(32), nullable=False, server_default="monthly"),
            sa.Column("price_minor", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
            sa.Column("trial_days", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "limits_json",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "features_json",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            *_audit_cols(),
            sa.UniqueConstraint("code", name="uq_subscription_plans_code"),
        )
        op.create_index("ix_subscription_plans_code", "subscription_plans", ["code"])

    if "tenant_subscriptions" not in tables:
        op.create_table(
            "tenant_subscriptions",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="trialing"),
            sa.Column("billing_period", sa.String(32), nullable=False),
            sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("grace_ends_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("auto_renew", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("external_ref", sa.String(128), nullable=True),
            *_audit_cols(),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["plan_id"], ["subscription_plans.id"], ondelete="RESTRICT"),
        )
        op.create_index("ix_tenant_subscriptions_tenant_id", "tenant_subscriptions", ["tenant_id"])
        op.create_index("ix_tenant_subscriptions_status", "tenant_subscriptions", ["status"])

    if "licenses" not in tables:
        op.create_table(
            "licenses",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("license_key", sa.String(128), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="active"),
            sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "limits_json",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "features_json",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("signature", sa.String(255), nullable=True),
            *_audit_cols(),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("license_key", name="uq_licenses_key"),
        )
        op.create_index("ix_licenses_tenant_id", "licenses", ["tenant_id"])
        op.create_index("ix_licenses_status", "licenses", ["status"])

    if "feature_flags" not in tables:
        op.create_table(
            "feature_flags",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("key", sa.String(128), nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column(
                "default_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")
            ),
            sa.Column("rollout_percent", sa.Integer(), nullable=False, server_default="100"),
            sa.Column(
                "tags_json",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
            *_audit_cols(),
            sa.UniqueConstraint("key", name="uq_feature_flags_key"),
        )
        op.create_index("ix_feature_flags_key", "feature_flags", ["key"])

    if "tenant_feature_flags" not in tables:
        op.create_table(
            "tenant_feature_flags",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("flag_key", sa.String(128), nullable=False),
            sa.Column("mode", sa.String(16), nullable=False, server_default="inherit"),
            *_audit_cols(),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("tenant_id", "flag_key", name="uq_tenant_feature_flags"),
        )
        op.create_index("ix_tenant_feature_flags_tenant_id", "tenant_feature_flags", ["tenant_id"])

    if "platform_settings" not in tables:
        op.create_table(
            "platform_settings",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("group_key", sa.String(64), nullable=False),
            sa.Column(
                "values_json",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "secret_refs_json",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            *_audit_cols(),
            sa.UniqueConstraint("group_key", name="uq_platform_settings_group"),
        )
        op.create_index("ix_platform_settings_group_key", "platform_settings", ["group_key"])

    if "platform_announcements" not in tables:
        op.create_table(
            "platform_announcements",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("title", sa.String(300), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column(
                "announcement_type", sa.String(32), nullable=False, server_default="broadcast"
            ),
            sa.Column("priority", sa.String(16), nullable=False, server_default="normal"),
            sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
            sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "target_roles_json",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'[\"admin\"]'::jsonb"),
            ),
            *_audit_cols(),
        )
        op.create_index("ix_platform_announcements_status", "platform_announcements", ["status"])

    if "platform_announcement_deliveries" not in tables:
        op.create_table(
            "platform_announcement_deliveries",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("announcement_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
            sa.Column("recipient_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "metadata_json",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["announcement_id"], ["platform_announcements.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
            sa.UniqueConstraint(
                "announcement_id", "tenant_id", name="uq_platform_announcement_delivery"
            ),
        )

    if "platform_audit_logs" not in tables:
        op.create_table(
            "platform_audit_logs",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("actor_role", sa.String(32), nullable=True),
            sa.Column("action", sa.String(128), nullable=False),
            sa.Column("resource_type", sa.String(64), nullable=False),
            sa.Column("resource_id", sa.String(64), nullable=True),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("before_json", postgresql.JSONB(), nullable=True),
            sa.Column("after_json", postgresql.JSONB(), nullable=True),
            sa.Column("ip", sa.String(64), nullable=True),
            sa.Column("user_agent", sa.String(500), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
        )
        op.create_index("ix_platform_audit_logs_action", "platform_audit_logs", ["action"])
        op.create_index("ix_platform_audit_logs_created_at", "platform_audit_logs", ["created_at"])

    if "platform_impersonation_sessions" not in tables:
        op.create_table(
            "platform_impersonation_sessions",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("impersonator_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("target_user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("reason", sa.String(500), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="active"),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("ip", sa.String(64), nullable=True),
            sa.Column("user_agent", sa.String(500), nullable=True),
            sa.Column(
                "metadata_json",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        )
        op.create_index(
            "ix_platform_impersonation_sessions_tenant_id",
            "platform_impersonation_sessions",
            ["tenant_id"],
        )

    if "platform_maintenance_windows" not in tables:
        op.create_table(
            "platform_maintenance_windows",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column(
                "message",
                sa.Text(),
                nullable=False,
                server_default="Platform under maintenance",
            ),
            sa.Column(
                "allow_platform_admin",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
            *_audit_cols(),
        )
        op.create_index(
            "ix_platform_maintenance_windows_enabled",
            "platform_maintenance_windows",
            ["enabled"],
        )

    if "platform_job_runs" not in tables:
        op.create_table(
            "platform_job_runs",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("job_key", sa.String(128), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("duration_ms", sa.Integer(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column(
                "result_json",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
        )
        op.create_index("ix_platform_job_runs_job_key", "platform_job_runs", ["job_key"])

    if "platform_metric_daily" not in tables:
        op.create_table(
            "platform_metric_daily",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("metric_date", sa.Date(), nullable=False),
            sa.Column("metric_key", sa.String(128), nullable=False),
            sa.Column("value_num", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("value_int", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column(
                "dimensions_json",
                postgresql.JSONB(),
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
            sa.UniqueConstraint("metric_date", "metric_key", name="uq_platform_metric_daily"),
        )
        op.create_index("ix_platform_metric_daily_metric_date", "platform_metric_daily", ["metric_date"])
        op.create_index("ix_platform_metric_daily_metric_key", "platform_metric_daily", ["metric_key"])


def downgrade() -> None:
    for table in (
        "platform_metric_daily",
        "platform_job_runs",
        "platform_maintenance_windows",
        "platform_impersonation_sessions",
        "platform_audit_logs",
        "platform_announcement_deliveries",
        "platform_announcements",
        "platform_settings",
        "tenant_feature_flags",
        "feature_flags",
        "licenses",
        "tenant_subscriptions",
        "subscription_plans",
        "tenants",
    ):
        op.drop_table(table)

    op.alter_column(
        "users",
        "role",
        existing_type=sa.String(length=32),
        type_=sa.String(length=20),
        existing_nullable=False,
    )
