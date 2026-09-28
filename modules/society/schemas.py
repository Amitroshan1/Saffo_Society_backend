from pydantic import BaseModel, EmailStr


class SocietyCreate(BaseModel):
    name: str
    registration_number: str
    society_type: str
    address: str
    city: str
    state: str
    pincode: str
    email: EmailStr
    contact_number: str
    admin_email: EmailStr
    admin_password: str


class SocietyOut(BaseModel):
    id: int
    name: str
    slug: str
    registration_number: str | None
    society_type: str | None
    address: str | None
    city: str | None
    state: str | None
    pincode: str | None
    email: str | None
    contact_number: str | None
    is_active: bool
    admin_email: str = ""

    class Config:
        from_attributes = True