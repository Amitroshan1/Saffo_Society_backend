from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from core.permissions import GATE_SOS_UPDATE, GATE_SOS_VIEW
from modules.guard_common.deps import GuardUser, guard_from_token, require_guard
from modules.guard_common.responses import success_response
from modules.guard_sos.manager import broadcast_sos_resolved, manager
from modules.guard_sos.service import get_sos_alert, list_sos_alerts, resolve_sos_alert

router = APIRouter(tags=["Guard SOS"])


@router.get("/guard/sos")
def fetch_sos_alerts(
    status: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    sortBy: str = Query("createdAt"),
    sortOrder: str = Query("desc"),
    dateFrom: date | None = Query(None, alias="from"),
    dateTo: date | None = Query(None, alias="to"),
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard(GATE_SOS_VIEW)),
):
    data = list_sos_alerts(
        db,
        current_user,
        status_filter=status,
        search=search,
        page=page,
        page_size=pageSize,
        sort_by=sortBy,
        sort_order=sortOrder.lower(),
        date_from=dateFrom,
        date_to=dateTo,
    )
    return success_response("Guard SOS alerts fetched", data.model_dump(mode="json"))


@router.get("/guard/sos/{sos_id}")
def fetch_sos_alert(
    sos_id: int,
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard(GATE_SOS_VIEW)),
):
    item = get_sos_alert(db, current_user, sos_id)
    return success_response("SOS alert fetched", item.model_dump(mode="json"))


@router.patch("/guard/sos/{sos_id}/resolve")
async def mark_sos_resolved(
    sos_id: int,
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard(GATE_SOS_UPDATE)),
):
    item = resolve_sos_alert(db, current_user, sos_id)
    payload = item.model_dump(mode="json")
    await broadcast_sos_resolved(current_user.society_id, payload)
    return success_response("SOS resolved", payload)


@router.websocket("/ws/guard/alerts")
async def guard_alerts(websocket: WebSocket, token: str | None = Query(None)):
    db = SessionLocal()
    try:
        user = guard_from_token(db, token)
    except HTTPException:
        await websocket.close(code=1008)
        return
    finally:
        db.close()

    await manager.connect(user.society_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(user.society_id, websocket)
