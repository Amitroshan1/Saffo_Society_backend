"""Add gate geofence coordinates and radius (attendance geo enforcement)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020_gate_geofence"
down_revision: Union[str, None] = "0019_mobile_integrations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())
    if "gates" not in tables:
        return

    columns = {c["name"] for c in inspector.get_columns("gates")}
    if "latitude" not in columns:
        op.add_column("gates", sa.Column("latitude", sa.Float(), nullable=True))
    if "longitude" not in columns:
        op.add_column("gates", sa.Column("longitude", sa.Float(), nullable=True))
    if "geofence_radius_meters" not in columns:
        op.add_column(
            "gates",
            sa.Column(
                "geofence_radius_meters",
                sa.Integer(),
                nullable=False,
                server_default="120",
            ),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())
    if "gates" not in tables:
        return

    columns = {c["name"] for c in inspector.get_columns("gates")}
    if "geofence_radius_meters" in columns:
        op.drop_column("gates", "geofence_radius_meters")
    if "longitude" in columns:
        op.drop_column("gates", "longitude")
    if "latitude" in columns:
        op.drop_column("gates", "latitude")
