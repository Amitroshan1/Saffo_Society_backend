from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.config import settings
import uuid


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: int, society_id: int | None) -> str:
    payload = {
        "sub": str(user_id),
        "sid": society_id,
        "type": TOKEN_TYPE_ACCESS,
        "exp": datetime.now(timezone.utc)
        + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict:
    payload = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
    )
    if payload.get("type") != TOKEN_TYPE_ACCESS:
        raise JWTError("Not an access token")
    return payload


def decode_refresh_token(token: str) -> dict:
    payload = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
    )
    if payload.get("type") != TOKEN_TYPE_REFRESH:
        raise JWTError("Not a refresh token")
    return payload

def create_refresh_token(user_id: int, society_id: int | None) -> str:
    payload = {
        "sub": str(user_id),
        "sid": society_id,
        "type": TOKEN_TYPE_REFRESH,
        "jti": str(uuid.uuid4()),
        "exp": datetime.now(timezone.utc)
        + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)