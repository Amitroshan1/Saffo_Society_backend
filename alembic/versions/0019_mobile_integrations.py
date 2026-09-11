"""Create mobile API and third-party integration tables (Phase 18)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019_mobile_integrations"
down_revision: Union[str, None] = "0018_platform_control_plane"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _ts_cols():
    return [
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

    if "mobile_devices" not in tables:
        op.create_table(
            "mobile_devices",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("device_uid", sa.String(128), nullable=False),
            sa.Column("platform", sa.String(32), nullable=False, server_default="android"),
            sa.Column("app_id", sa.String(64), nullable=False, server_default="resident"),
            sa.Column("app_version", sa.String(32), nullable=True),
            sa.Column("os_version", sa.String(64), nullable=True),
            sa.Column("push_token", sa.String(512), nullable=True),
            sa.Column("push_provider", sa.String(32), nullable=True),
            sa.Column("fingerprint_hash", sa.String(128), nullable=True),
            sa.Column(
                "biometric_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column("status", sa.String(32), nullable=False, server_default="active"),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "metadata_json",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            *_ts_cols(),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["society_id"], ["societies.id"], ondelete="SET NULL"),
            sa.UniqueConstraint("device_uid", name="uq_mobile_devices_device_uid"),
        )
        op.create_index("ix_mobile_devices_user_id", "mobile_devices", ["user_id"])
        op.create_index("ix_mobile_devices_society_id", "mobile_devices", ["society_id"])
        op.create_index("ix_mobile_devices_device_uid", "mobile_devices", ["device_uid"])
        op.create_index("ix_mobile_devices_status", "mobile_devices", ["status"])

    if "mobile_sessions" not in tables:
        op.create_table(
            "mobile_sessions",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("refresh_token_hash", sa.String(128), nullable=False),
            sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("rotated_from_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("status", sa.String(32), nullable=False, server_default="active"),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "metadata_json",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            *_ts_cols(),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["device_id"], ["mobile_devices.id"], ondelete="SET NULL"
            ),
        )
        op.create_index("ix_mobile_sessions_user_id", "mobile_sessions", ["user_id"])
        op.create_index("ix_mobile_sessions_device_id", "mobile_sessions", ["device_id"])
        op.create_index("ix_mobile_sessions_society_id", "mobile_sessions", ["society_id"])
        op.create_index(
            "ix_mobile_sessions_refresh_token_hash",
            "mobile_sessions",
            ["refresh_token_hash"],
        )
        op.create_index("ix_mobile_sessions_family_id", "mobile_sessions", ["family_id"])
        op.create_index("ix_mobile_sessions_status", "mobile_sessions", ["status"])

    if "sync_cursors" not in tables:
        op.create_table(
            "sync_cursors",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("collection", sa.String(64), nullable=False),
            sa.Column("cursor_value", sa.String(128), nullable=False, server_default="0"),
            sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "metadata_json",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            *_ts_cols(),
            sa.UniqueConstraint(
                "user_id",
                "device_id",
                "collection",
                name="uq_sync_cursors_user_device_coll",
            ),
        )
        op.create_index("ix_sync_cursors_user_id", "sync_cursors", ["user_id"])
        op.create_index("ix_sync_cursors_device_id", "sync_cursors", ["device_id"])
        op.create_index("ix_sync_cursors_society_id", "sync_cursors", ["society_id"])

    if "sync_mutation_log" not in tables:
        op.create_table(
            "sync_mutation_log",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("collection", sa.String(64), nullable=False),
            sa.Column("mutation_type", sa.String(32), nullable=False),
            sa.Column("client_mutation_id", sa.String(128), nullable=False),
            sa.Column("entity_id", sa.String(64), nullable=True),
            sa.Column(
                "payload_json",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("status", sa.String(32), nullable=False, server_default="accepted"),
            sa.Column("conflict_json", postgresql.JSONB(), nullable=True),
            sa.Column("server_result_json", postgresql.JSONB(), nullable=True),
            *_ts_cols(),
        )
        op.create_index("ix_sync_mutation_log_user_id", "sync_mutation_log", ["user_id"])
        op.create_index("ix_sync_mutation_log_device_id", "sync_mutation_log", ["device_id"])
        op.create_index("ix_sync_mutation_log_society_id", "sync_mutation_log", ["society_id"])
        op.create_index("ix_sync_mutation_log_collection", "sync_mutation_log", ["collection"])
        op.create_index(
            "ix_sync_mutation_log_client_mutation_id",
            "sync_mutation_log",
            ["client_mutation_id"],
        )
        op.create_index("ix_sync_mutation_log_status", "sync_mutation_log", ["status"])

    if "idempotency_keys" not in tables:
        op.create_table(
            "idempotency_keys",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("scope_key", sa.String(256), nullable=False),
            sa.Column("idempotency_key", sa.String(128), nullable=False),
            sa.Column("request_hash", sa.String(128), nullable=False),
            sa.Column("response_json", postgresql.JSONB(), nullable=True),
            sa.Column("status_code", sa.Integer(), nullable=False, server_default="200"),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.UniqueConstraint(
                "scope_key",
                "idempotency_key",
                name="uq_idempotency_scope_key",
            ),
        )
        op.create_index("ix_idempotency_keys_scope_key", "idempotency_keys", ["scope_key"])
        op.create_index("ix_idempotency_keys_expires_at", "idempotency_keys", ["expires_at"])

    if "integration_providers" not in tables:
        op.create_table(
            "integration_providers",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("code", sa.String(64), nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("category", sa.String(64), nullable=False),
            sa.Column("adapter_key", sa.String(64), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="active"),
            sa.Column("health_status", sa.String(32), nullable=False, server_default="unknown"),
            sa.Column("health_detail", sa.Text(), nullable=True),
            sa.Column("last_health_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "config_json",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "scopes_json",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
            sa.Column(
                "is_platform_default",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column(
                "metadata_json",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            *_ts_cols(),
            sa.UniqueConstraint("code", name="uq_integration_providers_code"),
        )
        op.create_index("ix_integration_providers_code", "integration_providers", ["code"])
        op.create_index("ix_integration_providers_category", "integration_providers", ["category"])
        op.create_index("ix_integration_providers_status", "integration_providers", ["status"])

    if "integration_credentials" not in tables:
        op.create_table(
            "integration_credentials",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("provider_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("label", sa.String(128), nullable=False, server_default="default"),
            sa.Column("secret_ref", sa.String(255), nullable=False),
            sa.Column(
                "config_json",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("status", sa.String(32), nullable=False, server_default="active"),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            *_ts_cols(),
            sa.ForeignKeyConstraint(
                ["provider_id"], ["integration_providers.id"], ondelete="CASCADE"
            ),
        )
        op.create_index(
            "ix_integration_credentials_provider_id",
            "integration_credentials",
            ["provider_id"],
        )
        op.create_index(
            "ix_integration_credentials_society_id",
            "integration_credentials",
            ["society_id"],
        )

    if "webhook_subscriptions" not in tables:
        op.create_table(
            "webhook_subscriptions",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("target_url", sa.String(1024), nullable=False),
            sa.Column("secret_hash", sa.String(128), nullable=False),
            sa.Column("secret_hint", sa.String(16), nullable=True),
            sa.Column(
                "events_json",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
            sa.Column("status", sa.String(32), nullable=False, server_default="active"),
            sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="8"),
            sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="10"),
            sa.Column(
                "metadata_json",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
            *_ts_cols(),
        )
        op.create_index(
            "ix_webhook_subscriptions_society_id",
            "webhook_subscriptions",
            ["society_id"],
        )
        op.create_index("ix_webhook_subscriptions_status", "webhook_subscriptions", ["status"])

    if "webhook_deliveries" not in tables:
        op.create_table(
            "webhook_deliveries",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("subscription_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("direction", sa.String(16), nullable=False, server_default="outbound"),
            sa.Column("event_name", sa.String(128), nullable=False),
            sa.Column("event_id", sa.String(128), nullable=False),
            sa.Column(
                "payload_json",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("http_status", sa.Integer(), nullable=True),
            sa.Column("response_body", sa.Text(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
            *_ts_cols(),
            sa.ForeignKeyConstraint(
                ["subscription_id"],
                ["webhook_subscriptions.id"],
                ondelete="SET NULL",
            ),
        )
        op.create_index(
            "ix_webhook_deliveries_subscription_id",
            "webhook_deliveries",
            ["subscription_id"],
        )
        op.create_index(
            "ix_webhook_deliveries_society_id",
            "webhook_deliveries",
            ["society_id"],
        )
        op.create_index(
            "ix_webhook_deliveries_event_name",
            "webhook_deliveries",
            ["event_name"],
        )
        op.create_index("ix_webhook_deliveries_event_id", "webhook_deliveries", ["event_id"])
        op.create_index("ix_webhook_deliveries_status", "webhook_deliveries", ["status"])

    if "webhook_dlq" not in tables:
        op.create_table(
            "webhook_dlq",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("delivery_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("subscription_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("event_name", sa.String(128), nullable=False),
            sa.Column(
                "payload_json",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="open"),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
        )
        op.create_index("ix_webhook_dlq_delivery_id", "webhook_dlq", ["delivery_id"])
        op.create_index("ix_webhook_dlq_status", "webhook_dlq", ["status"])

    if "payment_provider_intents" not in tables:
        op.create_table(
            "payment_provider_intents",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("bill_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("provider_code", sa.String(32), nullable=False),
            sa.Column("external_id", sa.String(128), nullable=False),
            sa.Column("amount_minor", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
            sa.Column("status", sa.String(32), nullable=False, server_default="created"),
            sa.Column("checkout_url", sa.String(1024), nullable=True),
            sa.Column("client_secret", sa.String(512), nullable=True),
            sa.Column(
                "provider_payload_json",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("idempotency_key", sa.String(128), nullable=True),
            sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
            *_ts_cols(),
        )
        op.create_index(
            "ix_payment_provider_intents_society_id",
            "payment_provider_intents",
            ["society_id"],
        )
        op.create_index(
            "ix_payment_provider_intents_user_id",
            "payment_provider_intents",
            ["user_id"],
        )
        op.create_index(
            "ix_payment_provider_intents_bill_id",
            "payment_provider_intents",
            ["bill_id"],
        )
        op.create_index(
            "ix_payment_provider_intents_payment_id",
            "payment_provider_intents",
            ["payment_id"],
        )
        op.create_index(
            "ix_payment_provider_intents_provider_code",
            "payment_provider_intents",
            ["provider_code"],
        )
        op.create_index(
            "ix_payment_provider_intents_external_id",
            "payment_provider_intents",
            ["external_id"],
        )
        op.create_index(
            "ix_payment_provider_intents_status",
            "payment_provider_intents",
            ["status"],
        )
        op.create_index(
            "ix_payment_provider_intents_idempotency_key",
            "payment_provider_intents",
            ["idempotency_key"],
        )

    if "identity_links" not in tables:
        op.create_table(
            "identity_links",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("provider", sa.String(32), nullable=False),
            sa.Column("subject", sa.String(255), nullable=False),
            sa.Column("email", sa.String(255), nullable=True),
            sa.Column(
                "profile_json",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("status", sa.String(32), nullable=False, server_default="active"),
            sa.Column(
                "linked_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column("unlinked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("provider", "subject", name="uq_identity_provider_subject"),
        )
        op.create_index("ix_identity_links_user_id", "identity_links", ["user_id"])
        op.create_index("ix_identity_links_provider", "identity_links", ["provider"])

    if "api_clients" not in tables:
        op.create_table(
            "api_clients",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("client_code", sa.String(64), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column(
                "scopes_json",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
            sa.Column("status", sa.String(32), nullable=False, server_default="active"),
            sa.Column("rate_limit_rpm", sa.Integer(), nullable=False, server_default="120"),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
            *_ts_cols(),
            sa.UniqueConstraint("client_code", name="uq_api_clients_client_code"),
        )
        op.create_index("ix_api_clients_society_id", "api_clients", ["society_id"])
        op.create_index("ix_api_clients_client_code", "api_clients", ["client_code"])
        op.create_index("ix_api_clients_status", "api_clients", ["status"])

    if "api_keys" not in tables:
        op.create_table(
            "api_keys",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("name", sa.String(128), nullable=False, server_default="default"),
            sa.Column("key_prefix", sa.String(16), nullable=False),
            sa.Column("key_hash", sa.String(128), nullable=False),
            sa.Column(
                "scopes_json",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
            sa.Column("status", sa.String(32), nullable=False, server_default="active"),
            sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["client_id"], ["api_clients.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("key_hash", name="uq_api_keys_key_hash"),
        )
        op.create_index("ix_api_keys_client_id", "api_keys", ["client_id"])
        op.create_index("ix_api_keys_key_prefix", "api_keys", ["key_prefix"])
        op.create_index("ix_api_keys_status", "api_keys", ["status"])

    if "storage_objects" not in tables:
        op.create_table(
            "storage_objects",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("module", sa.String(64), nullable=False, server_default="general"),
            sa.Column("provider_code", sa.String(32), nullable=False, server_default="minio"),
            sa.Column("bucket", sa.String(128), nullable=False),
            sa.Column("object_key", sa.String(512), nullable=False),
            sa.Column("content_type", sa.String(128), nullable=True),
            sa.Column("size_bytes", sa.BigInteger(), nullable=True),
            sa.Column("checksum", sa.String(128), nullable=True),
            sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
            sa.Column("cdn_url", sa.String(1024), nullable=True),
            sa.Column(
                "metadata_json",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            *_ts_cols(),
        )
        op.create_index("ix_storage_objects_society_id", "storage_objects", ["society_id"])
        op.create_index("ix_storage_objects_user_id", "storage_objects", ["user_id"])
        op.create_index("ix_storage_objects_module", "storage_objects", ["module"])
        op.create_index("ix_storage_objects_object_key", "storage_objects", ["object_key"])
        op.create_index("ix_storage_objects_status", "storage_objects", ["status"])

    if "mobile_crash_reports" not in tables:
        op.create_table(
            "mobile_crash_reports",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("app_id", sa.String(64), nullable=True),
            sa.Column("app_version", sa.String(32), nullable=True),
            sa.Column("platform", sa.String(32), nullable=True),
            sa.Column("message", sa.String(512), nullable=False),
            sa.Column("stack_hash", sa.String(128), nullable=True),
            sa.Column(
                "breadcrumbs_json",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
        )
        op.create_index(
            "ix_mobile_crash_reports_society_id",
            "mobile_crash_reports",
            ["society_id"],
        )
        op.create_index(
            "ix_mobile_crash_reports_stack_hash",
            "mobile_crash_reports",
            ["stack_hash"],
        )


def downgrade() -> None:
    for table in (
        "mobile_crash_reports",
        "storage_objects",
        "api_keys",
        "api_clients",
        "identity_links",
        "payment_provider_intents",
        "webhook_dlq",
        "webhook_deliveries",
        "webhook_subscriptions",
        "integration_credentials",
        "integration_providers",
        "idempotency_keys",
        "sync_mutation_log",
        "sync_cursors",
        "mobile_sessions",
        "mobile_devices",
    ):
        op.drop_table(table)
