from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    society_id: int | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class SwitchSocietyRequest(BaseModel):
    society_id: int


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: str | None = None
    society_id: int | None = None
    permissions: list[str] = []


class MeResponse(BaseModel):
    user_id: int
    email: str
    is_platform_admin: bool
    role: str | None
    society_id: int | None
    permissions: list[str]