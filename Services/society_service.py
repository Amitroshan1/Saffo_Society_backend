"""Society business logic."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from Models.society import DEFAULT_SOCIETY_SETTINGS, Society
from Models.user import User
from Schemas.common import ListQueryParams, build_pagination_meta
from Schemas.society import SocietyCreate, SocietyOut, SocietyUpdate, _validate_in_tax_ids
from Utils.audit import apply_create_audit, apply_update_audit
from Utils.errors import ApiError
from Utils.query import ListQueryBuilder
from Utils.soft_delete import soft_activate, soft_deactivate


def _society_dict(society: Society) -> Dict[str, Any]:
    return SocietyOut.from_orm_society(society).model_dump(mode="json")


async def get_default_society(db: AsyncSession) -> Optional[Society]:
    result = await db.execute(
        select(Society).where(Society.is_active.is_(True)).order_by(Society.created_at).limit(1)
    )
    return result.scalar_one_or_none()


async def create_society(
    db: AsyncSession,
    body: SocietyCreate,
    *,
    actor_id: UUID,
) -> Dict[str, Any]:
    existing = await db.execute(select(Society).where(Society.code == body.code))
    if existing.scalar_one_or_none():
        raise ApiError(409, "Society code already exists")

    settings = (
        body.settings.model_dump()
        if body.settings
        else dict(DEFAULT_SOCIETY_SETTINGS)
    )
    now = datetime.now(timezone.utc)
    society = Society(
        name=body.name,
        display_name=body.displayName or body.name,
        short_name=body.shortName,
        description=body.description,
        code=body.code,
        registration_no=body.registrationNo,
        registration_date=body.registrationDate,
        gstin=body.gstin,
        pan=body.pan,
        email=str(body.email) if body.email else None,
        phone=body.phone,
        contact_person=body.contactPerson,
        contact_designation=body.contactDesignation,
        contact_email=str(body.contactEmail) if body.contactEmail else None,
        contact_phone=body.contactPhone,
        address_line1=body.addressLine1,
        address_line2=body.addressLine2,
        city=body.city,
        state=body.state,
        pincode=body.pincode,
        country=body.country,
        website=body.website,
        logo_url=body.logoUrl,
        cover_image=body.coverImage,
        latitude=body.latitude,
        longitude=body.longitude,
        established_year=body.establishedYear,
        settings=settings,
        is_active=True,
        version=1,
        created_by=actor_id,
        updated_by=actor_id,
        last_activity_at=now,
    )
    apply_create_audit(society, actor_id)
    db.add(society)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise ApiError(409, "Society code already exists") from exc

    # Link creating admin if they have no society yet
    result = await db.execute(select(User).where(User.id == actor_id))
    actor = result.scalar_one_or_none()
    if actor and actor.society_id is None:
        actor.society_id = society.id

    await db.commit()
    await db.refresh(society)
    return {"society": _society_dict(society)}


async def list_societies(db: AsyncSession, query: ListQueryParams) -> Dict[str, Any]:
    allowed_sort = ("name", "code", "city", "created_at", "last_activity_at", "is_active")
    builder = (
        ListQueryBuilder(Society)
        .search(query.search, "name", "code", "city", "display_name", "short_name")
        .filter_eq("is_active", query.is_active)
        .sort(query.sort_by, query.sort_order, allowed_sort, default="name")
    )
    items, total = await builder.paginate(
        db,
        page=query.page,
        page_size=query.page_size,
        serialize=_society_dict,
    )
    return {
        "societies": items,
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def get_society(db: AsyncSession, society_id: UUID) -> Dict[str, Any]:
    society = await _get_or_404(db, society_id)
    return {"society": _society_dict(society)}


async def get_my_society(db: AsyncSession, society_id: Optional[UUID]) -> Dict[str, Any]:
    if not society_id:
        raise ApiError(400, "User is not linked to a society")
    return await get_society(db, society_id)


async def update_society(
    db: AsyncSession,
    society_id: UUID,
    body: SocietyUpdate,
    *,
    actor_id: UUID,
    actor_society_id: Optional[UUID],
) -> Dict[str, Any]:
    society = await _get_or_404(db, society_id)
    # Cross-tenant IDOR → 404 (ADL-005), same as Building/Wing/Flat
    if actor_society_id and actor_society_id != society.id:
        raise ApiError(404, "Society not found")

    data = body.model_dump(exclude_unset=True)
    field_map = {
        "name": "name",
        "displayName": "display_name",
        "shortName": "short_name",
        "description": "description",
        "registrationNo": "registration_no",
        "registrationDate": "registration_date",
        "gstin": "gstin",
        "pan": "pan",
        "email": "email",
        "phone": "phone",
        "contactPerson": "contact_person",
        "contactDesignation": "contact_designation",
        "contactEmail": "contact_email",
        "contactPhone": "contact_phone",
        "addressLine1": "address_line1",
        "addressLine2": "address_line2",
        "city": "city",
        "state": "state",
        "pincode": "pincode",
        "country": "country",
        "website": "website",
        "logoUrl": "logo_url",
        "coverImage": "cover_image",
        "latitude": "latitude",
        "longitude": "longitude",
        "establishedYear": "established_year",
    }

    for api_key, orm_key in field_map.items():
        if api_key in data:
            value = data[api_key]
            if api_key in ("email", "contactEmail") and value is not None:
                value = str(value)
            setattr(society, orm_key, value)

    if "settings" in data and data["settings"] is not None:
        merged = dict(society.settings or {})
        merged.update(data["settings"])
        society.settings = merged

    country = society.country or "IN"
    if country == "IN" and society.pincode and not re.fullmatch(r"\d{6}", society.pincode):
        raise ApiError(422, "pincode must be 6 digits for India")
    try:
        _validate_in_tax_ids(country, society.gstin, society.pan)
    except ValueError as exc:
        raise ApiError(422, str(exc)) from exc

    apply_update_audit(society, actor_id)

    await db.commit()
    await db.refresh(society)
    return {"society": _society_dict(society)}


async def set_society_active(
    db: AsyncSession,
    society_id: UUID,
    *,
    active: bool,
    actor_id: UUID,
    actor_society_id: Optional[UUID],
) -> Dict[str, Any]:
    society = await _get_or_404(db, society_id)
    if actor_society_id and actor_society_id != society.id:
        raise ApiError(404, "Society not found")

    if active:
        soft_activate(society, actor_id)
    else:
        soft_deactivate(society, actor_id)
    await db.commit()
    await db.refresh(society)
    msg = "Society activated" if active else "Society deactivated"
    return {"society": _society_dict(society), "message": msg}


async def _get_or_404(db: AsyncSession, society_id: UUID) -> Society:
    result = await db.execute(select(Society).where(Society.id == society_id))
    society = result.scalar_one_or_none()
    if not society:
        raise ApiError(404, "Society not found")
    return society
