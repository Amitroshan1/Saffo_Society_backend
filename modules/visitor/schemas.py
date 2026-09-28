from pydantic import BaseModel


class InvitationIn(BaseModel):
    name: str
    phone: str
    visitor_type: str = "guest"
    purpose: str | None = None
    expected_now: bool = False


class ApprovalIn(BaseModel):
    visit_id: int
    action: str
    notes: str | None = None


class VisitOut(BaseModel):
    id: int
    visitor_name: str
    visitor_phone: str
    status: str
    visitor_type: str
    purpose: str | None
    is_preapproved: bool
    notes: str | None