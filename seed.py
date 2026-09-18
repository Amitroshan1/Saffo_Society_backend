"""
Seed demo society + users for local development.

Usage (from Backend/):
    python seed.py
"""

from __future__ import annotations

import asyncio
import calendar
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select, update

from Core.security import hash_password
from Database.session import AsyncSessionLocal, init_db
from Models.billing_cycle import BillingCycle
from Models.facility import Facility, FacilityBooking
from Models.building import Building
from Models.parking import ParkingAllocation, ParkingSlot, ParkingZone, ResidentVehicle
from Models.charge_head import ChargeHead
from Models.complaint import Complaint, ComplaintComment
from Models.financial_year import AccountingPeriod, FinancialYear
from Models.flat import Flat
from Models.gate import Gate
from Models.maintenance_bill import BillLineItem, MaintenanceBill
from Models.document import Document, DocumentCategory, DocumentPermission
from Models.notice import Notice, NoticeAttachment, NoticeTarget
from Models.notification import (
    Notification,
    NotificationDelivery,
    NotificationPreference,
    NotificationTemplate,
)
from Models.occupancy import Occupancy
from Models.payment import Payment, PaymentAllocation, Receipt
from Models.resident import Resident
from Models.shift import Shift
from Models.society import DEFAULT_SOCIETY_SETTINGS, Society
from Models.staff import Staff
from Models.user import User
from Models.visit import Visit
from Models.visitor import Visitor
from Models.wing import Wing
from Services.occupancy_helpers import derive_flat_from_occupancies, sync_user_flat_for_resident
from Services.facility_helpers import generate_booking_code, slugify
from Services.parking_helpers import generate_parking_code
from Utils.logger import logger

DEFAULT_PASSWORD = "Admin@123"

DEFAULT_SOCIETY = {
    "name": "Demo Housing Society",
    "display_name": "Demo Society",
    "short_name": "Demo",
    "description": "Default society for local development",
    "code": "DEMO-SOCIETY",
    "address_line1": "100 Demo Road",
    "city": "Pune",
    "state": "Maharashtra",
    "pincode": "411001",
    "country": "IN",
    "contact_person": "Society Admin",
    "contact_designation": "Secretary",
    "contact_email": "admin@society.com",
    "contact_phone": "9000000001",
}

SEED_USERS = [
    {
        "name": "Society Admin",
        "email": "admin@society.com",
        "phone": "9000000001",
        "role": "admin",
        "designation": "Society Administrator",
    },
    {
        "name": "Finance Manager",
        "email": "finance@society.com",
        "phone": "9000000002",
        "role": "finance",
        "designation": "Finance Manager",
    },
    {
        "name": "Demo Resident",
        "email": "resident@society.com",
        "phone": "9000000003",
        "role": "resident",
        "flat_no": "101",
        "wing": "A1",
        "building": "Tower A",
    },
    {
        "name": "Gate Guard",
        "email": "guard@society.com",
        "phone": "9000000004",
        "role": "guard",
        "designation": "Security Guard",
    },
]

SEED_BUILDINGS = [
    {
        "name": "Tower A",
        "display_name": "Tower A",
        "code": "A",
        "building_type": "tower",
        "status": "operational",
        "total_floors": 12,
        "planned_units": 48,
        "occupied_units": 26,
        "vacant_units": 22,
        "total_units": 48,
        "has_lift": True,
        "has_parking": True,
        "emergency_contact_name": "Facility Desk",
        "emergency_contact_phone": "9000000101",
    },
    {
        "name": "Tower B",
        "display_name": "Tower B",
        "code": "B",
        "building_type": "tower",
        "status": "operational",
        "total_floors": 10,
        "planned_units": 40,
        "occupied_units": 18,
        "vacant_units": 22,
        "total_units": 40,
        "has_lift": True,
        "has_parking": True,
        "emergency_contact_name": "Facility Desk",
        "emergency_contact_phone": "9000000101",
    },
]


SEED_WINGS = [
    {
        "building_code": "A",
        "name": "Wing A1",
        "code": "A1",
        "short_code": "A1",
        "wing_type": "residential",
        "sequence": 1,
        "color": "#4F46E5",
        "total_floors": 12,
        "total_flats": 24,
        "capacity": 24,
        "elevator_count": 2,
        "emergency_stair_count": 2,
    },
    {
        "building_code": "A",
        "name": "Wing A2",
        "code": "A2",
        "short_code": "A2",
        "wing_type": "residential",
        "sequence": 2,
        "color": "#7C3AED",
        "total_floors": 12,
        "total_flats": 24,
        "capacity": 24,
        "elevator_count": 2,
        "emergency_stair_count": 2,
    },
    {
        "building_code": "B",
        "name": "Wing B1",
        "code": "B1",
        "short_code": "B1",
        "wing_type": "residential",
        "sequence": 1,
        "color": "#2563EB",
        "total_floors": 10,
        "total_flats": 20,
        "capacity": 20,
        "elevator_count": 2,
        "emergency_stair_count": 2,
    },
]

# 2 flats per floor for floors 1–3 under each demo wing
SEED_FLATS = [
    {"wing_code": "A1", "flat_no": "101", "floor_no": "1", "flat_type": "2bhk", "sequence": 1},
    {"wing_code": "A1", "flat_no": "102", "floor_no": "1", "flat_type": "2bhk", "sequence": 2},
    {"wing_code": "A1", "flat_no": "201", "floor_no": "2", "flat_type": "3bhk", "sequence": 3},
    {"wing_code": "A1", "flat_no": "202", "floor_no": "2", "flat_type": "3bhk", "sequence": 4},
    {"wing_code": "A1", "flat_no": "301", "floor_no": "3", "flat_type": "2bhk", "sequence": 5},
    {"wing_code": "A1", "flat_no": "302", "floor_no": "3", "flat_type": "2bhk", "sequence": 6},
    {"wing_code": "A2", "flat_no": "101", "floor_no": "1", "flat_type": "2bhk", "sequence": 1},
    {"wing_code": "A2", "flat_no": "102", "floor_no": "1", "flat_type": "2bhk", "sequence": 2},
    {"wing_code": "A2", "flat_no": "201", "floor_no": "2", "flat_type": "3bhk", "sequence": 3},
    {"wing_code": "A2", "flat_no": "202", "floor_no": "2", "flat_type": "3bhk", "sequence": 4},
    {"wing_code": "A2", "flat_no": "301", "floor_no": "3", "flat_type": "2bhk", "sequence": 5},
    {"wing_code": "A2", "flat_no": "302", "floor_no": "3", "flat_type": "2bhk", "sequence": 6},
    {"wing_code": "B1", "flat_no": "101", "floor_no": "1", "flat_type": "2bhk", "sequence": 1},
    {"wing_code": "B1", "flat_no": "102", "floor_no": "1", "flat_type": "2bhk", "sequence": 2},
    {"wing_code": "B1", "flat_no": "201", "floor_no": "2", "flat_type": "3bhk", "sequence": 3},
    {"wing_code": "B1", "flat_no": "202", "floor_no": "2", "flat_type": "3bhk", "sequence": 4},
]


async def seed() -> None:
    await init_db()
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Society).where(Society.code == DEFAULT_SOCIETY["code"])
        )
        society = result.scalar_one_or_none()
        if not society:
            now = datetime.now(timezone.utc)
            society = Society(
                **DEFAULT_SOCIETY,
                settings=dict(DEFAULT_SOCIETY_SETTINGS),
                is_active=True,
                version=1,
                last_activity_at=now,
            )
            db.add(society)
            await db.flush()
            logger.info("Created society: %s", society.code)
        else:
            logger.info("Skip existing society: %s", society.code)

        created = 0
        skipped = 0
        for row in SEED_USERS:
            result = await db.execute(select(User).where(User.email == row["email"]))
            existing = result.scalar_one_or_none()
            if existing:
                if existing.society_id is None:
                    existing.society_id = society.id
                if row.get("flat_no"):
                    existing.flat_no = row.get("flat_no")
                if row.get("wing"):
                    existing.wing = row.get("wing")
                if row.get("building"):
                    existing.building = row.get("building")
                logger.info("Skip existing user: %s (%s)", row["email"], row["role"])
                skipped += 1
                continue

            user = User(
                name=row["name"],
                email=row["email"].lower(),
                phone=row["phone"],
                password=hash_password(DEFAULT_PASSWORD),
                password_changed_at=datetime.now(timezone.utc),
                role=row["role"],
                designation=row.get("designation"),
                flat_no=row.get("flat_no"),
                wing=row.get("wing"),
                building=row.get("building"),
                society_id=society.id,
                is_active=True,
                is_verified=True,
            )
            db.add(user)
            created += 1
            logger.info("Created user: %s (%s)", row["email"], row["role"])

        await db.execute(
            update(User)
            .where(User.society_id.is_(None))
            .values(society_id=society.id)
        )
        admin_user = (
            await db.execute(
                select(User).where(
                    User.society_id == society.id,
                    User.role == "admin",
                ).limit(1)
            )
        ).scalar_one_or_none()
        building_by_code: dict[str, Building] = {}
        for row in SEED_BUILDINGS:
            result = await db.execute(
                select(Building).where(
                    Building.society_id == society.id,
                    Building.code == row["code"],
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                building_by_code[row["code"]] = existing
                logger.info("Skip existing building: %s", row["code"])
                continue

            building = Building(
                society_id=society.id,
                name=row["name"],
                display_name=row["display_name"],
                code=row["code"],
                building_type=row["building_type"],
                status=row["status"],
                metadata_json={},
                total_floors=row["total_floors"],
                total_units=row["total_units"],
                planned_units=row["planned_units"],
                occupied_units=row["occupied_units"],
                vacant_units=row["vacant_units"],
                has_lift=row["has_lift"],
                has_parking=row["has_parking"],
                emergency_contact_name=row["emergency_contact_name"],
                emergency_contact_phone=row["emergency_contact_phone"],
                is_active=True,
            )
            db.add(building)
            await db.flush()
            building_by_code[row["code"]] = building
            logger.info("Created building: %s", row["code"])

        for row in SEED_WINGS:
            building = building_by_code.get(row["building_code"])
            if not building:
                result = await db.execute(
                    select(Building).where(
                        Building.society_id == society.id,
                        Building.code == row["building_code"],
                    )
                )
                building = result.scalar_one_or_none()
            if not building:
                logger.info("Skip wing %s — building %s missing", row["code"], row["building_code"])
                continue

            result = await db.execute(
                select(Wing).where(
                    Wing.building_id == building.id,
                    Wing.code == row["code"],
                )
            )
            if result.scalar_one_or_none():
                logger.info("Skip existing wing: %s", row["code"])
                continue

            wing = Wing(
                society_id=society.id,
                building_id=building.id,
                name=row["name"],
                display_name=row["name"],
                code=row["code"],
                short_code=row.get("short_code"),
                wing_type=row.get("wing_type"),
                status="operational",
                metadata_json={},
                sequence=row.get("sequence", 0),
                color=row.get("color"),
                total_floors=row.get("total_floors"),
                total_flats=row.get("total_flats"),
                capacity=row.get("capacity"),
                elevator_count=row.get("elevator_count"),
                emergency_stair_count=row.get("emergency_stair_count"),
                is_active=True,
            )
            db.add(wing)
            await db.flush()
            logger.info("Created wing: %s (building %s)", row["code"], row["building_code"])

        wing_by_code: dict[str, Wing] = {}
        for code in ("A1", "A2", "B1"):
            result = await db.execute(
                select(Wing).where(Wing.society_id == society.id, Wing.code == code)
            )
            wing = result.scalar_one_or_none()
            if wing:
                wing_by_code[code] = wing

        for row in SEED_FLATS:
            wing = wing_by_code.get(row["wing_code"])
            if not wing:
                logger.info("Skip flat %s — wing %s missing", row["flat_no"], row["wing_code"])
                continue

            result = await db.execute(
                select(Flat).where(
                    Flat.wing_id == wing.id,
                    Flat.flat_no == row["flat_no"],
                )
            )
            if result.scalar_one_or_none():
                logger.info("Skip existing flat: %s/%s", row["wing_code"], row["flat_no"])
                continue

            flat = Flat(
                society_id=society.id,
                building_id=wing.building_id,
                wing_id=wing.id,
                flat_no=row["flat_no"],
                floor_no=row["floor_no"],
                flat_type=row.get("flat_type"),
                usage_type="residential",
                status="vacant",
                ownership_type="owned",
                area_sqft=850.0 if row.get("flat_type") == "2bhk" else 1100.0,
                area_type="carpet",
                metadata_json={},
                sequence=row.get("sequence", 0),
                is_active=True,
            )
            db.add(flat)
            logger.info("Created flat: %s (wing %s)", row["flat_no"], row["wing_code"])

        # Best-effort backfill users.flat_id from denormalized strings
        users_result = await db.execute(
            select(User).where(
                User.society_id == society.id,
                User.flat_id.is_(None),
                User.flat_no.isnot(None),
            )
        )
        for user in users_result.scalars().all():
            flat_query = select(Flat).where(
                Flat.society_id == society.id,
                Flat.flat_no == user.flat_no.strip().upper(),
            )
            if user.wing:
                wing_hint = user.wing.strip().upper()
                flat_query = flat_query.join(Wing, Flat.wing_id == Wing.id).where(
                    (Wing.code == wing_hint) | (Wing.short_code == wing_hint)
                )
            if user.building:
                building_hint = user.building.strip()
                flat_query = flat_query.join(Building, Flat.building_id == Building.id).where(
                    (Building.name == building_hint)
                    | (Building.code == building_hint.upper())
                    | (Building.display_name == building_hint)
                )
            match = (await db.execute(flat_query.limit(2))).scalars().all()
            if len(match) == 1:
                user.flat_id = match[0].id
                logger.info("Backfilled flat_id for user %s → flat %s", user.email, match[0].flat_no)

        # Phase 5: demo resident + active occupancy for resident@society.com
        resident_user_result = await db.execute(
            select(User).where(User.email == "resident@society.com", User.society_id == society.id)
        )
        resident_user = resident_user_result.scalar_one_or_none()
        if resident_user:
            existing_resident = (
                await db.execute(
                    select(Resident).where(
                        Resident.society_id == society.id,
                        Resident.user_id == resident_user.id,
                    )
                )
            ).scalar_one_or_none()

            if not existing_resident:
                resident = Resident(
                    society_id=society.id,
                    user_id=resident_user.id,
                    code="RES-000001",
                    name=resident_user.name,
                    email=resident_user.email,
                    phone=resident_user.phone,
                    metadata_json={},
                    is_active=True,
                    version=1,
                )
                db.add(resident)
                await db.flush()
                logger.info("Created demo resident for %s", resident_user.email)
            else:
                resident = existing_resident
                logger.info("Skip existing resident for %s", resident_user.email)

            flat_101 = (
                await db.execute(
                    select(Flat)
                    .join(Wing, Flat.wing_id == Wing.id)
                    .where(
                        Flat.society_id == society.id,
                        Flat.flat_no == "101",
                        Wing.code == "A1",
                    )
                )
            ).scalar_one_or_none()

            if flat_101:
                active_occ = (
                    await db.execute(
                        select(Occupancy).where(
                            Occupancy.resident_id == resident.id,
                            Occupancy.flat_id == flat_101.id,
                            Occupancy.status == "active",
                        )
                    )
                ).scalar_one_or_none()

                if not active_occ:
                    occ = Occupancy(
                        society_id=society.id,
                        building_id=flat_101.building_id,
                        wing_id=flat_101.wing_id,
                        flat_id=flat_101.id,
                        resident_id=resident.id,
                        role="owner",
                        is_primary=True,
                        status="active",
                        move_in_date=date.today(),
                        metadata_json={},
                        is_active=True,
                        version=1,
                    )
                    db.add(occ)
                    await db.flush()
                    await derive_flat_from_occupancies(db, flat_101)
                    await sync_user_flat_for_resident(db, resident, preferred_flat_id=flat_101.id)
                    logger.info(
                        "Created active occupancy: %s → flat 101/A1",
                        resident_user.email,
                    )
                else:
                    logger.info("Skip existing occupancy for demo resident")

        # Phase 6: demo visitors + visits for occupancy flows
        active_occupancy = (
            await db.execute(
                select(Occupancy)
                .join(Flat, Occupancy.flat_id == Flat.id)
                .join(Wing, Occupancy.wing_id == Wing.id)
                .where(
                    Occupancy.society_id == society.id,
                    Occupancy.status == "active",
                    Flat.flat_no == "101",
                    Wing.code == "A1",
                )
                .limit(1)
            )
        ).scalar_one_or_none()

        if active_occupancy:
            demo_visitors = [
                ("Rohit Sharma", "9000011111", "guest"),
                ("Swiggy Rider", "9000011112", "delivery"),
                ("Anita Maid", "9000011113", "maid"),
            ]
            visitor_by_phone: dict[str, Visitor] = {}
            for name, phone, _ in demo_visitors:
                existing_visitor = (
                    await db.execute(
                        select(Visitor).where(Visitor.society_id == society.id, Visitor.phone == phone)
                    )
                ).scalar_one_or_none()
                if existing_visitor:
                    visitor_by_phone[phone] = existing_visitor
                    logger.info("Skip existing visitor: %s", phone)
                    continue
                visitor = Visitor(
                    society_id=society.id,
                    name=name,
                    phone=phone,
                    metadata_json={},
                    is_active=True,
                    version=1,
                )
                db.add(visitor)
                await db.flush()
                visitor_by_phone[phone] = visitor
                logger.info("Created demo visitor: %s (%s)", name, phone)

            for _, phone, vtype in demo_visitors:
                visitor = visitor_by_phone[phone]
                existing_visit = (
                    await db.execute(
                        select(Visit).where(
                            Visit.society_id == society.id,
                            Visit.occupancy_id == active_occupancy.id,
                            Visit.visitor_id == visitor.id,
                            Visit.status.in_(("scheduled", "waiting", "approved", "checked_in")),
                        )
                    )
                ).scalar_one_or_none()
                if existing_visit:
                    logger.info("Skip existing open visit for %s", phone)
                    continue
                visit = Visit(
                    society_id=society.id,
                    building_id=active_occupancy.building_id,
                    wing_id=active_occupancy.wing_id,
                    flat_id=active_occupancy.flat_id,
                    occupancy_id=active_occupancy.id,
                    visitor_id=visitor.id,
                    purpose="Seeded visitor flow",
                    visitor_type=vtype,
                    pass_type="one_time",
                    status="scheduled",
                    scheduled_at=datetime.now(timezone.utc),
                    expected_at=datetime.now(timezone.utc),
                    number_of_people=1,
                    is_preapproved=True,
                    metadata_json={},
                    is_active=True,
                    version=1,
                )
                db.add(visit)
                logger.info("Created demo visit: %s (%s)", visitor.name, vtype)

        # Phase 7: gates, staff, shifts
        gate_defs = [
            ("MAIN", "Main Vehicle Gate", "main", 1),
            ("PED-1", "Pedestrian Gate", "pedestrian", 2),
            ("SVC-1", "Service Gate", "service", 3),
        ]
        gate_by_code: dict[str, Gate] = {}
        for code, name, gtype, seq in gate_defs:
            existing_gate = (
                await db.execute(
                    select(Gate).where(Gate.society_id == society.id, Gate.code == code)
                )
            ).scalar_one_or_none()
            if existing_gate:
                gate_by_code[code] = existing_gate
                logger.info("Skip existing gate: %s", code)
                continue
            gate = Gate(
                society_id=society.id,
                code=code,
                name=name,
                gate_type=gtype,
                sequence=seq,
                metadata_json={},
                is_active=True,
                version=1,
            )
            db.add(gate)
            await db.flush()
            gate_by_code[code] = gate
            logger.info("Created demo gate: %s", code)

        guard_user = (
            await db.execute(
                select(User).where(User.email == "guard@society.com", User.society_id == society.id)
            )
        ).scalar_one_or_none()

        staff_guard = (
            await db.execute(
                select(Staff).where(Staff.society_id == society.id, Staff.code == "STF-000001")
            )
        ).scalar_one_or_none()
        if not staff_guard:
            staff_guard = Staff(
                society_id=society.id,
                user_id=guard_user.id if guard_user else None,
                code="STF-000001",
                name=guard_user.name if guard_user else "Demo Guard",
                phone=guard_user.phone if guard_user else "9000090001",
                email=guard_user.email if guard_user else None,
                staff_role="security_guard",
                employment_type="permanent",
                assigned_gate_id=gate_by_code.get("MAIN").id if gate_by_code.get("MAIN") else None,
                joining_date=date.today(),
                metadata_json={},
                is_active=True,
                version=1,
            )
            db.add(staff_guard)
            await db.flush()
            logger.info("Created demo staff: STF-000001")
        else:
            if guard_user and staff_guard.user_id is None:
                staff_guard.user_id = guard_user.id
                logger.info("Linked existing staff STF-000001 to demo guard user")
            else:
                logger.info("Skip existing staff: STF-000001")

        for code, name, phone, role in (
            ("STF-000002", "Meena Housekeeping", "9000090002", "housekeeping"),
            ("STF-000003", "Ravi Facility", "9000090003", "facility_manager"),
        ):
            existing_staff = (
                await db.execute(
                    select(Staff).where(Staff.society_id == society.id, Staff.code == code)
                )
            ).scalar_one_or_none()
            if existing_staff:
                logger.info("Skip existing staff: %s", code)
                continue
            db.add(
                Staff(
                    society_id=society.id,
                    code=code,
                    name=name,
                    phone=phone,
                    staff_role=role,
                    employment_type="contract",
                    joining_date=date.today(),
                    metadata_json={},
                    is_active=True,
                    version=1,
                )
            )
            logger.info("Created demo staff: %s", code)

        await db.flush()

        from Services.staff_helpers import ensure_staff_profile_for_user

        society_guards = (
            await db.execute(
                select(User).where(
                    User.society_id == society.id,
                    User.role == "guard",
                    User.is_active.is_(True),
                )
            )
        ).scalars().all()
        for guser in society_guards:
            await ensure_staff_profile_for_user(db, guser.id, society.id)
        await db.flush()
        if staff_guard and gate_by_code.get("MAIN"):
            today = date.today()
            now = datetime.now(timezone.utc)
            # uq_shifts_staff_active: only one status='active' shift per staff, any date.
            leftover_active = (
                await db.execute(
                    select(Shift).where(
                        Shift.staff_id == staff_guard.id,
                        Shift.status == "active",
                        Shift.shift_date != today,
                    )
                )
            ).scalars().all()
            for leftover in leftover_active:
                leftover.status = "completed"
                leftover.actual_end = leftover.actual_end or now
                logger.info(
                    "Completed leftover active shift for %s", leftover.shift_date
                )
            if leftover_active:
                await db.flush()

            existing_shift = (
                await db.execute(
                    select(Shift).where(
                        Shift.society_id == society.id,
                        Shift.staff_id == staff_guard.id,
                        Shift.shift_date == today,
                        Shift.status.in_(("scheduled", "active")),
                    )
                )
            ).scalar_one_or_none()
            if not existing_shift:
                shift = Shift(
                    society_id=society.id,
                    staff_id=staff_guard.id,
                    gate_id=gate_by_code["MAIN"].id,
                    shift_date=today,
                    shift_type="morning",
                    scheduled_start=now.replace(hour=6, minute=0, second=0, microsecond=0),
                    scheduled_end=now.replace(hour=14, minute=0, second=0, microsecond=0),
                    actual_start=now,
                    status="active",
                    metadata_json={},
                    is_active=True,
                    version=1,
                )
                db.add(shift)
                logger.info("Created active morning shift for guard")
            else:
                logger.info("Skip existing shift for today")
            tomorrow = today + timedelta(days=1)
            existing_tom = (
                await db.execute(
                    select(Shift).where(
                        Shift.society_id == society.id,
                        Shift.staff_id == staff_guard.id,
                        Shift.shift_date == tomorrow,
                    )
                )
            ).scalar_one_or_none()
            if not existing_tom:
                db.add(
                    Shift(
                        society_id=society.id,
                        staff_id=staff_guard.id,
                        gate_id=gate_by_code["MAIN"].id,
                        shift_date=tomorrow,
                        shift_type="evening",
                        scheduled_start=datetime.combine(tomorrow, datetime.min.time()).replace(
                            hour=14, tzinfo=timezone.utc
                        ),
                        scheduled_end=datetime.combine(tomorrow, datetime.min.time()).replace(
                            hour=22, tzinfo=timezone.utc
                        ),
                        status="scheduled",
                        metadata_json={},
                        is_active=True,
                        version=1,
                    )
                )
                logger.info("Created tomorrow evening shift for guard")
            else:
                logger.info("Skip existing shift for tomorrow")
            await db.flush()

        # Phase 9: demo complaints
        demo_occ = (
            await db.execute(
                select(Occupancy)
                .where(
                    Occupancy.society_id == society.id,
                    Occupancy.status == "active",
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        staff_plumber = (
            await db.execute(
                select(Staff).where(
                    Staff.society_id == society.id,
                    Staff.staff_role == "plumber",
                    Staff.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if demo_occ and staff_plumber:
            existing_complaint = (
                await db.execute(
                    select(Complaint).where(
                        Complaint.society_id == society.id,
                        Complaint.title == "Kitchen tap leakage",
                    )
                )
            ).scalar_one_or_none()
            if not existing_complaint:
                complaint = Complaint(
                    society_id=society.id,
                    building_id=demo_occ.building_id,
                    wing_id=demo_occ.wing_id,
                    flat_id=demo_occ.flat_id,
                    occupancy_id=demo_occ.id,
                    resident_id=demo_occ.resident_id,
                    assigned_staff_id=staff_plumber.id,
                    category="plumbing",
                    title="Kitchen tap leakage",
                    description="Water dripping continuously from kitchen tap.",
                    priority="high",
                    status="assigned",
                    source="resident",
                    metadata_json={},
                    is_active=True,
                    version=1,
                )
                db.add(complaint)
                await db.flush()
                db.add(
                    ComplaintComment(
                        complaint_id=complaint.id,
                        author_type="resident",
                        author_id=demo_occ.resident_id,
                        message="Issue started yesterday evening.",
                        is_active=True,
                        version=1,
                    )
                )
                logger.info("Created demo complaint: Kitchen tap leakage")

        # Phase 10: billing & accounting demo data
        existing_maint = (
            await db.execute(
                select(ChargeHead).where(
                    ChargeHead.society_id == society.id,
                    ChargeHead.code == "MAINT",
                )
            )
        ).scalar_one_or_none()
        if not existing_maint:
            maint_head = ChargeHead(
                society_id=society.id,
                code="MAINT",
                name="Maintenance",
                category="maintenance",
                default_amount_minor=350000,
                is_recurring=True,
                is_taxable=False,
                display_order=1,
                metadata_json={},
                is_active=True,
                version=1,
            )
            water_head = ChargeHead(
                society_id=society.id,
                code="WATER",
                name="Water Charges",
                category="water",
                default_amount_minor=50000,
                is_recurring=True,
                is_taxable=False,
                display_order=2,
                metadata_json={},
                is_active=True,
                version=1,
            )
            db.add(maint_head)
            db.add(water_head)
            await db.flush()
            logger.info("Created charge heads: MAINT, WATER")
        else:
            maint_head = existing_maint
            water_head = (
                await db.execute(
                    select(ChargeHead).where(
                        ChargeHead.society_id == society.id,
                        ChargeHead.code == "WATER",
                    )
                )
            ).scalar_one_or_none()

        today = date.today()
        if today.month >= 4:
            fy_start = date(today.year, 4, 1)
            fy_end = date(today.year + 1, 3, 31)
            fy_code = f"FY{today.year}-{str(today.year + 1)[-2:]}"
        else:
            fy_start = date(today.year - 1, 4, 1)
            fy_end = date(today.year, 3, 31)
            fy_code = f"FY{today.year - 1}-{str(today.year)[-2:]}"

        fy = (
            await db.execute(
                select(FinancialYear).where(
                    FinancialYear.society_id == society.id,
                    FinancialYear.code == fy_code,
                )
            )
        ).scalar_one_or_none()
        if not fy:
            fy = FinancialYear(
                society_id=society.id,
                code=fy_code,
                name=f"Financial Year {fy_code[2:]}",
                start_date=fy_start,
                end_date=fy_end,
                status="open",
                next_bill_seq=1,
                next_receipt_seq=1,
                metadata_json={"next_payment_seq": 1},
                is_active=True,
                version=1,
            )
            db.add(fy)
            await db.flush()
            y, m = fy_start.year, fy_start.month
            while True:
                p_start = date(y, m, 1)
                last = calendar.monthrange(y, m)[1]
                p_end = date(y, m, last)
                if p_start < fy_start:
                    p_start = fy_start
                if p_end > fy_end:
                    p_end = fy_end
                db.add(
                    AccountingPeriod(
                        society_id=society.id,
                        financial_year_id=fy.id,
                        period_key=f"{y:04d}-{m:02d}",
                        start_date=p_start,
                        end_date=p_end,
                        status="open",
                        metadata_json={},
                        is_active=True,
                        version=1,
                    )
                )
                if p_end >= fy_end:
                    break
                if m == 12:
                    y, m = y + 1, 1
                else:
                    m += 1
            await db.flush()
            logger.info("Created financial year %s with monthly periods", fy_code)

        cycle = (
            await db.execute(
                select(BillingCycle).where(
                    BillingCycle.society_id == society.id,
                    BillingCycle.code == "MONTHLY",
                )
            )
        ).scalar_one_or_none()
        if not cycle:
            cycle = BillingCycle(
                society_id=society.id,
                code="MONTHLY",
                name="Monthly Maintenance",
                frequency="monthly",
                day_of_month=1,
                default_due_days=10,
                auto_publish=True,
                metadata_json={},
                is_active=True,
                version=1,
            )
            db.add(cycle)
            await db.flush()
            logger.info("Created billing cycle MONTHLY")

        if demo_occ and maint_head and water_head:
            period_from = date(today.year, today.month, 1)
            last_day = calendar.monthrange(today.year, today.month)[1]
            period_to = date(today.year, today.month, last_day)
            due_date = date(today.year, today.month, min(10, last_day))
            period = (
                await db.execute(
                    select(AccountingPeriod).where(
                        AccountingPeriod.society_id == society.id,
                        AccountingPeriod.financial_year_id == fy.id,
                        AccountingPeriod.period_key == f"{today.year:04d}-{today.month:02d}",
                    )
                )
            ).scalar_one_or_none()
            existing_bill = (
                await db.execute(
                    select(MaintenanceBill).where(
                        MaintenanceBill.society_id == society.id,
                        MaintenanceBill.occupancy_id == demo_occ.id,
                        MaintenanceBill.period_from == period_from,
                        MaintenanceBill.period_to == period_to,
                    )
                )
            ).scalar_one_or_none()
            if not existing_bill:
                bill_seq = fy.next_bill_seq
                fy.next_bill_seq = bill_seq + 1
                gross = maint_head.default_amount_minor + water_head.default_amount_minor
                bill = MaintenanceBill(
                    society_id=society.id,
                    building_id=demo_occ.building_id,
                    wing_id=demo_occ.wing_id,
                    flat_id=demo_occ.flat_id,
                    occupancy_id=demo_occ.id,
                    resident_id=demo_occ.resident_id,
                    billing_cycle_id=cycle.id,
                    financial_year_id=fy.id,
                    accounting_period_id=period.id if period else None,
                    bill_number=f"{fy.code}-BILL-{bill_seq:05d}",
                    title=f"Monthly Maintenance {period_from.strftime('%b %Y')}",
                    status="paid",
                    bill_date=period_from,
                    period_from=period_from,
                    period_to=period_to,
                    due_date=due_date,
                    gross_minor=gross,
                    discount_minor=0,
                    penalty_minor=0,
                    tax_minor=0,
                    net_minor=gross,
                    paid_minor=gross,
                    outstanding_minor=0,
                    currency="INR",
                    published_at=datetime.now(timezone.utc),
                    source="system",
                    metadata_json={},
                    is_active=True,
                    version=1,
                )
                db.add(bill)
                await db.flush()
                db.add(
                    BillLineItem(
                        society_id=society.id,
                        bill_id=bill.id,
                        charge_head_id=maint_head.id,
                        line_no=1,
                        description=maint_head.name,
                        quantity=1,
                        unit_amount_minor=maint_head.default_amount_minor,
                        line_total_minor=maint_head.default_amount_minor,
                        tax_minor=0,
                        discount_minor=0,
                        is_penalty=False,
                        is_discount=False,
                        metadata_json={},
                        is_active=True,
                        version=1,
                    )
                )
                db.add(
                    BillLineItem(
                        society_id=society.id,
                        bill_id=bill.id,
                        charge_head_id=water_head.id,
                        line_no=2,
                        description=water_head.name,
                        quantity=1,
                        unit_amount_minor=water_head.default_amount_minor,
                        line_total_minor=water_head.default_amount_minor,
                        tax_minor=0,
                        discount_minor=0,
                        is_penalty=False,
                        is_discount=False,
                        metadata_json={},
                        is_active=True,
                        version=1,
                    )
                )
                meta = dict(fy.metadata_json or {})
                pay_seq = int(meta.get("next_payment_seq", 1))
                meta["next_payment_seq"] = pay_seq + 1
                fy.metadata_json = meta
                rcpt_seq = fy.next_receipt_seq
                fy.next_receipt_seq = rcpt_seq + 1
                now = datetime.now(timezone.utc)
                payment = Payment(
                    society_id=society.id,
                    resident_id=demo_occ.resident_id,
                    occupancy_id=demo_occ.id,
                    financial_year_id=fy.id,
                    accounting_period_id=period.id if period else None,
                    payment_number=f"{fy.code}-PAY-{pay_seq:05d}",
                    amount_minor=gross,
                    unallocated_minor=0,
                    currency="INR",
                    mode="cash",
                    status="cleared",
                    payment_date=now,
                    payer_name="Demo Resident",
                    metadata_json={},
                    is_active=True,
                    version=1,
                )
                db.add(payment)
                await db.flush()
                db.add(
                    PaymentAllocation(
                        society_id=society.id,
                        payment_id=payment.id,
                        bill_id=bill.id,
                        allocation_type="bill",
                        amount_minor=gross,
                        allocated_at=now,
                        metadata_json={},
                        is_active=True,
                        version=1,
                    )
                )
                db.add(
                    Receipt(
                        society_id=society.id,
                        payment_id=payment.id,
                        resident_id=demo_occ.resident_id,
                        financial_year_id=fy.id,
                        receipt_number=f"{fy.code}-RCPT-{rcpt_seq:05d}",
                        issued_at=now,
                        amount_minor=gross,
                        currency="INR",
                        is_void=False,
                        metadata_json={"mode": "cash"},
                        is_active=True,
                        version=1,
                    )
                )
                logger.info("Created demo published bill + cash payment + receipt")

        # Phase 11: Notices
        existing_notice = (
            await db.execute(
                select(Notice).where(
                    Notice.society_id == society.id,
                    Notice.notice_number == "NTC-000001",
                )
            )
        ).scalar_one_or_none()
        if existing_notice:
            logger.info("Skip existing notices")
        else:
            admin_user = (
                await db.execute(
                    select(User).where(
                        User.society_id == society.id,
                        User.role == "admin",
                    ).limit(1)
                )
            ).scalar_one_or_none()
            seed_building = next(iter(building_by_code.values()), None)
            if seed_building is None:
                seed_building = (
                    await db.execute(
                        select(Building).where(Building.society_id == society.id).limit(1)
                    )
                ).scalar_one_or_none()
            now = datetime.now(timezone.utc)
            society_notice = Notice(
                society_id=society.id,
                notice_number="NTC-000001",
                title="Welcome to Demo Housing Society",
                summary="Society-wide welcome notice for all residents.",
                body_text=(
                    "Welcome to Demo Housing Society. Please keep your contact details "
                    "updated and review pinned notices regularly."
                ),
                category="general",
                priority="normal",
                status="published",
                publish_at=now,
                published_at=now,
                is_pinned=True,
                requires_acknowledgement=False,
                audience_count_snapshot=1,
                published_by_user_id=admin_user.id if admin_user else None,
                metadata_json={},
                is_active=True,
                version=1,
            )
            db.add(society_notice)
            await db.flush()
            db.add(
                NoticeTarget(
                    society_id=society.id,
                    notice_id=society_notice.id,
                    target_type="society",
                    metadata_json={},
                    is_active=True,
                    version=1,
                )
            )
            db.add(
                NoticeAttachment(
                    notice_id=society_notice.id,
                    file_name="welcome-guide.pdf",
                    file_url="https://example.com/docs/welcome-guide.pdf",
                    mime_type="application/pdf",
                    file_size_bytes=1024,
                    sort_order=0,
                    uploaded_by=admin_user.id if admin_user else None,
                    is_active=True,
                    version=1,
                )
            )

            maint_notice = Notice(
                society_id=society.id,
                notice_number="NTC-000002",
                title="Water supply maintenance window",
                summary="Temporary water interruption tomorrow.",
                body_text=(
                    "Water supply may be interrupted between 11:00 AM and 1:00 PM tomorrow "
                    "for maintenance. Please store water accordingly."
                ),
                category="water",
                priority="high",
                status="published",
                publish_at=now - timedelta(days=1),
                published_at=now - timedelta(days=1),
                expires_at=now + timedelta(days=7),
                is_pinned=False,
                requires_acknowledgement=True,
                audience_count_snapshot=1,
                published_by_user_id=admin_user.id if admin_user else None,
                metadata_json={},
                is_active=True,
                version=1,
            )
            db.add(maint_notice)
            await db.flush()
            db.add(
                NoticeTarget(
                    society_id=society.id,
                    notice_id=maint_notice.id,
                    target_type="building" if seed_building else "society",
                    building_id=seed_building.id if seed_building else None,
                    metadata_json={},
                    is_active=True,
                    version=1,
                )
            )
            logger.info("Created demo society + building notices")

        # Phase 12: Document Management
        existing_category = (
            await db.execute(
                select(DocumentCategory).where(
                    DocumentCategory.society_id == society.id,
                    DocumentCategory.code == "SOCIETY_DOCS",
                )
            )
        ).scalar_one_or_none()
        if existing_category:
            logger.info("Skip existing document categories")
        else:
            doc_now = datetime.now(timezone.utc)
            admin_user = (
                await db.execute(
                    select(User).where(
                        User.society_id == society.id,
                        User.role == "admin",
                    ).limit(1)
                )
            ).scalar_one_or_none()
            finance_user = (
                await db.execute(
                    select(User).where(
                        User.society_id == society.id,
                        User.role == "finance",
                    ).limit(1)
                )
            ).scalar_one_or_none()

            if not admin_user:
                logger.info("Skip document seed — no admin user found")
            else:
                society_docs_category = DocumentCategory(
                    society_id=society.id,
                    code="SOCIETY_DOCS",
                    name="Society Documents",
                    display_order=1,
                    description="Bye-laws, meeting minutes, and general society documents.",
                    icon="building",
                    metadata_json={},
                    is_active=True,
                    version=1,
                )
                finance_docs_category = DocumentCategory(
                    society_id=society.id,
                    code="FINANCE_DOCS",
                    name="Financial Documents",
                    display_order=2,
                    description="Budgets, audit reports, and finance statements.",
                    icon="wallet",
                    metadata_json={},
                    is_active=True,
                    version=1,
                )
                security_docs_category = DocumentCategory(
                    society_id=society.id,
                    code="SECURITY_DOCS",
                    name="Security Documents",
                    display_order=3,
                    description="Gate protocols and security guidelines.",
                    icon="shield",
                    metadata_json={},
                    is_active=True,
                    version=1,
                )
                db.add_all([society_docs_category, finance_docs_category, security_docs_category])
                await db.flush()

                society_doc = Document(
                    society_id=society.id,
                    category_id=society_docs_category.id,
                    title="Society Bye Laws",
                    description="Official bye-laws governing the society.",
                    file_name="society-bye-laws.pdf",
                    file_url="https://example.com/docs/society-bye-laws.pdf",
                    file_size_bytes=204800,
                    mime_type="application/pdf",
                    document_number="DOC-000001",
                    status="published",
                    scope="society",
                    tags=["bye-laws", "governance"],
                    is_pinned=True,
                    uploaded_by=admin_user.id,
                    published_by=admin_user.id,
                    published_at=doc_now,
                    metadata_json={},
                    is_active=True,
                    version=1,
                )
                db.add(society_doc)
                await db.flush()
                db.add(
                    DocumentPermission(
                        document_id=society_doc.id,
                        society_id=society.id,
                        permission_type="everyone",
                        can_download=True,
                        metadata_json={},
                        is_active=True,
                        version=1,
                    )
                )

                finance_uploader = finance_user or admin_user
                finance_doc = Document(
                    society_id=society.id,
                    category_id=finance_docs_category.id,
                    title="Annual Budget Report FY24-25",
                    description="Approved annual budget for the financial year.",
                    file_name="annual-budget-fy24-25.pdf",
                    file_url="https://example.com/docs/annual-budget-fy24-25.pdf",
                    file_size_bytes=512000,
                    mime_type="application/pdf",
                    document_number="DOC-000002",
                    status="published",
                    scope="finance",
                    tags=["budget", "finance"],
                    uploaded_by=finance_uploader.id,
                    published_by=finance_uploader.id,
                    published_at=doc_now,
                    metadata_json={},
                    is_active=True,
                    version=1,
                )
                db.add(finance_doc)
                await db.flush()
                db.add(
                    DocumentPermission(
                        document_id=finance_doc.id,
                        society_id=society.id,
                        permission_type="role",
                        role_name="finance",
                        can_download=True,
                        metadata_json={},
                        is_active=True,
                        version=1,
                    )
                )

                guard_doc = Document(
                    society_id=society.id,
                    category_id=security_docs_category.id,
                    title="Gate Security Protocol",
                    description="Standard operating procedure for gate security staff.",
                    file_name="gate-security-protocol.pdf",
                    file_url="https://example.com/docs/gate-security-protocol.pdf",
                    file_size_bytes=153600,
                    mime_type="application/pdf",
                    document_number="DOC-000003",
                    status="published",
                    scope="guard",
                    tags=["security", "sop"],
                    uploaded_by=admin_user.id,
                    published_by=admin_user.id,
                    published_at=doc_now,
                    metadata_json={},
                    is_active=True,
                    version=1,
                )
                db.add(guard_doc)
                await db.flush()
                db.add(
                    DocumentPermission(
                        document_id=guard_doc.id,
                        society_id=society.id,
                        permission_type="role",
                        role_name="guard",
                        can_download=True,
                        metadata_json={},
                        is_active=True,
                        version=1,
                    )
                )
                logger.info("Created demo document categories + documents + permissions")

        # Phase 13: Amenities booking
        existing_amenity = (
            await db.execute(
                select(Facility).where(
                    Facility.society_id == society.id,
                    Facility.slug == "clubhouse",
                )
            )
        ).scalar_one_or_none()
        if existing_amenity:
            logger.info("Skip existing amenities")
        else:
            admin_user = (
                await db.execute(
                    select(User).where(User.society_id == society.id, User.role == "admin").limit(1)
                )
            ).scalar_one_or_none()
            resident_user = (
                await db.execute(
                    select(User).where(User.society_id == society.id, User.role == "resident").limit(1)
                )
            ).scalar_one_or_none()
            resident = (
                await db.execute(
                    select(Resident).where(Resident.society_id == society.id, Resident.user_id == resident_user.id)
                )
            ).scalar_one_or_none() if resident_user else None

            clubhouse = Facility(
                society_id=society.id,
                name="Clubhouse",
                slug=slugify("Clubhouse"),
                description="Main clubhouse available for events and gatherings.",
                category="clubhouse",
                location="Tower A Podium",
                capacity=2,
                is_paid=True,
                price_per_slot=2500,
                security_deposit=5000,
                slot_duration_minutes=60,
                advance_booking_days=30,
                cancellation_hours=24,
                max_bookings_per_resident=2,
                requires_approval=True,
                operating_hours_start="08:00",
                operating_hours_end="22:00",
                available_days="0123456",
                rules_text="Keep the area clean and follow noise restrictions.",
                status="active",
                metadata_json={},
                is_active=True,
                version=1,
                created_by=admin_user.id if admin_user else None,
                updated_by=admin_user.id if admin_user else None,
            )
            gym = Facility(
                society_id=society.id,
                name="Gym",
                slug=slugify("Gym"),
                description="Residents-only gymnasium.",
                category="gym",
                location="Club Level -1",
                capacity=4,
                is_paid=False,
                price_per_slot=0,
                security_deposit=0,
                slot_duration_minutes=60,
                advance_booking_days=7,
                cancellation_hours=2,
                max_bookings_per_resident=1,
                requires_approval=False,
                operating_hours_start="06:00",
                operating_hours_end="23:00",
                available_days="0123456",
                status="active",
                metadata_json={},
                is_active=True,
                version=1,
                created_by=admin_user.id if admin_user else None,
                updated_by=admin_user.id if admin_user else None,
            )
            swimming_pool = Facility(
                society_id=society.id,
                name="Swimming Pool",
                slug=slugify("Swimming Pool"),
                description="Outdoor swimming pool with lifeguard on duty.",
                category="swimming_pool",
                location="Podium Level",
                capacity=10,
                is_paid=True,
                price_per_slot=500,
                security_deposit=0,
                slot_duration_minutes=60,
                advance_booking_days=14,
                cancellation_hours=6,
                max_bookings_per_resident=1,
                requires_approval=False,
                operating_hours_start="06:00",
                operating_hours_end="20:00",
                available_days="0123456",
                rules_text="Children under 12 must be accompanied by an adult.",
                status="active",
                metadata_json={},
                is_active=True,
                version=1,
                created_by=admin_user.id if admin_user else None,
                updated_by=admin_user.id if admin_user else None,
            )
            badminton_court = Facility(
                society_id=society.id,
                name="Badminton Court",
                slug=slugify("Badminton Court"),
                description="Indoor badminton court, single court booking.",
                category="badminton_court",
                location="Sports Complex",
                capacity=1,
                is_paid=False,
                price_per_slot=0,
                security_deposit=0,
                slot_duration_minutes=45,
                advance_booking_days=7,
                cancellation_hours=2,
                max_bookings_per_resident=2,
                requires_approval=False,
                operating_hours_start="06:00",
                operating_hours_end="22:00",
                available_days="0123456",
                status="active",
                metadata_json={},
                is_active=True,
                version=1,
                created_by=admin_user.id if admin_user else None,
                updated_by=admin_user.id if admin_user else None,
            )
            db.add_all([clubhouse, gym, swimming_pool, badminton_court])
            await db.flush()

            tomorrow = date.today() + timedelta(days=1)
            if resident and resident_user:
                db.add(
                    FacilityBooking(
                        society_id=society.id,
                        amenity_id=clubhouse.id,
                        resident_id=resident.id,
                        user_id=resident_user.id,
                        booking_number="BKG-000001",
                        booking_date=tomorrow,
                        start_time="18:00",
                        end_time="19:00",
                        guest_count=10,
                        purpose="Birthday party",
                        status="pending",
                        amount=2500,
                        security_deposit=5000,
                        payment_status="pending",
                        booking_code=generate_booking_code(),
                        metadata_json={},
                        is_active=True,
                        version=1,
                        created_by=resident_user.id,
                        updated_by=resident_user.id,
                    )
                )
                db.add(
                    FacilityBooking(
                        society_id=society.id,
                        amenity_id=badminton_court.id,
                        resident_id=resident.id,
                        user_id=resident_user.id,
                        booking_number="BKG-000002",
                        booking_date=date.today(),
                        start_time="17:00",
                        end_time="17:45",
                        guest_count=1,
                        purpose="Evening game",
                        status="confirmed",
                        amount=0,
                        security_deposit=0,
                        payment_status="not_required",
                        booking_code=generate_booking_code(),
                        metadata_json={},
                        is_active=True,
                        version=1,
                        created_by=resident_user.id,
                        updated_by=resident_user.id,
                    )
                )
            logger.info("Created demo amenities and bookings")

        # Phase 14: Parking management
        existing_zone = (
            await db.execute(
                select(ParkingZone).where(
                    ParkingZone.society_id == society.id,
                    ParkingZone.code == "BASM-A",
                )
            )
        ).scalar_one_or_none()
        if existing_zone:
            logger.info("Skip existing parking")
        else:
            admin_user = (
                await db.execute(
                    select(User).where(User.society_id == society.id, User.role == "admin").limit(1)
                )
            ).scalar_one_or_none()
            resident_user = (
                await db.execute(
                    select(User).where(User.society_id == society.id, User.role == "resident").limit(1)
                )
            ).scalar_one_or_none()
            resident = (
                await db.execute(
                    select(Resident).where(
                        Resident.society_id == society.id, Resident.user_id == resident_user.id
                    )
                )
            ).scalar_one_or_none() if resident_user else None

            basement = ParkingZone(
                society_id=society.id,
                code="BASM-A",
                name="Basement A",
                description="Covered basement parking for residents.",
                zone_type="basement",
                floor_label="B1",
                total_slots=0,
                available_slots=0,
                is_visitor_allowed=False,
                monthly_fee_minor=150000,
                visitor_fee_minor=0,
                additional_vehicle_fee_minor=50000,
                metadata_json={},
                is_active=True,
                version=1,
                created_by=admin_user.id if admin_user else None,
                updated_by=admin_user.id if admin_user else None,
            )
            visitor_zone = ParkingZone(
                society_id=society.id,
                code="VIS-OPEN",
                name="Visitor Open",
                description="Open visitor parking near the main gate.",
                zone_type="visitor",
                floor_label="G",
                total_slots=0,
                available_slots=0,
                is_visitor_allowed=True,
                monthly_fee_minor=0,
                visitor_fee_minor=5000,
                additional_vehicle_fee_minor=0,
                metadata_json={},
                is_active=True,
                version=1,
                created_by=admin_user.id if admin_user else None,
                updated_by=admin_user.id if admin_user else None,
            )
            db.add_all([basement, visitor_zone])
            await db.flush()

            slots = [
                ParkingSlot(
                    society_id=society.id,
                    zone_id=basement.id,
                    slot_code="B1-01",
                    label="Basement A-01",
                    slot_category="standard",
                    vehicle_types_allowed="car,ev",
                    status="available",
                    floor_no=-1,
                    is_covered=True,
                    is_ev_charging=False,
                    monthly_fee_minor=150000,
                    metadata_json={},
                    is_active=True,
                    version=1,
                    created_by=admin_user.id if admin_user else None,
                    updated_by=admin_user.id if admin_user else None,
                ),
                ParkingSlot(
                    society_id=society.id,
                    zone_id=basement.id,
                    slot_code="B1-02",
                    label="Basement A-02 EV",
                    slot_category="ev",
                    vehicle_types_allowed="ev",
                    status="available",
                    floor_no=-1,
                    is_covered=True,
                    is_ev_charging=True,
                    monthly_fee_minor=180000,
                    metadata_json={},
                    is_active=True,
                    version=1,
                    created_by=admin_user.id if admin_user else None,
                    updated_by=admin_user.id if admin_user else None,
                ),
                ParkingSlot(
                    society_id=society.id,
                    zone_id=basement.id,
                    slot_code="B1-03",
                    label="Basement A-03",
                    slot_category="standard",
                    vehicle_types_allowed="car,bike,scooter",
                    status="available",
                    floor_no=-1,
                    is_covered=True,
                    is_ev_charging=False,
                    monthly_fee_minor=150000,
                    metadata_json={},
                    is_active=True,
                    version=1,
                    created_by=admin_user.id if admin_user else None,
                    updated_by=admin_user.id if admin_user else None,
                ),
                ParkingSlot(
                    society_id=society.id,
                    zone_id=visitor_zone.id,
                    slot_code="V-01",
                    label="Visitor 01",
                    slot_category="visitor",
                    vehicle_types_allowed="car,bike,scooter",
                    status="available",
                    floor_no=0,
                    is_covered=False,
                    is_ev_charging=False,
                    monthly_fee_minor=0,
                    metadata_json={},
                    is_active=True,
                    version=1,
                    created_by=admin_user.id if admin_user else None,
                    updated_by=admin_user.id if admin_user else None,
                ),
                ParkingSlot(
                    society_id=society.id,
                    zone_id=visitor_zone.id,
                    slot_code="V-02",
                    label="Visitor 02",
                    slot_category="visitor",
                    vehicle_types_allowed="car,bike,scooter",
                    status="available",
                    floor_no=0,
                    is_covered=False,
                    is_ev_charging=False,
                    monthly_fee_minor=0,
                    metadata_json={},
                    is_active=True,
                    version=1,
                    created_by=admin_user.id if admin_user else None,
                    updated_by=admin_user.id if admin_user else None,
                ),
            ]
            db.add_all(slots)
            await db.flush()

            basement.total_slots = 3
            basement.available_slots = 3
            visitor_zone.total_slots = 2
            visitor_zone.available_slots = 2

            if resident and resident_user:
                car = ResidentVehicle(
                    society_id=society.id,
                    resident_id=resident.id,
                    user_id=resident_user.id,
                    vehicle_number="MH12AB1234",
                    vehicle_type="car",
                    make="Honda",
                    model="City",
                    color="White",
                    is_primary=True,
                    is_verified=True,
                    status="active",
                    parking_code=generate_parking_code(),
                    metadata_json={},
                    is_active=True,
                    version=1,
                    created_by=resident_user.id,
                    updated_by=resident_user.id,
                )
                bike = ResidentVehicle(
                    society_id=society.id,
                    resident_id=resident.id,
                    user_id=resident_user.id,
                    vehicle_number="MH12XY9876",
                    vehicle_type="bike",
                    make="Honda",
                    model="Activa",
                    color="Grey",
                    is_primary=False,
                    is_verified=True,
                    status="active",
                    parking_code=generate_parking_code(),
                    metadata_json={},
                    is_active=True,
                    version=1,
                    created_by=resident_user.id,
                    updated_by=resident_user.id,
                )
                db.add_all([car, bike])
                await db.flush()

                allocation = ParkingAllocation(
                    society_id=society.id,
                    slot_id=slots[0].id,
                    resident_id=resident.id,
                    vehicle_id=car.id,
                    allocation_number="ALC-000001",
                    allocation_type="permanent",
                    status="active",
                    start_date=date.today(),
                    end_date=None,
                    monthly_fee_minor=150000,
                    payment_status="pending",
                    allocated_by=admin_user.id if admin_user else None,
                    allocated_at=datetime.now(timezone.utc),
                    metadata_json={},
                    is_active=True,
                    version=1,
                    created_by=admin_user.id if admin_user else None,
                    updated_by=admin_user.id if admin_user else None,
                )
                db.add(allocation)
                await db.flush()
                slots[0].status = "allocated"
                slots[0].current_allocation_id = allocation.id
                basement.available_slots = 2

            logger.info("Created demo parking zones, slots, vehicles, and allocation")

        # Phase 15: Notifications & communication
        existing_template = (
            await db.execute(
                select(NotificationTemplate).where(
                    NotificationTemplate.society_id == society.id,
                    NotificationTemplate.code == "payment_reminder",
                )
            )
        ).scalar_one_or_none()
        if existing_template:
            logger.info("Skip existing notification templates")
        else:
            admin_user = (
                await db.execute(
                    select(User).where(User.society_id == society.id, User.role == "admin").limit(1)
                )
            ).scalar_one_or_none()
            resident_user = (
                await db.execute(
                    select(User).where(User.society_id == society.id, User.role == "resident").limit(1)
                )
            ).scalar_one_or_none()
            resident = (
                await db.execute(
                    select(Resident).where(
                        Resident.society_id == society.id, Resident.user_id == resident_user.id
                    )
                )
            ).scalar_one_or_none() if resident_user else None

            template_defs = [
                (
                    "payment_reminder",
                    "Payment Reminder",
                    "billing",
                    "Dear {{resident_name}}, your payment of {{amount}} for invoice {{invoice_number}} is due at {{society_name}}.",
                ),
                (
                    "notice_published",
                    "Notice Published",
                    "notice",
                    "A new notice '{{notice_title}}' has been published at {{society_name}}.",
                ),
                (
                    "visitor_checked_in",
                    "Visitor Checked In",
                    "visitor",
                    "Visitor {{visitor_name}} has checked in at {{society_name}}.",
                ),
                (
                    "booking_approved",
                    "Booking Approved",
                    "amenity",
                    "Your amenity booking {{booking_number}} has been approved at {{society_name}}.",
                ),
                (
                    "parking_allocated",
                    "Parking Allocated",
                    "parking",
                    "Parking slot {{parking_slot}} has been allocated to {{resident_name}} at {{society_name}}.",
                ),
                (
                    "emergency_broadcast",
                    "Emergency Broadcast",
                    "emergency",
                    "Emergency alert from {{society_name}}: please check the app for details immediately.",
                ),
            ]
            for code, name, category, body in template_defs:
                db.add(
                    NotificationTemplate(
                        society_id=society.id,
                        code=code,
                        name=name,
                        category=category,
                        channel="in_app",
                        subject_template=name,
                        body_template=body,
                        priority="critical" if category == "emergency" else "normal",
                        is_system=True,
                        metadata_json={},
                        is_active=True,
                        version=1,
                        created_by=admin_user.id if admin_user else None,
                        updated_by=admin_user.id if admin_user else None,
                    )
                )
            await db.flush()

            if resident_user:
                existing_prefs = (
                    await db.execute(
                        select(NotificationPreference).where(
                            NotificationPreference.society_id == society.id,
                            NotificationPreference.user_id == resident_user.id,
                        )
                    )
                ).scalar_one_or_none()
                if not existing_prefs:
                    db.add(
                        NotificationPreference(
                            society_id=society.id,
                            user_id=resident_user.id,
                            resident_id=resident.id if resident else None,
                            email_enabled=True,
                            sms_enabled=True,
                            push_enabled=True,
                            marketing_enabled=False,
                            system_enabled=True,
                            emergency_enabled=True,
                            metadata_json={},
                            is_active=True,
                            version=1,
                            created_by=admin_user.id if admin_user else None,
                            updated_by=admin_user.id if admin_user else None,
                        )
                    )

            if resident_user and resident:
                now = datetime.now(timezone.utc)
                for idx, (title, body, category) in enumerate(
                    [
                        (
                            "Welcome to Demo Society",
                            "Your notification center is active. You will receive billing, visitor, and notice alerts here.",
                            "system",
                        ),
                        (
                            "Parking allocation update",
                            "Your parking slot B1-01 is active. View details in the parking section.",
                            "parking",
                        ),
                    ],
                    start=1,
                ):
                    notification = Notification(
                        society_id=society.id,
                        source_module="system",
                        source_event="Seed",
                        category=category,
                        priority="normal",
                        title=title,
                        body=body,
                        payload_json={"seed": True, "index": idx},
                        target_type="resident",
                        resident_id=resident.id,
                        user_id=resident_user.id,
                        status="delivered",
                        sent_at=now,
                        metadata_json={},
                        is_active=True,
                        version=1,
                        created_by=admin_user.id if admin_user else None,
                        updated_by=admin_user.id if admin_user else None,
                    )
                    db.add(notification)
                    await db.flush()
                    db.add(
                        NotificationDelivery(
                            society_id=society.id,
                            notification_id=notification.id,
                            channel="in_app",
                            recipient_user_id=resident_user.id,
                            recipient_resident_id=resident.id,
                            status="delivered",
                            attempt_count=1,
                            delivered_at=now,
                            provider_response={"simulated": True, "seed": True},
                            metadata_json={},
                        )
                    )
            logger.info("Created demo notification templates, preferences, and sample notifications")

        admin_user = (
            await db.execute(
                select(User).where(User.society_id == society.id, User.role == "admin").limit(1)
            )
        ).scalar_one_or_none()
        guard_templates = [
            (
                "sos_alert",
                "SOS Alert",
                "emergency",
                "SOS at {{society_name}}: {{complaint_title}}. Respond from the guard dashboard.",
                "critical",
            ),
            (
                "guard_notice",
                "Guard Notice",
                "notice",
                "A notice '{{notice_title}}' was published at {{society_name}}.",
                "high",
            ),
            (
                "expected_visitor",
                "Expected Visitor",
                "visitor",
                "{{visitor_name}} is expected at the gate for {{purpose}} at {{society_name}}.",
                "high",
            ),
            (
                "shift_scheduled",
                "Shift Scheduled",
                "system",
                "Your {{shift_type}} shift is scheduled for {{shift_date}} at {{society_name}}.",
                "normal",
            ),
            (
                "complaint_assigned",
                "Complaint Assigned",
                "complaint",
                "Complaint '{{complaint_title}}' has been assigned to you at {{society_name}}.",
                "high",
            ),
        ]
        for code, name, category, body, priority in guard_templates:
            exists = (
                await db.execute(
                    select(NotificationTemplate).where(
                        NotificationTemplate.society_id == society.id,
                        NotificationTemplate.code == code,
                    )
                )
            ).scalar_one_or_none()
            if exists:
                continue
            db.add(
                NotificationTemplate(
                    society_id=society.id,
                    code=code,
                    name=name,
                    category=category,
                    channel="in_app",
                    subject_template=name,
                    body_template=body,
                    priority=priority,
                    is_system=True,
                    metadata_json={},
                    is_active=True,
                    version=1,
                    created_by=admin_user.id if admin_user else None,
                    updated_by=admin_user.id if admin_user else None,
                )
            )
            logger.info("Created notification template: %s", code)
        await db.flush()

        society_guards = (
            await db.execute(
                select(User).where(
                    User.society_id == society.id,
                    User.role == "guard",
                    User.is_active.is_(True),
                )
            )
        ).scalars().all()
        now = datetime.now(timezone.utc)
        guard_samples = [
            (
                "SOS alert — Flat A-101",
                "Critical security SOS from Flat A-101. Check the dashboard and respond immediately.",
                "emergency",
                "critical",
            ),
            (
                "Expected visitor: Courier",
                "A pre-approved courier for Flat B-204 is expected at the main gate.",
                "visitor",
                "high",
            ),
            (
                "Notice: Parking closed tonight",
                "Basement parking will be closed from 10 PM for maintenance. Direct vehicles to visitor slots.",
                "notice",
                "high",
            ),
            (
                "Shift scheduled",
                "Your night shift is scheduled for today at the main gate.",
                "system",
                "normal",
            ),
        ]
        for guser in society_guards:
            existing_guard_note = (
                await db.execute(
                    select(Notification).where(
                        Notification.society_id == society.id,
                        Notification.user_id == guser.id,
                    ).limit(1)
                )
            ).scalar_one_or_none()
            if existing_guard_note:
                logger.info("Skip existing guard notifications for %s", guser.email)
                continue
            for idx, (title, body, category, priority) in enumerate(guard_samples, start=1):
                notification = Notification(
                    society_id=society.id,
                    source_module="system",
                    source_event="Seed",
                    category=category,
                    priority=priority,
                    title=title,
                    body=body,
                    payload_json={"seed": True, "index": idx, "role": "guard"},
                    target_type="role",
                    target_role="guard",
                    user_id=guser.id,
                    status="delivered",
                    sent_at=now,
                    metadata_json={},
                    is_active=True,
                    version=1,
                    created_by=admin_user.id if admin_user else None,
                    updated_by=admin_user.id if admin_user else None,
                )
                db.add(notification)
                await db.flush()
                db.add(
                    NotificationDelivery(
                        society_id=society.id,
                        notification_id=notification.id,
                        channel="in_app",
                        recipient_user_id=guser.id,
                        status="delivered",
                        attempt_count=1,
                        delivered_at=now,
                        provider_response={"simulated": True, "seed": True},
                        metadata_json={},
                    )
                )
            logger.info("Created sample guard notifications for %s", guser.email)

        # Phase 16 — Analytics catalog + initial facts
        from Services.analytics_helpers import ensure_catalog_seeded
        from Services import analytics_service as analytics_svc
        from datetime import date as date_cls

        await ensure_catalog_seeded(db, society.id)
        await analytics_svc.rebuild_society_day(db, society.id, date_cls.today())
        await analytics_svc.refresh_kpi_snapshots(db, society.id, admin_user.id if admin_user else None)
        logger.info("Seeded analytics catalog, daily facts, and KPI snapshots")

        # Phase 17 — Platform control plane
        from Services.platform_feature_service import ensure_default_flags
        from Services.platform_settings_service import ensure_default_settings
        from Services.platform_subscription_service import (
            ensure_default_plans,
            ensure_subscription_for_tenant,
        )
        from Models.platform import Tenant
        from Constants.constants import UserRole

        await ensure_default_flags(db)
        await ensure_default_plans(db)
        await ensure_default_settings(db)

        tenant_q = await db.execute(select(Tenant).where(Tenant.code == society.code))
        tenant = tenant_q.scalar_one_or_none()
        if not tenant:
            tenant = Tenant(
                name=society.name,
                code=society.code,
                display_name=society.display_name,
                status="active",
                society_id=society.id,
                admin_email="admin@society.com",
                plan_code="enterprise",
                provisioned_at=datetime.now(timezone.utc),
            )
            db.add(tenant)
            await db.flush()
            logger.info("Created platform tenant for demo society")
        await ensure_subscription_for_tenant(
            db,
            tenant,
            actor_id=admin_user.id if admin_user else tenant.id,
            actor_role="super_admin",
        )

        sa_email = "superadmin@platform.com"
        sa_q = await db.execute(select(User).where(User.email == sa_email))
        if not sa_q.scalar_one_or_none():
            db.add(
                User(
                    name="Platform Super Admin",
                    email=sa_email,
                    phone="9111111111",
                    password=hash_password(DEFAULT_PASSWORD),
                    role=UserRole.SUPER_ADMIN.value,
                    society_id=None,
                    is_active=True,
                    is_verified=True,
                    designation="Super Admin",
                )
            )
            created += 1
            logger.info("Created platform super admin %s", sa_email)
        else:
            skipped += 1

        # Phase 18 — Mobile & Integrations defaults
        from Services.integration_admin_service import ensure_default_providers

        created_providers = await ensure_default_providers(db)
        if created_providers:
            logger.info("Seeded %s integration providers", created_providers)

        await db.commit()
        logger.info("Seed complete — created=%s skipped=%s", created, skipped)
        logger.info("Default password for seeded users: %s", DEFAULT_PASSWORD)
        logger.info("Super Admin login: %s / %s (role=super_admin)", sa_email, DEFAULT_PASSWORD)


if __name__ == "__main__":
    asyncio.run(seed())
