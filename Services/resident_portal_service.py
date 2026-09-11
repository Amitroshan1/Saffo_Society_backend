"""Resident portal service layer."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from Models.building import Building
from Models.flat import Flat
from Models.occupancy import Occupancy
from Models.resident import Resident
from Models.society import Society
from Models.user import User
from Models.visit import Visit
from Schemas.document import ResidentDocumentListQueryParams
from Schemas.notice import ResidentNoticeListQueryParams
from Schemas.resident_portal import ResidentVisitorApprovalRequest, ResidentVisitorInvitationCreate
from Schemas.visit import VisitCreate, VisitDecision, VisitListQueryParams
from Schemas.visitor import VisitorCreate
from Services import document_service, notice_service, occupancy_service, visit_service, visitor_service
from Utils.errors import ApiError

OPEN_VISIT_STATUSES = {"scheduled", "waiting", "approved", "checked_in"}
UPCOMING_VISIT_STATUSES = {"scheduled", "waiting", "approved"}


async def _get_resident_context(
    db: AsyncSession, *, actor_id: UUID, actor_society_id: UUID | None
) -> dict[str, Any]:
    if not actor_society_id:
        raise ApiError(400, "User is not linked to a society")

    resident = (
        await db.execute(
            select(Resident).where(
                Resident.society_id == actor_society_id,
                Resident.user_id == actor_id,
                Resident.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if not resident:
        raise ApiError(404, "Resident profile not found")

    occupancies = (
        (
            await db.execute(
                select(Occupancy)
                .where(
                    Occupancy.society_id == actor_society_id,
                    Occupancy.resident_id == resident.id,
                    Occupancy.status == "active",
                    Occupancy.is_active.is_(True),
                )
                .order_by(Occupancy.is_primary.desc(), Occupancy.move_in_date.desc())
            )
        )
        .scalars()
        .all()
    )
    if not occupancies:
        raise ApiError(404, "Active occupancy not found for resident")

    primary_occupancy = next((o for o in occupancies if o.is_primary), occupancies[0])

    flat = (
        await db.execute(
            select(Flat).where(
                Flat.id == primary_occupancy.flat_id,
                Flat.society_id == actor_society_id,
            )
        )
    ).scalar_one_or_none()
    if not flat:
        raise ApiError(404, "Flat not found")

    building = (
        await db.execute(
            select(Building).where(
                Building.id == flat.building_id,
                Building.society_id == actor_society_id,
            )
        )
    ).scalar_one_or_none()
    society = (
        await db.execute(
            select(Society).where(
                Society.id == actor_society_id,
                Society.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    user = (await db.execute(select(User).where(User.id == actor_id))).scalar_one_or_none()

    return {
        "society_id": actor_society_id,
        "resident": resident,
        "occupancies": occupancies,
        "primary_occupancy": primary_occupancy,
        "flat": flat,
        "building": building,
        "society": society,
        "user": user,
    }


def _can_access_occupancy(ctx: dict[str, Any], occupancy_id: UUID) -> bool:
    return any(o.id == occupancy_id for o in ctx["occupancies"])


async def _assert_visit_in_resident_scope(
    db: AsyncSession, *, visit_id: UUID, ctx: dict[str, Any]
) -> None:
    visit = (
        await db.execute(
            select(Visit).where(
                Visit.id == visit_id,
                Visit.society_id == ctx["society_id"],
            )
        )
    ).scalar_one_or_none()
    if not visit:
        raise ApiError(404, "Visit not found")
    occupancy_ids = {o.id for o in ctx["occupancies"]}
    if visit.occupancy_id not in occupancy_ids:
        raise ApiError(404, "Visit not found")


async def get_dashboard(db: AsyncSession, *, actor_id: UUID, actor_society_id: UUID | None) -> dict:
    ctx = await _get_resident_context(db, actor_id=actor_id, actor_society_id=actor_society_id)
    primary = ctx["primary_occupancy"]

    household = await occupancy_service.get_flat_household(
        db, primary.flat_id, actor_society_id=ctx["society_id"]
    )
    upcoming = await visit_service.list_visits(
        db,
        VisitListQueryParams(
            page=1,
            page_size=5,
            flat_id=primary.flat_id,
            sort_by="expected_at",
            sort_order="asc",
        ),
        actor_society_id=ctx["society_id"],
    )
    recent = await visit_service.list_visits(
        db,
        VisitListQueryParams(
            page=1,
            page_size=5,
            flat_id=primary.flat_id,
            sort_by="created_at",
            sort_order="desc",
        ),
        actor_society_id=ctx["society_id"],
    )
    upcoming_visits = [v for v in upcoming["visits"] if v["status"] in UPCOMING_VISIT_STATUSES][:5]
    latest_notices = await get_notices(db, actor_id=actor_id, actor_society_id=actor_society_id)
    notice_summary = await notice_service.resident_dashboard_summary(
        db, actor_id=actor_id, actor_society_id=actor_society_id
    )

    return {
        "welcome": {
            "name": ctx["resident"].name,
            "residentCode": ctx["resident"].code,
        },
        "flat": {
            "id": str(ctx["flat"].id),
            "flatNo": ctx["flat"].flat_no,
            "floorNo": ctx["flat"].floor_no,
            "buildingName": ctx["building"].name if ctx["building"] else None,
            "wingId": str(primary.wing_id),
            "occupancyRole": primary.role,
        },
        "household": household["household"],
        "upcomingVisitors": upcoming_visits,
        "recentVisitors": recent["visits"][:5],
        "quickActions": [
            {"id": "invite-visitor", "label": "Invite Visitor", "path": "/resident/visitors"},
            {"id": "view-notices", "label": "View Notices", "path": "/resident/notices"},
            {"id": "my-profile", "label": "My Profile", "path": "/resident/profile"},
            {"id": "complaints", "label": "Create Complaint", "path": "/resident/complaints/new"},
        ],
        "emergencyContacts": [
            {
                "name": ctx["society"].contact_person if ctx["society"] else None,
                "phone": ctx["society"].contact_phone if ctx["society"] else None,
                "type": "society_office",
            },
            {
                "name": ctx["building"].emergency_contact_name if ctx["building"] else None,
                "phone": ctx["building"].emergency_contact_phone if ctx["building"] else None,
                "type": "building",
            },
        ],
        "latestNotices": latest_notices["notices"][:3],
        "noticesUnreadCount": notice_summary["unreadCount"],
        "pinnedNotices": notice_summary["pinnedNotices"],
        "paymentSummary": await _payment_summary(
            db, society_id=ctx["society_id"], resident_id=ctx["resident"].id
        ),
    }


async def _payment_summary(
    db: AsyncSession, *, society_id: UUID, resident_id: UUID
) -> dict[str, Any]:
    from Services.billing_helpers import sum_resident_outstanding

    outstanding = await sum_resident_outstanding(
        db, society_id=society_id, resident_id=resident_id
    )
    return {
        "status": "ok",
        "outstandingMinor": outstanding,
        "currency": "INR",
    }


async def get_household(db: AsyncSession, *, actor_id: UUID, actor_society_id: UUID | None) -> dict:
    ctx = await _get_resident_context(db, actor_id=actor_id, actor_society_id=actor_society_id)
    primary = ctx["primary_occupancy"]
    household = await occupancy_service.get_flat_household(
        db, primary.flat_id, actor_society_id=ctx["society_id"]
    )
    return {
        "primaryResidentId": str(ctx["resident"].id),
        "flatId": str(primary.flat_id),
        "household": household["household"],
    }


async def get_flat(db: AsyncSession, *, actor_id: UUID, actor_society_id: UUID | None) -> dict:
    ctx = await _get_resident_context(db, actor_id=actor_id, actor_society_id=actor_society_id)
    primary = ctx["primary_occupancy"]
    return {
        "society": {
            "id": str(ctx["society"].id) if ctx["society"] else None,
            "name": ctx["society"].name if ctx["society"] else None,
            "code": ctx["society"].code if ctx["society"] else None,
        },
        "building": {
            "id": str(ctx["building"].id) if ctx["building"] else None,
            "name": ctx["building"].name if ctx["building"] else None,
            "code": ctx["building"].code if ctx["building"] else None,
        },
        "flat": {
            "id": str(ctx["flat"].id),
            "flatNo": ctx["flat"].flat_no,
            "floorNo": ctx["flat"].floor_no,
            "areaSqft": ctx["flat"].area_sqft,
            "ownershipType": ctx["flat"].ownership_type,
            "status": ctx["flat"].status,
            "usageType": ctx["flat"].usage_type,
        },
        "occupancy": {
            "id": str(primary.id),
            "role": primary.role,
            "isPrimary": primary.is_primary,
            "status": primary.status,
            "moveInDate": primary.move_in_date.isoformat(),
        },
    }


async def get_visitors(
    db: AsyncSession,
    query: VisitListQueryParams,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> dict:
    ctx = await _get_resident_context(db, actor_id=actor_id, actor_society_id=actor_society_id)
    occupancy_ids = [o.id for o in ctx["occupancies"]]
    query.flat_id = ctx["primary_occupancy"].flat_id
    visits_data = await visit_service.list_visits(db, query, actor_society_id=ctx["society_id"])
    visits = [v for v in visits_data["visits"] if UUID(v["occupancyId"]) in occupancy_ids]
    return {"visits": visits, "pagination": visits_data["pagination"]}


async def create_visitor_invitation(
    db: AsyncSession,
    body: ResidentVisitorInvitationCreate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> dict:
    ctx = await _get_resident_context(db, actor_id=actor_id, actor_society_id=actor_society_id)
    occupancy = ctx["primary_occupancy"]
    if body.occupancyId:
        if not _can_access_occupancy(ctx, body.occupancyId):
            raise ApiError(404, "Occupancy not found")
        occupancy = next(o for o in ctx["occupancies"] if o.id == body.occupancyId)

    visitor_id = body.visitorId
    if not visitor_id:
        if not body.visitor:
            raise ApiError(422, "visitorId or visitor details are required")
        created = await visitor_service.create_visitor(
            db,
            VisitorCreate(**body.visitor.model_dump()),
            actor_id=actor_id,
            actor_society_id=ctx["society_id"],
        )
        visitor_id = UUID(str(created["visitor"]["id"]))

    payload = VisitCreate(
        occupancyId=occupancy.id,
        visitorId=visitor_id,
        purpose=body.purpose,
        visitorType=body.visitorType,
        passType=body.passType,
        expectedAt=body.expectedAt,
        scheduledAt=body.scheduledAt,
        vehicleNumber=body.vehicleNumber,
        numberOfPeople=body.numberOfPeople,
        notes=body.notes,
        status="scheduled",
        isPreapproved=False,
    )
    return await visit_service.create_visit(
        db,
        payload,
        actor_id=actor_id,
        actor_society_id=ctx["society_id"],
    )


async def visitor_approval_action(
    db: AsyncSession,
    body: ResidentVisitorApprovalRequest,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> dict:
    ctx = await _get_resident_context(db, actor_id=actor_id, actor_society_id=actor_society_id)
    await _assert_visit_in_resident_scope(db, visit_id=body.visitId, ctx=ctx)

    decision = VisitDecision(notes=body.notes)
    if body.action == "approve":
        return await visit_service.approve_visit(
            db, body.visitId, decision, actor_id=actor_id, actor_society_id=ctx["society_id"]
        )
    if body.action == "reject":
        return await visit_service.reject_visit(
            db, body.visitId, decision, actor_id=actor_id, actor_society_id=ctx["society_id"]
        )
    return await visit_service.cancel_visit(
        db, body.visitId, decision, actor_id=actor_id, actor_society_id=ctx["society_id"]
    )


async def get_notices(db: AsyncSession, *, actor_id: UUID, actor_society_id: UUID | None) -> dict:
    query = ResidentNoticeListQueryParams(page=1, page_size=20, sort_by="created_at", sort_order="desc")
    data = await notice_service.resident_list_notices(
        db, query, actor_id=actor_id, actor_society_id=actor_society_id
    )
    return {
        "societyId": str(actor_society_id),
        "notices": data["notices"],
        "pagination": data["pagination"],
    }


async def get_documents(db: AsyncSession, *, actor_id: UUID, actor_society_id: UUID | None) -> dict:
    query = ResidentDocumentListQueryParams(page=1, page_size=20, sort_by="created_at", sort_order="desc")
    data = await document_service.list_resident_documents(
        db, query, actor_id=actor_id, actor_society_id=actor_society_id
    )
    return {
        "societyId": str(actor_society_id),
        "documents": data["documents"],
        "pagination": data["pagination"],
    }


async def get_notifications(
    db: AsyncSession, *, actor_id: UUID, actor_society_id: UUID | None
) -> dict:
    ctx = await _get_resident_context(db, actor_id=actor_id, actor_society_id=actor_society_id)
    visit_items = (
        (
            await db.execute(
                select(Visit)
                .where(
                    and_(
                        Visit.society_id == ctx["society_id"],
                        Visit.flat_id == ctx["primary_occupancy"].flat_id,
                        Visit.status.in_(OPEN_VISIT_STATUSES),
                    )
                )
                .order_by(Visit.created_at.desc())
                .limit(5)
            )
        )
        .scalars()
        .all()
    )
    items = [
        {
            "id": str(v.id),
            "type": "visitor",
            "title": f"Visitor {v.status.replace('_', ' ').title()}",
            "message": v.purpose,
            "createdAt": v.created_at.isoformat(),
            "source": "event-adapter",
            "isRead": False,
        }
        for v in visit_items
    ]
    return {"notifications": items}
