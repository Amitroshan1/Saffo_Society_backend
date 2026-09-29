from sqlalchemy.orm import Session

from app.database import SessionLocal
from auth.models import Membership, Permission, Role, RolePermission, User
from core.permissions import ALL_PERMISSIONS, ROLE_PERMISSIONS
from core.security import hash_password
from modules.society.models import Society
from modules.resident.models import Building, Flat, HouseholdMember, Occupancy, Resident
from modules.facility.models import Amenity
from modules.vehicle.models import ParkingSlot, Vehicle
from datetime import date, time

from modules.guard_profile.models import GuardProfile
from modules.schedule.models import Shift

def upsert_permissions(db: Session) -> dict[str, int]:
    perm_ids = {}
    for name in ALL_PERMISSIONS:
        perm = db.query(Permission).filter(Permission.name == name).first()
        if not perm:
            perm = Permission(name=name, description=name)
            db.add(perm)
            db.flush()
        perm_ids[name] = perm.id
    return perm_ids


def upsert_roles(db: Session, perm_ids: dict[str, int]) -> dict[str, int]:
    role_ids = {}
    for role_name, perm_names in ROLE_PERMISSIONS.items():
        role = db.query(Role).filter(Role.name == role_name).first()
        if not role:
            role = Role(name=role_name, description=role_name.replace("_", " "))
            db.add(role)
            db.flush()
        role_ids[role_name] = role.id

        db.query(RolePermission).filter(RolePermission.role_id == role.id).delete()
        for perm_name in perm_names:
            db.add(
                RolePermission(
                    role_id=role.id,
                    permission_id=perm_ids[perm_name],
                )
            )
    return role_ids


def upsert_society(db: Session) -> Society:
    society = db.query(Society).filter(Society.slug == "demo").first()
    if not society:
        society = Society(name="Demo Society", slug="demo", is_active=True)
        db.add(society)
        db.flush()
    return society


def upsert_user(db: Session, email: str, password: str, is_platform_admin: bool) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            password=hash_password(password),
            is_active=True,
            is_platform_admin=is_platform_admin,
        )
        db.add(user)
        db.flush()
    return user


def upsert_membership(db: Session, user: User, society: Society, role_id: int) -> None:
    existing = (
        db.query(Membership)
        .filter(Membership.user_id == user.id, Membership.society_id == society.id)
        .first()
    )
    if not existing:
        db.add(
            Membership(
                user_id=user.id,
                society_id=society.id,
                role_id=role_id,
                is_active=True,
            )
        )


def run() -> None:
    db = SessionLocal()
    try:
        perm_ids = upsert_permissions(db)
        role_ids = upsert_roles(db, perm_ids)
        society = upsert_society(db)

        upsert_user(db, "superadmin@local.com", "Admin@123", is_platform_admin=True)

        admin = upsert_user(db, "admin@demo.com", "Admin@123", is_platform_admin=False)
        upsert_membership(db, admin, society, role_ids["admin"])

        resident_user = upsert_user(db, "resident@society.com", "Admin@123", False)
        upsert_membership(db, resident_user, society, role_ids["resident"])

        building = db.query(Building).filter(
            Building.society_id == society.id, Building.name == "A"
        ).first()
        if not building:
            building = Building(society_id=society.id, name="A")
            db.add(building)
            db.flush()

        flat = db.query(Flat).filter(
            Flat.society_id == society.id, Flat.number == "101"
        ).first()
        if not flat:
            flat = Flat(society_id=society.id, building_id=building.id, number="101")
            db.add(flat)
            db.flush()

        resident = db.query(Resident).filter(Resident.user_id == resident_user.id).first()
        if not resident:
            resident = Resident(
                user_id=resident_user.id,
                society_id=society.id,
                full_name="Demo Resident",
                phone="9876543210",
                emergency_name="Parent",
                emergency_phone="9876543211",
            )
            db.add(resident)
            db.flush()

        occupancy = db.query(Occupancy).filter(
            Occupancy.resident_id == resident.id, Occupancy.is_active == True
        ).first()
        if not occupancy:
            occupancy = Occupancy(
                society_id=society.id,
                resident_id=resident.id,
                flat_id=flat.id,
                is_active=True,
            )
            db.add(occupancy)
            db.flush()
            db.add(
                HouseholdMember(
                    occupancy_id=occupancy.id,
                    name="Spouse",
                    relation="spouse",
                    phone="9876543212",
                )
            )
        slot = db.query(ParkingSlot).filter(
            ParkingSlot.society_id == society.id, ParkingSlot.code == "P-A-101"
        ).first()
        if not slot:
            slot = ParkingSlot(
                society_id=society.id,
                occupancy_id=occupancy.id,
                code="P-A-101",
                kind="resident",
                is_active=True,
            )
            db.add(slot)
            db.flush()

        car = db.query(Vehicle).filter(
            Vehicle.society_id == society.id, Vehicle.vehicle_number == "MH12AB1234"
        ).first()
        if not car:
            db.add(
                Vehicle(
                    society_id=society.id,
                    occupancy_id=occupancy.id,
                    slot_id=slot.id,
                    vehicle_number="MH12AB1234",
                    vehicle_type="car",
                    make="Honda",
                    model="City",
                    color="White",
                    is_primary=True,
                    parking_code=slot.code,
                )
            )

        clubhouse = db.query(Amenity).filter(
            Amenity.society_id == society.id, Amenity.name == "Clubhouse"
        ).first()
        if not clubhouse:
            db.add(
                Amenity(
                    society_id=society.id,
                    name="Clubhouse",
                    is_bookable=True,
                    open_time="06:00",
                    close_time="22:00",
                )
            )

        guard_user = upsert_user(db, "guard@society.com", "Admin@123", False)
        upsert_membership(db, guard_user, society, role_ids["security_guard"])

        if not db.query(GuardProfile).filter(GuardProfile.user_id == guard_user.id).first():
            db.add(
                GuardProfile(
                    society_id=society.id,
                    user_id=guard_user.id,
                    name="Demo Guard",
                    email=guard_user.email,
                    phone="9876500000",
                    designation="Security Guard",
                    staff_code="G-001",
                    gate_name="Main Gate",
                    gate_code="MG",
                    joining_date=date.today(),
                    is_active=True,
                )
            )

        today = date.today()
        shift = db.query(Shift).filter(
            Shift.guard_user_id == guard_user.id, Shift.duty_date == today
        ).first()
        if not shift:
            db.add(
                Shift(
                    society_id=society.id,
                    guard_user_id=guard_user.id,
                    staff_name="Demo Guard",
                    staff_code="G-001",
                    gate_name="Main Gate",
                    gate_code="MG",
                    latitude=18.5204,
                    longitude=73.8567,
                    radius_meters=100,
                    duty_date=today,
                    shift_type="morning",
                    start_time=time(6, 0),
                    end_time=time(14, 0),
                    status="scheduled",
                )
            )

        db.commit()
        print("Seed done.")
        print("  superadmin@local.com / Admin@123  (platform, no society)")
        print("  admin@demo.com / Admin@123        (society: demo, role: admin)")
        print("  resident@society.com / Admin@123   (flat A-101, role: resident)")
        print("  resident@society.com / Admin@123   (flat A-101, role: resident)")
        print("  guard@society.com / Admin@123      (society: demo, role: security_guard)")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()




if __name__ == "__main__":
    run()