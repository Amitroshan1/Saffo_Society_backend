from sqlalchemy.orm import Session

from auth.models import Role, User
from modules.society.models import Society


def get_by_slug(db: Session, slug: str) -> Society | None:
    return db.query(Society).filter(Society.slug == slug).first()


def get_by_registration_number(db: Session, number: str) -> Society | None:
    return (
        db.query(Society)
        .filter(Society.registration_number == number)
        .first()
    )


def list_societies(db: Session) -> list[Society]:
    return db.query(Society).order_by(Society.id.asc()).all()


def get_role_by_name(db: Session, name: str) -> Role | None:
    return db.query(Role).filter(Role.name == name).first()


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email.lower()).first()