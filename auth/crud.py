from sqlalchemy.orm import Session, joinedload
from modules.society.models import Society
from datetime import datetime, timezone
from auth.models import Membership, RevokedToken, Role, User


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

def is_refresh_revoked(db: Session, jti: str) -> bool:
    return db.query(RevokedToken).filter(RevokedToken.jti == jti).first() is not None

def revoke_refresh(db: Session, jti: str, user_id: int, expires_at: datetime) -> None:
    if is_refresh_revoked(db, jti):
        return
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    db.add(RevokedToken(jti=jti, user_id=user_id, expires_at=expires_at))
    db.commit()
