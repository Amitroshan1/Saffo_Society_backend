"""Create document management tables (Phase 12)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013_document_management"
down_revision: Union[str, None] = "0012_notices_announcements"
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

    if "document_categories" not in inspector.get_table_names():
        op.create_table(
            "document_categories",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("code", sa.String(length=32), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("description", sa.String(length=500), nullable=True),
            sa.Column("icon", sa.String(length=64), nullable=True),
            *_common_audit_columns(),
            sa.ForeignKeyConstraint(
                ["society_id"],
                ["societies.id"],
                ondelete="RESTRICT",
                name="fk_document_categories_society_id",
            ),
            sa.ForeignKeyConstraint(
                ["parent_id"],
                ["document_categories.id"],
                ondelete="SET NULL",
                name="fk_document_categories_parent_id",
            ),
            sa.UniqueConstraint(
                "society_id", "code", name="uq_document_categories_society_code"
            ),
        )

    inspector = sa.inspect(conn)
    _create_indexes(
        inspector,
        "document_categories",
        (
            ("ix_document_categories_society_id", ["society_id"]),
            ("ix_document_categories_parent_id", ["parent_id"]),
            ("ix_document_categories_is_active", ["is_active"]),
        ),
    )

    inspector = sa.inspect(conn)
    if "documents" not in inspector.get_table_names():
        op.create_table(
            "documents",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("title", sa.String(length=300), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("file_name", sa.String(length=255), nullable=False),
            sa.Column("file_url", sa.String(length=500), nullable=False),
            sa.Column("file_size_bytes", sa.Integer(), nullable=True),
            sa.Column("mime_type", sa.String(length=100), nullable=True),
            sa.Column("document_number", sa.String(length=32), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"),
            sa.Column("scope", sa.String(length=32), nullable=False, server_default="society"),
            sa.Column(
                "tags",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
            sa.Column("folder_path", sa.String(length=500), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column(
                "is_favorite_default", sa.Boolean(), nullable=False, server_default=sa.text("false")
            ),
            sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("published_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("download_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
            *_common_audit_columns(),
            sa.ForeignKeyConstraint(
                ["society_id"], ["societies.id"], ondelete="RESTRICT", name="fk_documents_society_id"
            ),
            sa.ForeignKeyConstraint(
                ["category_id"],
                ["document_categories.id"],
                ondelete="SET NULL",
                name="fk_documents_category_id",
            ),
            sa.ForeignKeyConstraint(
                ["uploaded_by"], ["users.id"], ondelete="RESTRICT", name="fk_documents_uploaded_by"
            ),
            sa.ForeignKeyConstraint(
                ["published_by"], ["users.id"], ondelete="SET NULL", name="fk_documents_published_by"
            ),
            sa.UniqueConstraint(
                "society_id", "document_number", name="uq_documents_society_number"
            ),
        )

    inspector = sa.inspect(conn)
    _create_indexes(
        inspector,
        "documents",
        (
            ("ix_documents_society_id", ["society_id"]),
            ("ix_documents_status", ["status"]),
            ("ix_documents_category_id", ["category_id"]),
            ("ix_documents_scope", ["scope"]),
            ("ix_documents_document_number", ["document_number"]),
            ("ix_documents_is_pinned", ["is_pinned"]),
            ("ix_documents_expires_at", ["expires_at"]),
            ("ix_documents_society_status", ["society_id", "status"]),
            ("ix_documents_society_scope", ["society_id", "scope"]),
            ("ix_documents_is_active", ["is_active"]),
        ),
    )

    inspector = sa.inspect(conn)
    if "document_versions" not in inspector.get_table_names():
        op.create_table(
            "document_versions",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("version_number", sa.Integer(), nullable=False),
            sa.Column("file_name", sa.String(length=255), nullable=False),
            sa.Column("file_url", sa.String(length=500), nullable=False),
            sa.Column("file_size_bytes", sa.Integer(), nullable=True),
            sa.Column("mime_type", sa.String(length=100), nullable=True),
            sa.Column("change_notes", sa.Text(), nullable=True),
            sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("is_latest", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
            ),
            sa.ForeignKeyConstraint(
                ["document_id"],
                ["documents.id"],
                ondelete="CASCADE",
                name="fk_document_versions_document_id",
            ),
            sa.ForeignKeyConstraint(
                ["uploaded_by"], ["users.id"], ondelete="RESTRICT", name="fk_document_versions_uploaded_by"
            ),
            sa.UniqueConstraint(
                "document_id", "version_number", name="uq_document_versions_doc_version"
            ),
        )

    inspector = sa.inspect(conn)
    _create_indexes(
        inspector,
        "document_versions",
        (
            ("ix_document_versions_document_id", ["document_id"]),
        ),
    )

    inspector = sa.inspect(conn)
    if "document_permissions" not in inspector.get_table_names():
        op.create_table(
            "document_permissions",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("permission_type", sa.String(length=32), nullable=False),
            sa.Column("role_name", sa.String(length=32), nullable=True),
            sa.Column("building_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("wing_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("flat_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("resident_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column(
                "can_download", sa.Boolean(), nullable=False, server_default=sa.text("true")
            ),
            *_common_audit_columns(),
            sa.ForeignKeyConstraint(
                ["document_id"],
                ["documents.id"],
                ondelete="CASCADE",
                name="fk_document_permissions_document_id",
            ),
            sa.ForeignKeyConstraint(
                ["society_id"],
                ["societies.id"],
                ondelete="RESTRICT",
                name="fk_document_permissions_society_id",
            ),
            sa.ForeignKeyConstraint(
                ["building_id"],
                ["buildings.id"],
                ondelete="RESTRICT",
                name="fk_document_permissions_building_id",
            ),
            sa.ForeignKeyConstraint(
                ["wing_id"], ["wings.id"], ondelete="RESTRICT", name="fk_document_permissions_wing_id"
            ),
            sa.ForeignKeyConstraint(
                ["flat_id"], ["flats.id"], ondelete="RESTRICT", name="fk_document_permissions_flat_id"
            ),
            sa.ForeignKeyConstraint(
                ["resident_id"],
                ["residents.id"],
                ondelete="RESTRICT",
                name="fk_document_permissions_resident_id",
            ),
        )

    inspector = sa.inspect(conn)
    _create_indexes(
        inspector,
        "document_permissions",
        (
            ("ix_document_permissions_document_id", ["document_id"]),
            ("ix_document_permissions_society_id", ["society_id"]),
            ("ix_document_permissions_permission_type", ["permission_type"]),
            ("ix_document_permissions_building_id", ["building_id"]),
            ("ix_document_permissions_wing_id", ["wing_id"]),
            ("ix_document_permissions_flat_id", ["flat_id"]),
            ("ix_document_permissions_resident_id", ["resident_id"]),
        ),
    )

    inspector = sa.inspect(conn)
    if "document_download_logs" not in inspector.get_table_names():
        op.create_table(
            "document_download_logs",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("resident_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("downloaded_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("ip_hash", sa.String(length=128), nullable=True),
            sa.Column("user_agent", sa.String(length=255), nullable=True),
            sa.Column("version_number", sa.Integer(), nullable=True),
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
                ["document_id"],
                ["documents.id"],
                ondelete="CASCADE",
                name="fk_document_download_logs_document_id",
            ),
            sa.ForeignKeyConstraint(
                ["society_id"],
                ["societies.id"],
                ondelete="RESTRICT",
                name="fk_document_download_logs_society_id",
            ),
            sa.ForeignKeyConstraint(
                ["user_id"], ["users.id"], ondelete="RESTRICT", name="fk_document_download_logs_user_id"
            ),
            sa.ForeignKeyConstraint(
                ["resident_id"],
                ["residents.id"],
                ondelete="SET NULL",
                name="fk_document_download_logs_resident_id",
            ),
        )

    inspector = sa.inspect(conn)
    _create_indexes(
        inspector,
        "document_download_logs",
        (
            ("ix_document_download_logs_document_id", ["document_id"]),
            ("ix_document_download_logs_society_id", ["society_id"]),
            ("ix_document_download_logs_user_id", ["user_id"]),
            ("ix_document_download_logs_downloaded_at", ["downloaded_at"]),
        ),
    )


def downgrade() -> None:
    op.drop_table("document_download_logs")
    op.drop_table("document_permissions")
    op.drop_table("document_versions")
    op.drop_table("documents")
    op.drop_table("document_categories")
