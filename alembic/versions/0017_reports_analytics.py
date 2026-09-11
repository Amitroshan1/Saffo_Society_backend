"""Create reports & analytics tables (Phase 16)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017_reports_analytics"
down_revision: Union[str, None] = "0016_notifications_communication"
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


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "analytics_report_definitions" not in tables:
        op.create_table(
            "analytics_report_definitions",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("report_key", sa.String(128), nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("category", sa.String(64), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("strategy", sa.String(32), nullable=False, server_default="fact_query"),
            sa.Column("roles_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("columns_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("default_filters_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("chart_types_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            *_common_audit_columns(),
            sa.ForeignKeyConstraint(["society_id"], ["societies.id"], ondelete="RESTRICT"),
            sa.UniqueConstraint("society_id", "report_key", name="uq_analytics_report_defs_society_key"),
        )
    if "analytics_kpi_definitions" not in tables:
        op.create_table(
            "analytics_kpi_definitions",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("kpi_key", sa.String(128), nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("category", sa.String(64), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("unit", sa.String(32), nullable=False, server_default="count"),
            sa.Column("formula_type", sa.String(32), nullable=False, server_default="direct_fact"),
            sa.Column("aggregation", sa.String(32), nullable=False, server_default="latest"),
            sa.Column("grain", sa.String(32), nullable=False, server_default="society"),
            sa.Column("refresh_policy", sa.String(32), nullable=False, server_default="daily"),
            sa.Column("roles_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("metric_key", sa.String(128), nullable=True),
            sa.Column("numerator_key", sa.String(128), nullable=True),
            sa.Column("denominator_key", sa.String(128), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            *_common_audit_columns(),
            sa.ForeignKeyConstraint(["society_id"], ["societies.id"], ondelete="RESTRICT"),
            sa.UniqueConstraint("society_id", "kpi_key", name="uq_analytics_kpi_defs_society_key"),
        )
    if "analytics_dashboard_layouts" not in tables:
        op.create_table(
            "analytics_dashboard_layouts",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("role", sa.String(32), nullable=False),
            sa.Column("layout_key", sa.String(64), nullable=False, server_default="default"),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("widgets_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
            *_common_audit_columns(),
            sa.ForeignKeyConstraint(["society_id"], ["societies.id"], ondelete="RESTRICT"),
            sa.UniqueConstraint(
                "society_id", "role", "layout_key", name="uq_analytics_dashboard_layouts_society_role_key"
            ),
        )
    if "analytics_daily_facts" not in tables:
        op.create_table(
            "analytics_daily_facts",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("grain_date", sa.Date(), nullable=False),
            sa.Column("building_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("wing_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("metric_key", sa.String(128), nullable=False),
            sa.Column("metric_value", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("dimensions_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["society_id"], ["societies.id"], ondelete="RESTRICT"),
            sa.UniqueConstraint(
                "society_id",
                "grain_date",
                "metric_key",
                "building_id",
                "wing_id",
                name="uq_analytics_daily_facts_grain",
            ),
        )
    if "analytics_monthly_facts" not in tables:
        op.create_table(
            "analytics_monthly_facts",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("year", sa.Integer(), nullable=False),
            sa.Column("month", sa.Integer(), nullable=False),
            sa.Column("building_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("wing_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("metric_key", sa.String(128), nullable=False),
            sa.Column("metric_value", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("dimensions_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["society_id"], ["societies.id"], ondelete="RESTRICT"),
            sa.UniqueConstraint(
                "society_id",
                "year",
                "month",
                "metric_key",
                "building_id",
                "wing_id",
                name="uq_analytics_monthly_facts_grain",
            ),
        )
    if "analytics_kpi_snapshots" not in tables:
        op.create_table(
            "analytics_kpi_snapshots",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("kpi_key", sa.String(128), nullable=False),
            sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
            sa.Column("value", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("numerator", sa.BigInteger(), nullable=True),
            sa.Column("denominator", sa.BigInteger(), nullable=True),
            sa.Column("building_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("payload_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["society_id"], ["societies.id"], ondelete="RESTRICT"),
        )
    if "analytics_export_jobs" not in tables:
        op.create_table(
            "analytics_export_jobs",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("report_key", sa.String(128), nullable=False),
            sa.Column("format", sa.String(16), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
            sa.Column("filters_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("file_url", sa.String(1000), nullable=True),
            sa.Column("file_name", sa.String(255), nullable=True),
            sa.Column("content_text", sa.Text(), nullable=True),
            sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("byte_size", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("requested_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            *_common_audit_columns(),
            sa.ForeignKeyConstraint(["society_id"], ["societies.id"], ondelete="RESTRICT"),
        )
    if "analytics_export_downloads" not in tables:
        op.create_table(
            "analytics_export_downloads",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("export_job_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("ip_address", sa.String(64), nullable=True),
            sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["society_id"], ["societies.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["export_job_id"], ["analytics_export_jobs.id"], ondelete="CASCADE"),
        )
    if "report_schedules" not in tables:
        op.create_table(
            "report_schedules",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("report_key", sa.String(128), nullable=False),
            sa.Column("format", sa.String(16), nullable=False, server_default="csv"),
            sa.Column("frequency", sa.String(32), nullable=False),
            sa.Column("cron_expression", sa.String(128), nullable=True),
            sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
            sa.Column("filters_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("recipient_user_ids_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("recipient_roles_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
            *_common_audit_columns(),
            sa.ForeignKeyConstraint(["society_id"], ["societies.id"], ondelete="RESTRICT"),
        )
    if "report_schedule_runs" not in tables:
        op.create_table(
            "report_schedule_runs",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("schedule_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("export_job_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
            sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["society_id"], ["societies.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["schedule_id"], ["report_schedules.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["export_job_id"], ["analytics_export_jobs.id"], ondelete="SET NULL"),
        )
    if "analytics_user_preferences" not in tables:
        op.create_table(
            "analytics_user_preferences",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("favorite_report_keys_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("default_filters_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("saved_filters_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["society_id"], ["societies.id"], ondelete="RESTRICT"),
            sa.UniqueConstraint("society_id", "user_id", name="uq_analytics_user_prefs_society_user"),
        )
    if "analytics_access_logs" not in tables:
        op.create_table(
            "analytics_access_logs",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("action", sa.String(64), nullable=False),
            sa.Column("resource_type", sa.String(64), nullable=False),
            sa.Column("resource_key", sa.String(128), nullable=True),
            sa.Column("details_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["society_id"], ["societies.id"], ondelete="RESTRICT"),
        )

    inspector = sa.inspect(conn)
    indexes = [
        ("analytics_report_definitions", "ix_analytics_report_defs_society_id", ["society_id"]),
        ("analytics_kpi_definitions", "ix_analytics_kpi_defs_society_id", ["society_id"]),
        ("analytics_dashboard_layouts", "ix_analytics_dashboard_layouts_society_id", ["society_id"]),
        ("analytics_daily_facts", "ix_analytics_daily_facts_society_date", ["society_id", "grain_date"]),
        ("analytics_monthly_facts", "ix_analytics_monthly_facts_society", ["society_id", "year", "month"]),
        ("analytics_kpi_snapshots", "ix_analytics_kpi_snapshots_society", ["society_id", "as_of"]),
        ("analytics_export_jobs", "ix_analytics_export_jobs_society_id", ["society_id"]),
        ("report_schedules", "ix_report_schedules_society_id", ["society_id"]),
        ("analytics_access_logs", "ix_analytics_access_logs_society_id", ["society_id"]),
    ]
    for table, name, cols in indexes:
        if table in inspector.get_table_names() and not _has_index(inspector, table, name):
            op.create_index(name, table, cols)


def downgrade() -> None:
    for table in (
        "analytics_access_logs",
        "analytics_user_preferences",
        "report_schedule_runs",
        "report_schedules",
        "analytics_export_downloads",
        "analytics_export_jobs",
        "analytics_kpi_snapshots",
        "analytics_monthly_facts",
        "analytics_daily_facts",
        "analytics_dashboard_layouts",
        "analytics_kpi_definitions",
        "analytics_report_definitions",
    ):
        op.drop_table(table)
