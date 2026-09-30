"""guard panel tables

Revision ID: a7c3e91f4b20
Revises: dd6e2cf8b483
Create Date: 2026-09-28 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7c3e91f4b20'
down_revision: Union[str, Sequence[str], None] = 'dd6e2cf8b483'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TZ = sa.DateTime(timezone=True)

INDEXES = {
    'staff': ['id', 'society_id', 'flat_no', 'phone'],
    'staff_logs': ['id', 'society_id', 'staff_id', 'attendance_date', 'recorded_by'],
    'shifts': ['id', 'society_id', 'guard_user_id', 'duty_date', 'status'],
    'punch_logs': ['id', 'shift_id', 'society_id', 'guard_user_id', 'punched_at'],
    'parking': ['id', 'society_id', 'slot_number', 'building', 'slot_type'],
    'parking_logs': [
        'id', 'society_id', 'parking_id', 'parking_type', 'entry_time', 'exit_time', 'recorded_by',
    ],
    'guard_move_out': ['id', 'society_id', 'resident_id', 'flat_no', 'move_out_date', 'allowed_by'],
    'move_out_files': ['id', 'society_id', 'move_out_id', 'uploaded_by'],
    'guard_profiles': ['id', 'society_id', 'user_id'],
    'documents': ['id', 'society_id', 'category', 'published_at', 'uploaded_by'],
    'deliveries': ['id', 'society_id', 'phone', 'flat_no', 'status', 'recorded_by'],
    'cabs': ['id', 'society_id', 'vehicle_number', 'flat_no', 'status', 'recorded_by'],
    'visit_gate_entries': ['id', 'society_id', 'recorded_by'],
    'sos_resolutions': ['id', 'society_id', 'resolved_by'],
}
UNIQUE_INDEXES = {
    'visit_gate_entries': ['visit_id'],
    'sos_resolutions': ['sos_id'],
}


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('staff',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('society_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=150), nullable=False),
    sa.Column('role', sa.String(length=80), nullable=False),
    sa.Column('building_no', sa.String(length=80), nullable=False),
    sa.Column('wing_no', sa.String(length=30), nullable=True),
    sa.Column('flat_no', sa.String(length=50), nullable=False),
    sa.Column('owner_name', sa.String(length=150), nullable=False),
    sa.Column('phone', sa.String(length=20), nullable=True),
    sa.Column('aadhaar', sa.String(length=20), nullable=True),
    sa.Column('staff_type', sa.String(length=20), nullable=False),
    sa.Column('created_at', TZ, nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('staff_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('society_id', sa.Integer(), nullable=False),
    sa.Column('staff_id', sa.Integer(), nullable=False),
    sa.Column('attendance_date', sa.Date(), nullable=False),
    sa.Column('check_in', TZ, nullable=False),
    sa.Column('check_out', TZ, nullable=True),
    sa.Column('recorded_by', sa.Integer(), nullable=False),
    sa.Column('created_at', TZ, nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('society_id', 'staff_id', 'attendance_date', name='uq_staff_logs_one_day')
    )
    op.create_table('shifts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('society_id', sa.Integer(), nullable=False),
    sa.Column('guard_user_id', sa.Integer(), nullable=False),
    sa.Column('staff_name', sa.String(length=150), nullable=False),
    sa.Column('staff_code', sa.String(length=40), nullable=False),
    sa.Column('gate_name', sa.String(length=150), nullable=False),
    sa.Column('gate_code', sa.String(length=30), nullable=False),
    sa.Column('latitude', sa.Float(), nullable=False),
    sa.Column('longitude', sa.Float(), nullable=False),
    sa.Column('radius_meters', sa.Integer(), nullable=False),
    sa.Column('duty_date', sa.Date(), nullable=False),
    sa.Column('shift_type', sa.String(length=30), nullable=False),
    sa.Column('start_time', sa.Time(), nullable=False),
    sa.Column('end_time', sa.Time(), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.Column('created_at', TZ, nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('punch_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('shift_id', sa.Integer(), nullable=False),
    sa.Column('society_id', sa.Integer(), nullable=False),
    sa.Column('guard_user_id', sa.Integer(), nullable=False),
    sa.Column('action', sa.String(length=10), nullable=False),
    sa.Column('latitude', sa.Float(), nullable=False),
    sa.Column('longitude', sa.Float(), nullable=False),
    sa.Column('punched_at', TZ, nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('parking',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('society_id', sa.Integer(), nullable=False),
    sa.Column('slot_number', sa.String(length=40), nullable=False),
    sa.Column('building', sa.String(length=80), nullable=False),
    sa.Column('wing_no', sa.String(length=30), nullable=True),
    sa.Column('slot_type', sa.String(length=20), nullable=False),
    sa.Column('resident_id', sa.Integer(), nullable=True),
    sa.Column('resident_name', sa.String(length=150), nullable=True),
    sa.Column('flat_no', sa.String(length=50), nullable=True),
    sa.Column('vehicle_number', sa.String(length=30), nullable=True),
    sa.Column('vehicle_type', sa.String(length=30), nullable=True),
    sa.Column('created_at', TZ, nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('society_id', 'slot_number', name='uq_parking_society_slot')
    )
    op.create_table('parking_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('society_id', sa.Integer(), nullable=False),
    sa.Column('parking_id', sa.Integer(), nullable=False),
    sa.Column('parking_type', sa.String(length=20), nullable=False),
    sa.Column('resident_id', sa.Integer(), nullable=True),
    sa.Column('resident_name', sa.String(length=150), nullable=True),
    sa.Column('visitor_name', sa.String(length=150), nullable=True),
    sa.Column('visitor_phone', sa.String(length=20), nullable=True),
    sa.Column('building', sa.String(length=80), nullable=True),
    sa.Column('wing_no', sa.String(length=30), nullable=True),
    sa.Column('flat_no', sa.String(length=50), nullable=True),
    sa.Column('vehicle_number', sa.String(length=30), nullable=False),
    sa.Column('vehicle_type', sa.String(length=30), nullable=False),
    sa.Column('entry_time', TZ, nullable=False),
    sa.Column('exit_time', TZ, nullable=True),
    sa.Column('recorded_by', sa.Integer(), nullable=False),
    sa.Column('created_at', TZ, nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        'uq_parking_logs_one_open', 'parking_logs', ['society_id', 'parking_id'],
        unique=True, postgresql_where=sa.text('exit_time IS NULL'),
    )
    op.create_table('guard_move_out',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('society_id', sa.Integer(), nullable=False),
    sa.Column('resident_id', sa.Integer(), nullable=False),
    sa.Column('resident_name', sa.String(length=150), nullable=False),
    sa.Column('flat_no', sa.String(length=50), nullable=False),
    sa.Column('building_no', sa.String(length=80), nullable=False),
    sa.Column('wing_no', sa.String(length=30), nullable=True),
    sa.Column('move_out_date', sa.Date(), nullable=False),
    sa.Column('leave_license', sa.Boolean(), nullable=False),
    sa.Column('tenant_id_proof', sa.Boolean(), nullable=False),
    sa.Column('owner_confirmation', sa.Boolean(), nullable=False),
    sa.Column('dues_clearance', sa.Boolean(), nullable=False),
    sa.Column('allowed_at', TZ, nullable=True),
    sa.Column('allowed_by', sa.Integer(), nullable=True),
    sa.Column('created_at', TZ, nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('move_out_files',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('society_id', sa.Integer(), nullable=False),
    sa.Column('move_out_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('file_path', sa.String(length=500), nullable=False),
    sa.Column('file_name', sa.String(length=255), nullable=False),
    sa.Column('size_bytes', sa.Integer(), nullable=False),
    sa.Column('uploaded_by', sa.Integer(), nullable=False),
    sa.Column('created_at', TZ, nullable=False),
    sa.ForeignKeyConstraint(['move_out_id'], ['guard_move_out.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('guard_profiles',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('society_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=150), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('phone', sa.String(length=20), nullable=True),
    sa.Column('designation', sa.String(length=80), nullable=False),
    sa.Column('staff_code', sa.String(length=40), nullable=False),
    sa.Column('gate_name', sa.String(length=150), nullable=False),
    sa.Column('gate_code', sa.String(length=30), nullable=False),
    sa.Column('photo_path', sa.String(length=500), nullable=True),
    sa.Column('joining_date', sa.Date(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', TZ, nullable=False),
    sa.Column('updated_at', TZ, nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', name='uq_guard_profiles_user'),
    sa.UniqueConstraint('society_id', 'staff_code', name='uq_guard_profiles_staff_code')
    )
    op.create_table('documents',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('society_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('category', sa.String(length=30), nullable=False),
    sa.Column('file_path', sa.String(length=500), nullable=False),
    sa.Column('file_name', sa.String(length=255), nullable=False),
    sa.Column('size_bytes', sa.Integer(), nullable=False),
    sa.Column('published_at', TZ, nullable=False),
    sa.Column('uploaded_by', sa.Integer(), nullable=False),
    sa.Column('created_at', TZ, nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('deliveries',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('society_id', sa.Integer(), nullable=False),
    sa.Column('courier_name', sa.String(length=150), nullable=False),
    sa.Column('phone', sa.String(length=20), nullable=False),
    sa.Column('company', sa.String(length=50), nullable=False),
    sa.Column('tracking_id', sa.String(length=80), nullable=True),
    sa.Column('building_no', sa.String(length=80), nullable=False),
    sa.Column('wing_no', sa.String(length=30), nullable=False),
    sa.Column('flat_no', sa.String(length=50), nullable=False),
    sa.Column('parcel_note', sa.Text(), nullable=True),
    sa.Column('photo_path', sa.String(length=500), nullable=True),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.Column('received_by', sa.String(length=40), nullable=True),
    sa.Column('recorded_by', sa.Integer(), nullable=False),
    sa.Column('entry_time', TZ, nullable=True),
    sa.Column('exit_time', TZ, nullable=True),
    sa.Column('created_at', TZ, nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('cabs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('society_id', sa.Integer(), nullable=False),
    sa.Column('vehicle_number', sa.String(length=20), nullable=False),
    sa.Column('driver_name', sa.String(length=150), nullable=True),
    sa.Column('cab_service', sa.String(length=50), nullable=False),
    sa.Column('building_no', sa.String(length=80), nullable=False),
    sa.Column('wing_no', sa.String(length=30), nullable=False),
    sa.Column('flat_no', sa.String(length=50), nullable=False),
    sa.Column('purpose', sa.String(length=50), nullable=False),
    sa.Column('photo_path', sa.String(length=500), nullable=True),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.Column('recorded_by', sa.Integer(), nullable=False),
    sa.Column('entry_time', TZ, nullable=True),
    sa.Column('exit_time', TZ, nullable=True),
    sa.Column('created_at', TZ, nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('visit_gate_entries',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('visit_id', sa.Integer(), nullable=False),
    sa.Column('society_id', sa.Integer(), nullable=False),
    sa.Column('wing_no', sa.String(length=30), nullable=True),
    sa.Column('person_count', sa.Integer(), nullable=False),
    sa.Column('vehicle_number', sa.String(length=30), nullable=True),
    sa.Column('vehicle_type', sa.String(length=30), nullable=True),
    sa.Column('notify_resident', sa.Boolean(), nullable=False),
    sa.Column('remarks', sa.Text(), nullable=True),
    sa.Column('photo_path', sa.String(length=500), nullable=True),
    sa.Column('recorded_by', sa.Integer(), nullable=False),
    sa.Column('check_in_time', TZ, nullable=True),
    sa.Column('check_out_time', TZ, nullable=True),
    sa.Column('created_at', TZ, nullable=False),
    sa.ForeignKeyConstraint(['recorded_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['society_id'], ['societies.id'], ),
    sa.ForeignKeyConstraint(['visit_id'], ['visits.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('sos_resolutions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('sos_id', sa.Integer(), nullable=False),
    sa.Column('society_id', sa.Integer(), nullable=False),
    sa.Column('resolved_by', sa.Integer(), nullable=False),
    sa.Column('resolved_at', TZ, nullable=False),
    sa.ForeignKeyConstraint(['resolved_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['society_id'], ['societies.id'], ),
    sa.ForeignKeyConstraint(['sos_id'], ['sos_alerts.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    for table, columns in INDEXES.items():
        for column in columns:
            op.create_index(op.f(f'ix_{table}_{column}'), table, [column], unique=False)
    for table, columns in UNIQUE_INDEXES.items():
        for column in columns:
            op.create_index(op.f(f'ix_{table}_{column}'), table, [column], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    for table, columns in UNIQUE_INDEXES.items():
        for column in columns:
            op.drop_index(op.f(f'ix_{table}_{column}'), table_name=table)
    for table, columns in INDEXES.items():
        for column in columns:
            op.drop_index(op.f(f'ix_{table}_{column}'), table_name=table)
    op.drop_index('uq_parking_logs_one_open', table_name='parking_logs', postgresql_where=sa.text('exit_time IS NULL'))

    op.drop_table('sos_resolutions')
    op.drop_table('visit_gate_entries')
    op.drop_table('cabs')
    op.drop_table('deliveries')
    op.drop_table('documents')
    op.drop_table('guard_profiles')
    op.drop_table('move_out_files')
    op.drop_table('guard_move_out')
    op.drop_table('parking_logs')
    op.drop_table('parking')
    op.drop_table('punch_logs')
    op.drop_table('shifts')
    op.drop_table('staff_logs')
    op.drop_table('staff')
