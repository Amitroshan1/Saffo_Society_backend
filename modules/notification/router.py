from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import AuthContext, require_permission
from modules.notification import service
from modules.notification.schemas import MarkAllReadOut, NotificationOut, UnreadCountOut
from core.permissions import NOTIFICATIONS_UPDATE, NOTIFICATIONS_VIEW
router = APIRouter(prefix="/resident", tags=["Resident notifications"])


@router.get("/notifications/unread-count", response_model=UnreadCountOut)
def unread_count(ctx: AuthContext = Depends(require_permission(NOTIFICATIONS_VIEW)), db: Session = Depends(get_db)):
    return service.unread_count(db, ctx.user.id, ctx.society_id)


@router.post("/notifications/mark-all-read", response_model=MarkAllReadOut)
def mark_all_read(ctx: AuthContext = Depends(require_permission(NOTIFICATIONS_UPDATE)), db: Session = Depends(get_db)):
    return service.mark_all_read(db, ctx.user.id, ctx.society_id)


@router.get("/notifications", response_model=list[NotificationOut])
def notifications(
    category: str | None = Query(None),
    ctx: AuthContext = Depends(require_permission(NOTIFICATIONS_VIEW)),
    db: Session = Depends(get_db),
):
    return service.list_inbox(db, ctx.user.id, ctx.society_id, category)


@router.get("/notifications/{notification_id}", response_model=NotificationOut)
def notification_detail(
    notification_id: int,
    ctx: AuthContext = Depends(require_permission(NOTIFICATIONS_VIEW)),
    db: Session = Depends(get_db),
):
    return service.get_one(db, ctx.user.id, ctx.society_id, notification_id)


@router.post("/notifications/{notification_id}/read", response_model=NotificationOut)
def mark_read(
    notification_id: int,
    ctx: AuthContext = Depends(require_permission(NOTIFICATIONS_UPDATE)),
    db: Session = Depends(get_db),
):
    return service.mark_read(db, ctx.user.id, ctx.society_id, notification_id)
