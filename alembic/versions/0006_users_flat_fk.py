"""Add users.flat_id foreign key to flats."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_users_flat_fk"
down_revision: Union[str, None] = "0005_flats"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_fk(inspector: sa.Inspector, table: str, fk_name: str) -> bool:
    return any(fk["name"] == fk_name for fk in inspector.get_foreign_keys(table))


def _has_index(inspector: sa.Inspector, table: str, index_name: str) -> bool:
    return any(i["name"] == index_name for i in inspector.get_indexes(table))


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "users" not in inspector.get_table_names():
        return

    if not _has_fk(inspector, "users", "fk_users_flat_id"):
        op.create_foreign_key(
            "fk_users_flat_id",
            "users",
            "flats",
            ["flat_id"],
            ["id"],
            ondelete="SET NULL",
        )

    if not _has_index(inspector, "users", "ix_users_flat_id"):
        op.create_index("ix_users_flat_id", "users", ["flat_id"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "users" not in inspector.get_table_names():
        return

    if _has_index(inspector, "users", "ix_users_flat_id"):
        op.drop_index("ix_users_flat_id", table_name="users")
    if _has_fk(inspector, "users", "fk_users_flat_id"):
        op.drop_constraint("fk_users_flat_id", "users", type_="foreignkey")
