"""Create billing & accounting tables (Phase 10)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_billing_accounting"
down_revision: Union[str, None] = "0010_complaints"
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
    tables = inspector.get_table_names()

    if "charge_heads" not in tables:
        op.create_table(
            "charge_heads",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("code", sa.String(length=32), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("category", sa.String(length=64), nullable=False),
            sa.Column(
                "default_amount_minor", sa.Integer(), nullable=False, server_default="0"
            ),
            sa.Column(
                "is_recurring", sa.Boolean(), nullable=False, server_default=sa.text("false")
            ),
            sa.Column(
                "is_taxable", sa.Boolean(), nullable=False, server_default=sa.text("false")
            ),
            sa.Column("gl_code", sa.String(length=64), nullable=True),
            sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("description", sa.Text(), nullable=True),
            *_common_audit_columns(),
            sa.ForeignKeyConstraint(
                ["society_id"],
                ["societies.id"],
                ondelete="RESTRICT",
                name="fk_charge_heads_society_id",
            ),
        )

    inspector = sa.inspect(conn)
    _create_indexes(
        inspector,
        "charge_heads",
        (
            ("ix_charge_heads_society_id", ["society_id"]),
            ("ix_charge_heads_society_is_active", ["society_id", "is_active"]),
            ("ix_charge_heads_category", ["category"]),
            ("uq_charge_heads_society_code", ["society_id", "code"], True),
        ),
    )

    inspector = sa.inspect(conn)
    if "billing_cycles" not in inspector.get_table_names():
        op.create_table(
            "billing_cycles",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("code", sa.String(length=32), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("frequency", sa.String(length=32), nullable=False),
            sa.Column("day_of_month", sa.Integer(), nullable=True),
            sa.Column("custom_cron", sa.String(length=128), nullable=True),
            sa.Column("period_label_template", sa.String(length=128), nullable=True),
            sa.Column("default_due_days", sa.Integer(), nullable=False, server_default="10"),
            sa.Column(
                "auto_publish", sa.Boolean(), nullable=False, server_default=sa.text("false")
            ),
            sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
            *_common_audit_columns(),
            sa.ForeignKeyConstraint(
                ["society_id"],
                ["societies.id"],
                ondelete="RESTRICT",
                name="fk_billing_cycles_society_id",
            ),
        )

    inspector = sa.inspect(conn)
    _create_indexes(
        inspector,
        "billing_cycles",
        (
            ("ix_billing_cycles_society_id", ["society_id"]),
            ("ix_billing_cycles_frequency", ["frequency"]),
            ("ix_billing_cycles_next_run_at", ["next_run_at"]),
            ("uq_billing_cycles_society_code", ["society_id", "code"], True),
        ),
    )

    inspector = sa.inspect(conn)
    if "financial_years" not in inspector.get_table_names():
        op.create_table(
            "financial_years",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("code", sa.String(length=32), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("start_date", sa.Date(), nullable=False),
            sa.Column("end_date", sa.Date(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
            sa.Column("next_bill_seq", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("next_receipt_seq", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("closed_by", postgresql.UUID(as_uuid=True), nullable=True),
            *_common_audit_columns(),
            sa.ForeignKeyConstraint(
                ["society_id"],
                ["societies.id"],
                ondelete="RESTRICT",
                name="fk_financial_years_society_id",
            ),
        )

    inspector = sa.inspect(conn)
    _create_indexes(
        inspector,
        "financial_years",
        (
            ("ix_financial_years_society_id", ["society_id"]),
            ("ix_financial_years_start_end", ["start_date", "end_date"]),
            ("uq_financial_years_society_code", ["society_id", "code"], True),
        ),
    )

    inspector = sa.inspect(conn)
    if "accounting_periods" not in inspector.get_table_names():
        op.create_table(
            "accounting_periods",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("financial_year_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("period_key", sa.String(length=32), nullable=False),
            sa.Column("start_date", sa.Date(), nullable=False),
            sa.Column("end_date", sa.Date(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
            sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("closed_by", postgresql.UUID(as_uuid=True), nullable=True),
            *_common_audit_columns(),
            sa.ForeignKeyConstraint(
                ["society_id"],
                ["societies.id"],
                ondelete="RESTRICT",
                name="fk_accounting_periods_society_id",
            ),
            sa.ForeignKeyConstraint(
                ["financial_year_id"],
                ["financial_years.id"],
                ondelete="RESTRICT",
                name="fk_accounting_periods_financial_year_id",
            ),
        )

    inspector = sa.inspect(conn)
    _create_indexes(
        inspector,
        "accounting_periods",
        (
            ("ix_accounting_periods_society_id", ["society_id"]),
            ("ix_accounting_periods_financial_year_id", ["financial_year_id"]),
            ("uq_accounting_periods_society_period_key", ["society_id", "period_key"], True),
        ),
    )

    inspector = sa.inspect(conn)
    if "late_fee_rules" not in inspector.get_table_names():
        op.create_table(
            "late_fee_rules",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("charge_head_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("billing_cycle_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("grace_days", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("fee_type", sa.String(length=32), nullable=False),
            sa.Column("fixed_amount_minor", sa.Integer(), nullable=True),
            sa.Column("percentage_bps", sa.Integer(), nullable=True),
            sa.Column("daily_amount_minor", sa.Integer(), nullable=True),
            sa.Column("max_penalty_minor", sa.Integer(), nullable=True),
            sa.Column(
                "apply_on", sa.String(length=32), nullable=False, server_default="outstanding"
            ),
            sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("effective_from", sa.Date(), nullable=True),
            sa.Column("effective_to", sa.Date(), nullable=True),
            *_common_audit_columns(),
            sa.ForeignKeyConstraint(
                ["society_id"],
                ["societies.id"],
                ondelete="RESTRICT",
                name="fk_late_fee_rules_society_id",
            ),
            sa.ForeignKeyConstraint(
                ["charge_head_id"],
                ["charge_heads.id"],
                ondelete="SET NULL",
                name="fk_late_fee_rules_charge_head_id",
            ),
            sa.ForeignKeyConstraint(
                ["billing_cycle_id"],
                ["billing_cycles.id"],
                ondelete="SET NULL",
                name="fk_late_fee_rules_billing_cycle_id",
            ),
        )

    inspector = sa.inspect(conn)
    _create_indexes(
        inspector,
        "late_fee_rules",
        (
            ("ix_late_fee_rules_society_id", ["society_id"]),
            ("ix_late_fee_rules_society_is_active", ["society_id", "is_active"]),
            ("ix_late_fee_rules_priority", ["priority"]),
            ("ix_late_fee_rules_charge_head_id", ["charge_head_id"]),
            ("ix_late_fee_rules_billing_cycle_id", ["billing_cycle_id"]),
        ),
    )

    inspector = sa.inspect(conn)
    if "discount_rules" not in inspector.get_table_names():
        op.create_table(
            "discount_rules",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("charge_head_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("resident_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("occupancy_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("discount_type", sa.String(length=32), nullable=False),
            sa.Column("fixed_amount_minor", sa.Integer(), nullable=True),
            sa.Column("percentage_bps", sa.Integer(), nullable=True),
            sa.Column("scope", sa.String(length=32), nullable=False, server_default="society"),
            sa.Column("one_time", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("max_uses", sa.Integer(), nullable=True),
            sa.Column("uses_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("stackable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("effective_from", sa.Date(), nullable=True),
            sa.Column("effective_to", sa.Date(), nullable=True),
            *_common_audit_columns(),
            sa.ForeignKeyConstraint(
                ["society_id"],
                ["societies.id"],
                ondelete="RESTRICT",
                name="fk_discount_rules_society_id",
            ),
            sa.ForeignKeyConstraint(
                ["charge_head_id"],
                ["charge_heads.id"],
                ondelete="SET NULL",
                name="fk_discount_rules_charge_head_id",
            ),
            sa.ForeignKeyConstraint(
                ["resident_id"],
                ["residents.id"],
                ondelete="SET NULL",
                name="fk_discount_rules_resident_id",
            ),
            sa.ForeignKeyConstraint(
                ["occupancy_id"],
                ["occupancies.id"],
                ondelete="SET NULL",
                name="fk_discount_rules_occupancy_id",
            ),
        )

    inspector = sa.inspect(conn)
    _create_indexes(
        inspector,
        "discount_rules",
        (
            ("ix_discount_rules_society_id", ["society_id"]),
            ("ix_discount_rules_society_is_active", ["society_id", "is_active"]),
            ("ix_discount_rules_resident_id", ["resident_id"]),
            ("ix_discount_rules_effective", ["effective_from", "effective_to"]),
            ("ix_discount_rules_charge_head_id", ["charge_head_id"]),
            ("ix_discount_rules_occupancy_id", ["occupancy_id"]),
        ),
    )

    inspector = sa.inspect(conn)
    if "maintenance_bills" not in inspector.get_table_names():
        op.create_table(
            "maintenance_bills",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("building_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("wing_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("flat_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("occupancy_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("resident_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("billing_cycle_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("financial_year_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("accounting_period_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("bill_number", sa.String(length=64), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
            sa.Column("bill_date", sa.Date(), nullable=False),
            sa.Column("period_from", sa.Date(), nullable=False),
            sa.Column("period_to", sa.Date(), nullable=False),
            sa.Column("due_date", sa.Date(), nullable=False),
            sa.Column("gross_minor", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("discount_minor", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("penalty_minor", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("tax_minor", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("net_minor", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("paid_minor", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("outstanding_minor", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("currency", sa.String(length=8), nullable=False, server_default="INR"),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("written_off_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("write_off_reason", sa.Text(), nullable=True),
            sa.Column("source", sa.String(length=32), nullable=False, server_default="manual"),
            *_common_audit_columns(),
            sa.ForeignKeyConstraint(
                ["society_id"],
                ["societies.id"],
                ondelete="RESTRICT",
                name="fk_maintenance_bills_society_id",
            ),
            sa.ForeignKeyConstraint(
                ["building_id"],
                ["buildings.id"],
                ondelete="RESTRICT",
                name="fk_maintenance_bills_building_id",
            ),
            sa.ForeignKeyConstraint(
                ["wing_id"], ["wings.id"], ondelete="RESTRICT", name="fk_maintenance_bills_wing_id"
            ),
            sa.ForeignKeyConstraint(
                ["flat_id"], ["flats.id"], ondelete="RESTRICT", name="fk_maintenance_bills_flat_id"
            ),
            sa.ForeignKeyConstraint(
                ["occupancy_id"],
                ["occupancies.id"],
                ondelete="RESTRICT",
                name="fk_maintenance_bills_occupancy_id",
            ),
            sa.ForeignKeyConstraint(
                ["resident_id"],
                ["residents.id"],
                ondelete="RESTRICT",
                name="fk_maintenance_bills_resident_id",
            ),
            sa.ForeignKeyConstraint(
                ["billing_cycle_id"],
                ["billing_cycles.id"],
                ondelete="SET NULL",
                name="fk_maintenance_bills_billing_cycle_id",
            ),
            sa.ForeignKeyConstraint(
                ["financial_year_id"],
                ["financial_years.id"],
                ondelete="RESTRICT",
                name="fk_maintenance_bills_financial_year_id",
            ),
            sa.ForeignKeyConstraint(
                ["accounting_period_id"],
                ["accounting_periods.id"],
                ondelete="SET NULL",
                name="fk_maintenance_bills_accounting_period_id",
            ),
        )

    inspector = sa.inspect(conn)
    _create_indexes(
        inspector,
        "maintenance_bills",
        (
            ("ix_maintenance_bills_society_status", ["society_id", "status"]),
            ("ix_maintenance_bills_society_due_date", ["society_id", "due_date"]),
            ("ix_maintenance_bills_occupancy_id", ["occupancy_id"]),
            ("ix_maintenance_bills_resident_id", ["resident_id"]),
            ("ix_maintenance_bills_flat_id", ["flat_id"]),
            ("uq_maintenance_bills_society_bill_number", ["society_id", "bill_number"], True),
            ("ix_maintenance_bills_financial_year_id", ["financial_year_id"]),
            ("ix_maintenance_bills_created_at", ["created_at"]),
            ("ix_maintenance_bills_society_id", ["society_id"]),
            ("ix_maintenance_bills_billing_cycle_id", ["billing_cycle_id"]),
            ("ix_maintenance_bills_accounting_period_id", ["accounting_period_id"]),
        ),
    )

    inspector = sa.inspect(conn)
    if "bill_line_items" not in inspector.get_table_names():
        op.create_table(
            "bill_line_items",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("bill_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("charge_head_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("line_no", sa.Integer(), nullable=False),
            sa.Column("description", sa.String(length=500), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("unit_amount_minor", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("line_total_minor", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("tax_minor", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("discount_minor", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "is_penalty", sa.Boolean(), nullable=False, server_default=sa.text("false")
            ),
            sa.Column(
                "is_discount", sa.Boolean(), nullable=False, server_default=sa.text("false")
            ),
            *_common_audit_columns(),
            sa.ForeignKeyConstraint(
                ["society_id"],
                ["societies.id"],
                ondelete="RESTRICT",
                name="fk_bill_line_items_society_id",
            ),
            sa.ForeignKeyConstraint(
                ["bill_id"],
                ["maintenance_bills.id"],
                ondelete="CASCADE",
                name="fk_bill_line_items_bill_id",
            ),
            sa.ForeignKeyConstraint(
                ["charge_head_id"],
                ["charge_heads.id"],
                ondelete="RESTRICT",
                name="fk_bill_line_items_charge_head_id",
            ),
        )

    inspector = sa.inspect(conn)
    _create_indexes(
        inspector,
        "bill_line_items",
        (
            ("ix_bill_line_items_society_id", ["society_id"]),
            ("ix_bill_line_items_bill_id", ["bill_id"]),
            ("ix_bill_line_items_charge_head_id", ["charge_head_id"]),
        ),
    )

    inspector = sa.inspect(conn)
    if "payments" not in inspector.get_table_names():
        op.create_table(
            "payments",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("resident_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("occupancy_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("collected_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("collected_by_staff_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("financial_year_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("accounting_period_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("reversed_payment_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("payment_number", sa.String(length=64), nullable=False),
            sa.Column("amount_minor", sa.Integer(), nullable=False),
            sa.Column("unallocated_minor", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("currency", sa.String(length=8), nullable=False, server_default="INR"),
            sa.Column("mode", sa.String(length=32), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("payment_date", sa.DateTime(timezone=True), nullable=False),
            sa.Column("value_date", sa.Date(), nullable=True),
            sa.Column("external_reference", sa.String(length=128), nullable=True),
            sa.Column("cheque_number", sa.String(length=64), nullable=True),
            sa.Column("bank_name", sa.String(length=128), nullable=True),
            sa.Column("upi_vpa", sa.String(length=128), nullable=True),
            sa.Column("gateway_provider", sa.String(length=64), nullable=True),
            sa.Column("gateway_txn_id", sa.String(length=128), nullable=True),
            sa.Column("idempotency_key", sa.String(length=128), nullable=True),
            sa.Column("payer_name", sa.String(length=200), nullable=True),
            *_common_audit_columns(),
            sa.ForeignKeyConstraint(
                ["society_id"],
                ["societies.id"],
                ondelete="RESTRICT",
                name="fk_payments_society_id",
            ),
            sa.ForeignKeyConstraint(
                ["resident_id"],
                ["residents.id"],
                ondelete="RESTRICT",
                name="fk_payments_resident_id",
            ),
            sa.ForeignKeyConstraint(
                ["occupancy_id"],
                ["occupancies.id"],
                ondelete="SET NULL",
                name="fk_payments_occupancy_id",
            ),
            sa.ForeignKeyConstraint(
                ["collected_by_staff_id"],
                ["staff.id"],
                ondelete="SET NULL",
                name="fk_payments_collected_by_staff_id",
            ),
            sa.ForeignKeyConstraint(
                ["financial_year_id"],
                ["financial_years.id"],
                ondelete="RESTRICT",
                name="fk_payments_financial_year_id",
            ),
            sa.ForeignKeyConstraint(
                ["accounting_period_id"],
                ["accounting_periods.id"],
                ondelete="SET NULL",
                name="fk_payments_accounting_period_id",
            ),
            sa.ForeignKeyConstraint(
                ["reversed_payment_id"],
                ["payments.id"],
                ondelete="SET NULL",
                name="fk_payments_reversed_payment_id",
            ),
        )

    inspector = sa.inspect(conn)
    _create_indexes(
        inspector,
        "payments",
        (
            ("ix_payments_society_status", ["society_id", "status"]),
            ("ix_payments_society_payment_date", ["society_id", "payment_date"]),
            ("ix_payments_resident_id", ["resident_id"]),
            ("ix_payments_society_id", ["society_id"]),
            ("ix_payments_occupancy_id", ["occupancy_id"]),
            ("ix_payments_financial_year_id", ["financial_year_id"]),
            ("ix_payments_mode", ["mode"]),
            ("ix_payments_payment_number", ["payment_number"]),
        ),
    )
    inspector = sa.inspect(conn)
    if "payments" in inspector.get_table_names() and not _has_index(
        inspector, "payments", "uq_payments_society_idempotency_key"
    ):
        op.execute(
            """
            CREATE UNIQUE INDEX uq_payments_society_idempotency_key
            ON payments (society_id, idempotency_key)
            WHERE idempotency_key IS NOT NULL
            """
        )

    inspector = sa.inspect(conn)
    if "payment_allocations" not in inspector.get_table_names():
        op.create_table(
            "payment_allocations",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("bill_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("allocation_type", sa.String(length=32), nullable=False),
            sa.Column("amount_minor", sa.Integer(), nullable=False),
            sa.Column("allocated_at", sa.DateTime(timezone=True), nullable=False),
            *_common_audit_columns(),
            sa.ForeignKeyConstraint(
                ["society_id"],
                ["societies.id"],
                ondelete="RESTRICT",
                name="fk_payment_allocations_society_id",
            ),
            sa.ForeignKeyConstraint(
                ["payment_id"],
                ["payments.id"],
                ondelete="CASCADE",
                name="fk_payment_allocations_payment_id",
            ),
            sa.ForeignKeyConstraint(
                ["bill_id"],
                ["maintenance_bills.id"],
                ondelete="SET NULL",
                name="fk_payment_allocations_bill_id",
            ),
        )

    inspector = sa.inspect(conn)
    _create_indexes(
        inspector,
        "payment_allocations",
        (
            ("ix_payment_allocations_society_id", ["society_id"]),
            ("ix_payment_allocations_payment_id", ["payment_id"]),
            ("ix_payment_allocations_bill_id", ["bill_id"]),
        ),
    )

    inspector = sa.inspect(conn)
    if "receipts" not in inspector.get_table_names():
        op.create_table(
            "receipts",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("resident_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("financial_year_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("receipt_number", sa.String(length=64), nullable=False),
            sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("issued_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("amount_minor", sa.Integer(), nullable=False),
            sa.Column("currency", sa.String(length=8), nullable=False, server_default="INR"),
            sa.Column("pdf_url", sa.String(length=500), nullable=True),
            sa.Column("is_void", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            *_common_audit_columns(),
            sa.ForeignKeyConstraint(
                ["society_id"],
                ["societies.id"],
                ondelete="RESTRICT",
                name="fk_receipts_society_id",
            ),
            sa.ForeignKeyConstraint(
                ["payment_id"],
                ["payments.id"],
                ondelete="RESTRICT",
                name="fk_receipts_payment_id",
            ),
            sa.ForeignKeyConstraint(
                ["resident_id"],
                ["residents.id"],
                ondelete="RESTRICT",
                name="fk_receipts_resident_id",
            ),
            sa.ForeignKeyConstraint(
                ["financial_year_id"],
                ["financial_years.id"],
                ondelete="RESTRICT",
                name="fk_receipts_financial_year_id",
            ),
            sa.UniqueConstraint("payment_id", name="uq_receipts_payment_id"),
        )

    inspector = sa.inspect(conn)
    _create_indexes(
        inspector,
        "receipts",
        (
            ("uq_receipts_society_receipt_number", ["society_id", "receipt_number"], True),
            ("ix_receipts_payment_id", ["payment_id"]),
            ("ix_receipts_resident_id", ["resident_id"]),
            ("ix_receipts_issued_at", ["issued_at"]),
            ("ix_receipts_society_id", ["society_id"]),
            ("ix_receipts_financial_year_id", ["financial_year_id"]),
        ),
    )


def downgrade() -> None:
    op.drop_table("receipts")
    op.drop_table("payment_allocations")
    op.drop_table("payments")
    op.drop_table("bill_line_items")
    op.drop_table("maintenance_bills")
    op.drop_table("discount_rules")
    op.drop_table("late_fee_rules")
    op.drop_table("accounting_periods")
    op.drop_table("financial_years")
    op.drop_table("billing_cycles")
    op.drop_table("charge_heads")
