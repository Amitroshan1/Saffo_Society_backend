import re

from fastapi import HTTPException
from sqlalchemy.orm import Session

from auth.models import Membership, User
from core.security import hash_password
from modules.society import crud
from modules.society.models import Society
from modules.society.schemas import SocietyCreate


def _slug_from_name(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "society"


def create_society_with_admin(db: Session, data: SocietyCreate) -> dict:
    slug = _slug_from_name(data.name)
    email = str(data.admin_email).strip().lower()
    society_email = str(data.email).strip().lower()
    reg_no = data.registration_number.strip()

    if crud.get_by_slug(db, slug):
        raise HTTPException(status_code=409, detail="Society name/slug already exists")
    if crud.get_by_registration_number(db, reg_no):
        raise HTTPException(status_code=409, detail="Registration number already exists")
    if crud.get_user_by_email(db, email):
        raise HTTPException(status_code=409, detail="Admin email already registered")

    admin_role = crud.get_role_by_name(db, "admin")
    if not admin_role:
        raise HTTPException(status_code=500, detail="Admin role missing. Run seed.py")

    society = Society(
        name=data.name.strip(),
        slug=slug,
        registration_number=reg_no,
        society_type=data.society_type.strip(),
        address=data.address.strip(),
        city=data.city.strip(),
        state=data.state.strip(),
        pincode=data.pincode.strip(),
        email=society_email,
        contact_number=data.contact_number.strip(),
        is_active=True,
    )
    db.add(society)
    db.flush()

    admin = User(
        email=email,
        password=hash_password(data.admin_password),
        is_active=True,
        is_platform_admin=False,
    )
    db.add(admin)
    db.flush()

    db.add(
        Membership(
            user_id=admin.id,
            society_id=society.id,
            role_id=admin_role.id,
            is_active=True,
        )
    )
    db.commit()
    db.refresh(society)

    return {
        "id": society.id,
        "name": society.name,
        "slug": society.slug,
        "registration_number": society.registration_number,
        "society_type": society.society_type,
        "address": society.address,
        "city": society.city,
        "state": society.state,
        "pincode": society.pincode,
        "email": society.email,
        "contact_number": society.contact_number,
        "is_active": society.is_active,
        "admin_email": admin.email,
    }


def list_societies(db: Session) -> list[Society]:
    return crud.list_societies(db)