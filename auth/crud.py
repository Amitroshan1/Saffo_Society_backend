from sqlalchemy.orm import Session, joinedload

from auth.models import Membership, Role, User
from modules.society.models import Society


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email.lower()).first()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def get_memberships_for_user(db: Session, user_id: int) -> list[Membership]:
    return (
        db.query(Membership)
        .options(joinedload(Membership.role).joinedload(Role.permissions))
        .filter(Membership.user_id == user_id, Membership.is_active == True)
        .all()
    )


def get_membership(db: Session, user_id: int, society_id: int) -> Membership | None:
    return (
        db.query(Membership)
        .options(joinedload(Membership.role).joinedload(Role.permissions))
        .filter(
            Membership.user_id == user_id,
            Membership.society_id == society_id,
            Membership.is_active == True,
        )
        .first()
    )


def get_society(db: Session, society_id: int) -> Society | None:
    return db.query(Society).filter(Society.id == society_id).first()