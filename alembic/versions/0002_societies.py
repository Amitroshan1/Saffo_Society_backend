"""Add societies table and users.society_id."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_societies"
down_revision: Union[str, None] = "0001_initial_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "societies" not in tables:
        op.create_table(
            "societies",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("display_name", sa.String(length=200), nullable=True),
            sa.Column("short_name", sa.String(length=50), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("code", sa.String(length=32), nullable=False),
            sa.Column("registration_no", sa.String(length=64), nullable=True),
            sa.Column("registration_date", sa.Date(), nullable=True),
            sa.Column("gstin", sa.String(length=15), nullable=True),
            sa.Column("pan", sa.String(length=10), nullable=True),
            sa.Column("email", sa.String(length=255), nullable=True),
            sa.Column("phone", sa.String(length=20), nullable=True),
            sa.Column("contact_person", sa.String(length=120), nullable=True),
            sa.Column("contact_designation", sa.String(length=100), nullable=True),
            sa.Column("contact_email", sa.String(length=255), nullable=True),
            sa.Column("contact_phone", sa.String(length=20), nullable=True),
            sa.Column("address_line1", sa.String(length=255), nullable=False),
            sa.Column("address_line2", sa.String(length=255), nullable=True),
            sa.Column("city", sa.String(length=100), nullable=False),
            sa.Column("state", sa.String(length=100), nullable=False),
            sa.Column("pincode", sa.String(length=10), nullable=False),
            sa.Column("country", sa.String(length=2), nullable=False, server_default="IN"),
            sa.Column("website", sa.String(length=255), nullable=True),
            sa.Column("logo_url", sa.String(length=500), nullable=True),
            sa.Column("cover_image", sa.String(length=500), nullable=True),
            sa.Column("latitude", sa.Float(), nullable=True),
            sa.Column("longitude", sa.Float(), nullable=True),
            sa.Column("established_year", sa.Integer(), nullable=True),
            sa.Column(
                "settings",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text(
                    "'{\"timezone\":\"Asia/Kolkata\",\"currency\":\"INR\",\"language\":\"en\","
                    "\"date_format\":\"DD/MM/YYYY\",\"theme\":\"system\","
                    "\"visitorApproval\":\"resident\",\"financialYearStart\":4}'::jsonb"
                ),
            ),
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
            sa.UniqueConstraint("code"),
        )
        op.create_index("ix_societies_code", "societies", ["code"])
        op.create_index("ix_societies_is_active", "societies", ["is_active"])
        op.create_index("ix_societies_city", "societies", ["city"])

    user_cols = {c["name"] for c in inspector.get_columns("users")}
    if "society_id" not in user_cols:
        op.add_column(
            "users",
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
        op.create_index("ix_users_society_id", "users", ["society_id"])
        op.create_foreign_key(
            "fk_users_society_id",
            "users",
            "societies",
            ["society_id"],
            ["id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    user_cols = {c["name"] for c in inspector.get_columns("users")}
    if "society_id" in user_cols:
        op.drop_constraint("fk_users_society_id", "users", type_="foreignkey")
        op.drop_index("ix_users_society_id", table_name="users")
        op.drop_column("users", "society_id")
    if "societies" in inspector.get_table_names():
        op.drop_index("ix_societies_city", table_name="societies")
        op.drop_index("ix_societies_is_active", table_name="societies")
        op.drop_index("ix_societies_code", table_name="societies")
        op.drop_table("societies")
