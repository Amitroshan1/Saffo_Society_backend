from datetime import datetime

from pydantic import BaseModel


class NotificationOut(BaseModel):
    id: int
    category: str
    title: str
    body: str
    is_read: bool
    created_at: datetime


class UnreadCountOut(BaseModel):
    count: int


class MarkAllReadOut(BaseModel):
    updated: int
