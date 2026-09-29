from datetime import date
from typing import Optional

from pydantic import BaseModel


class GuardProfileItem(BaseModel):
    id: int
    userId: int
    name: str
    email: str
    phone: Optional[str] = None
    designation: str
    staffCode: str
    gateName: str
    gateCode: str
    photoUrl: Optional[str] = None
    joiningDate: Optional[date] = None
    isActive: bool


class GuardProfileUpdate(BaseModel):
    name: str
    phone: Optional[str] = None


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str
