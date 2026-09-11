"""Initial users table — mirrors Node User.model.js fields for PostgreSQL."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_users"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=15), nullable=False),
        sa.Column("password", sa.String(length=255), nullable=False),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("flat_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("dob", sa.DateTime(timezone=True), nullable=True),
        sa.Column("gender", sa.String(length=32), nullable=True),
        sa.Column("blood_group", sa.String(length=5), nullable=True),
        sa.Column("flat_no", sa.String(length=50), nullable=True),
        sa.Column("wing", sa.String(length=50), nullable=True),
        sa.Column("building", sa.String(length=100), nullable=True),
        sa.Column("designation", sa.String(length=100), nullable=True),
        sa.Column("office_contact", sa.String(length=20), nullable=True),
        sa.Column("office_address", sa.Text(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("emergency_name", sa.String(length=120), nullable=True),
        sa.Column("emergency_phone", sa.String(length=20), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("login_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lock_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refresh_token", sa.String(length=128), nullable=True),
        sa.Column("otp", sa.String(length=255), nullable=True),
        sa.Column("otp_expiry", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("phone"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_phone", "users", ["phone"])
    op.create_index("ix_users_role", "users", ["role"])
    op.create_index("ix_users_is_active", "users", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_users_is_active", table_name="users")
    op.drop_index("ix_users_role", table_name="users")
    op.drop_index("ix_users_phone", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
