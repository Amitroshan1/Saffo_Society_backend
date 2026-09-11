"""Tenant lifecycle, provisioning, resolver, usage, health, clone."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from Core.security import hash_password
from Models.facility import FacilityBooking
from Models.building import Building
from Models.complaint import Complaint
from Models.flat import Flat
from Models.parking import ParkingSlot
from Models.platform import Tenant
from Models.society import DEFAULT_SOCIETY_SETTINGS, Society
from Models.user import User
from Models.visit import Visit
from Schemas.common import ListQueryParams, build_pagination_meta
from Services.platform_helpers import (
    emit_platform_event,
    finish_job,
    generate_temp_password,
    iso,
    start_job,
    tenant_to_dict,
    utcnow,
    write_audit,
)
from Utils.audit import apply_create_audit, apply_update_audit
from Utils.errors import ApiError


async def resolve_tenant_by_society(
    db: AsyncSession, society_id: UUID
) -> Optional[Tenant]:
    result = await db.execute(select(Tenant).where(Tenant.society_id == society_id))
    return result.scalar_one_or_none()


async def resolve_tenant(db: AsyncSession, tenant_id: UUID) -> Tenant:
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise ApiError(404, "Tenant not found")
    return tenant


async def get_tenant_status_for_society(
    db: AsyncSession, society_id: UUID
) -> Optional[str]:
    tenant = await resolve_tenant_by_society(db, society_id)
    return tenant.status if tenant else None


async def list_tenants(
    db: AsyncSession, query: ListQueryParams, *, status: str | None = None
) -> Dict[str, Any]:
    stmt = select(Tenant)
    count_stmt = select(func.count()).select_from(Tenant)
    if status:
        stmt = stmt.where(Tenant.status == status)
        count_stmt = count_stmt.where(Tenant.status == status)
    if query.search:
        like = f"%{query.search}%"
        filt = Tenant.name.ilike(like) | Tenant.code.ilike(like)
        stmt = stmt.where(filt)
        count_stmt = count_stmt.where(filt)
    if query.is_active is not None:
        stmt = stmt.where(Tenant.is_active.is_(query.is_active))
        count_stmt = count_stmt.where(Tenant.is_active.is_(query.is_active))

    total = int((await db.execute(count_stmt)).scalar() or 0)
    sort_col = getattr(Tenant, query.sort_by, Tenant.created_at)
    stmt = stmt.order_by(sort_col.desc() if query.sort_order == "desc" else sort_col.asc())
    stmt = stmt.offset((query.page - 1) * query.page_size).limit(query.page_size)
    rows = (await db.execute(stmt)).scalars().all()
    return {
        "items": [tenant_to_dict(t) for t in rows],
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def create_tenant(
    db: AsyncSession,
    body: Dict[str, Any],
    *,
    actor_id: UUID,
    actor_role: str,
) -> Dict[str, Any]:
    code = str(body["code"]).strip().upper()
    existing = await db.execute(select(Tenant).where(Tenant.code == code))
    if existing.scalar_one_or_none():
        raise ApiError(409, "Tenant code already exists")
    society_code_clash = await db.execute(select(Society).where(Society.code == code))
    if society_code_clash.scalar_one_or_none():
        raise ApiError(409, "Society code already exists for this tenant code")

    tenant = Tenant(
        name=body["name"].strip(),
        code=code,
        display_name=body.get("displayName") or body["name"].strip(),
        status="draft",
        isolation_mode=body.get("isolationMode") or "shared",
        region=body.get("region") or "IN",
        timezone=body.get("timezone") or "Asia/Kolkata",
        admin_email=(body.get("adminEmail") or "").lower().strip() or None,
        plan_code=body.get("planCode") or "trial",
        notes=body.get("notes"),
    )
    apply_create_audit(tenant, actor_id)
    db.add(tenant)
    await db.flush()
    await write_audit(
        db,
        actor_user_id=actor_id,
        actor_role=actor_role,
        action="tenant.create",
        resource_type="tenant",
        resource_id=str(tenant.id),
        tenant_id=tenant.id,
        after=tenant_to_dict(tenant),
    )
    emit_platform_event(
        "TenantCreated",
        tenant_id=tenant.id,
        entity_type="tenant",
        entity_id=tenant.id,
        actor_id=actor_id,
    )
    await db.commit()
    await db.refresh(tenant)
    return tenant_to_dict(tenant)


async def update_tenant(
    db: AsyncSession,
    tenant_id: UUID,
    body: Dict[str, Any],
    *,
    actor_id: UUID,
    actor_role: str,
) -> Dict[str, Any]:
    tenant = await resolve_tenant(db, tenant_id)
    before = tenant_to_dict(tenant)
    for field, attr in (
        ("name", "name"),
        ("displayName", "display_name"),
        ("region", "region"),
        ("timezone", "timezone"),
        ("adminEmail", "admin_email"),
        ("notes", "notes"),
        ("planCode", "plan_code"),
    ):
        if field in body and body[field] is not None:
            val = body[field]
            if field == "adminEmail":
                val = str(val).lower().strip()
            setattr(tenant, attr, val)
    apply_update_audit(tenant, actor_id)
    await write_audit(
        db,
        actor_user_id=actor_id,
        actor_role=actor_role,
        action="tenant.update",
        resource_type="tenant",
        resource_id=str(tenant.id),
        tenant_id=tenant.id,
        before=before,
        after=tenant_to_dict(tenant),
    )
    await db.commit()
    await db.refresh(tenant)
    return tenant_to_dict(tenant)


async def provision_tenant(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    actor_id: UUID,
    actor_role: str,
    admin_password: str | None = None,
) -> Dict[str, Any]:
    from Services.analytics_helpers import ensure_catalog_seeded
    from Services.platform_feature_service import apply_plan_features_to_tenant
    from Services.platform_subscription_service import ensure_subscription_for_tenant

    tenant = await resolve_tenant(db, tenant_id)
    if tenant.status not in ("draft", "provisioning_failed", "provisioning"):
        raise ApiError(422, f"Cannot provision tenant in status {tenant.status}")

    job = await start_job(db, "tenant.provision")
    tenant.status = "provisioning"
    apply_update_audit(tenant, actor_id)
    await db.flush()

    try:
        if not tenant.admin_email:
            raise ApiError(422, "adminEmail is required to provision")

        # Plan / subscription
        await ensure_subscription_for_tenant(
            db, tenant, actor_id=actor_id, actor_role=actor_role
        )

        # Society
        if not tenant.society_id:
            society = Society(
                name=tenant.name,
                display_name=tenant.display_name or tenant.name,
                short_name=tenant.code[:50],
                description=f"Provisioned tenant {tenant.code}",
                code=tenant.code,
                email=tenant.admin_email,
                phone="9000000000",
                contact_person="Society Admin",
                contact_email=tenant.admin_email,
                contact_phone="9000000000",
                address_line1="To be updated",
                city="Pune",
                state="Maharashtra",
                pincode="411001",
                country="IN",
                settings={
                    **DEFAULT_SOCIETY_SETTINGS,
                    "timezone": tenant.timezone,
                },
                is_active=True,
            )
            apply_create_audit(society, actor_id)
            db.add(society)
            await db.flush()
            tenant.society_id = society.id
        else:
            result = await db.execute(
                select(Society).where(Society.id == tenant.society_id)
            )
            society = result.scalar_one()

        # Bootstrap admin
        admin_q = await db.execute(
            select(User).where(
                User.society_id == society.id,
                User.role == "admin",
                User.email == tenant.admin_email,
            )
        )
        admin = admin_q.scalar_one_or_none()
        temp_password = admin_password or generate_temp_password()
        if not admin:
            # unique phone — derive from tenant code hash
            phone_suffix = abs(hash(tenant.code)) % 100000000
            phone = f"9{phone_suffix:09d}"[:10]
            existing_phone = await db.execute(select(User).where(User.phone == phone))
            if existing_phone.scalar_one_or_none():
                phone = f"8{phone_suffix:09d}"[:10]
            existing_email = await db.execute(
                select(User).where(User.email == tenant.admin_email)
            )
            if existing_email.scalar_one_or_none():
                raise ApiError(409, "Admin email already registered")
            admin = User(
                name=f"{tenant.name} Admin",
                email=tenant.admin_email,
                phone=phone,
                password=hash_password(temp_password),
                role="admin",
                society_id=society.id,
                is_active=True,
                is_verified=True,
                designation="Society Administrator",
            )
            db.add(admin)
            await db.flush()

        # Notification templates (minimal payment_reminder like seed)
        from Models.notification import NotificationTemplate

        tpl_q = await db.execute(
            select(NotificationTemplate).where(
                NotificationTemplate.society_id == society.id,
                NotificationTemplate.code == "payment_reminder",
            )
        )
        if not tpl_q.scalar_one_or_none():
            db.add(
                NotificationTemplate(
                    society_id=society.id,
                    code="payment_reminder",
                    name="Payment Reminder",
                    category="billing",
                    channel="in_app",
                    subject_template="Payment reminder",
                    body_template="Dear {{name}}, please pay your outstanding dues.",
                    is_system=True,
                    is_active=True,
                )
            )

        await ensure_catalog_seeded(db, society.id)
        await apply_plan_features_to_tenant(db, tenant, actor_id=actor_id)

        tenant.status = "active"
        tenant.provisioned_at = utcnow()
        apply_update_audit(tenant, actor_id)

        await write_audit(
            db,
            actor_user_id=actor_id,
            actor_role=actor_role,
            action="tenant.provision",
            resource_type="tenant",
            resource_id=str(tenant.id),
            tenant_id=tenant.id,
            after=tenant_to_dict(tenant),
        )
        await finish_job(
            db,
            job,
            status="succeeded",
            result={"tenantId": str(tenant.id), "societyId": str(society.id)},
        )
        emit_platform_event(
            "TenantProvisioned",
            tenant_id=tenant.id,
            society_id=society.id,
            entity_type="tenant",
            entity_id=tenant.id,
            actor_id=actor_id,
        )
        emit_platform_event(
            "TenantActivated",
            tenant_id=tenant.id,
            society_id=society.id,
            entity_type="tenant",
            entity_id=tenant.id,
            actor_id=actor_id,
        )
        await db.commit()
        await db.refresh(tenant)
        data = tenant_to_dict(tenant)
        data["bootstrap"] = {
            "adminEmail": tenant.admin_email,
            "tempPasswordIssued": admin_password is None,
            "tempPassword": temp_password if admin_password is None else None,
        }
        return data
    except Exception as exc:
        try:
            await db.rollback()
        except Exception:
            pass
        try:
            tenant = await resolve_tenant(db, tenant_id)
            tenant.status = "provisioning_failed"
            apply_update_audit(tenant, actor_id)
            job_fail = await start_job(db, "tenant.provision")
            await finish_job(db, job_fail, status="failed", error=str(exc)[:2000])
            await db.commit()
        except Exception:
            pass
        if isinstance(exc, ApiError):
            raise
        raise ApiError(500, f"Provisioning failed: {exc}") from exc


async def _set_status(
    db: AsyncSession,
    tenant_id: UUID,
    status: str,
    *,
    actor_id: UUID,
    actor_role: str,
    event: str,
    action: str,
) -> Dict[str, Any]:
    tenant = await resolve_tenant(db, tenant_id)
    before = tenant_to_dict(tenant)
    tenant.status = status
    now = utcnow()
    if status == "suspended":
        tenant.suspended_at = now
    if status == "active":
        tenant.suspended_at = None
    if status == "archived":
        tenant.archived_at = now
        tenant.is_active = False
    if status == "pending_delete":
        tenant.delete_after = now + timedelta(days=30)
        tenant.is_active = False
    apply_update_audit(tenant, actor_id)
    await write_audit(
        db,
        actor_user_id=actor_id,
        actor_role=actor_role,
        action=action,
        resource_type="tenant",
        resource_id=str(tenant.id),
        tenant_id=tenant.id,
        before=before,
        after=tenant_to_dict(tenant),
    )
    emit_platform_event(
        event,
        tenant_id=tenant.id,
        society_id=tenant.society_id,
        entity_type="tenant",
        entity_id=tenant.id,
        actor_id=actor_id,
    )
    await db.commit()
    await db.refresh(tenant)
    return tenant_to_dict(tenant)


async def activate_tenant(db, tenant_id, *, actor_id, actor_role):
    tenant = await resolve_tenant(db, tenant_id)
    if tenant.status not in ("draft", "suspended", "provisioning_failed"):
        if tenant.status == "active":
            return tenant_to_dict(tenant)
        raise ApiError(422, f"Cannot activate from {tenant.status}")
    if not tenant.society_id:
        raise ApiError(422, "Provision tenant before activating")
    return await _set_status(
        db,
        tenant_id,
        "active",
        actor_id=actor_id,
        actor_role=actor_role,
        event="TenantActivated",
        action="tenant.activate",
    )


async def suspend_tenant(db, tenant_id, *, actor_id, actor_role):
    return await _set_status(
        db,
        tenant_id,
        "suspended",
        actor_id=actor_id,
        actor_role=actor_role,
        event="TenantSuspended",
        action="tenant.suspend",
    )


async def reactivate_tenant(db, tenant_id, *, actor_id, actor_role):
    tenant = await resolve_tenant(db, tenant_id)
    if tenant.status != "suspended":
        raise ApiError(422, "Only suspended tenants can be reactivated")
    return await _set_status(
        db,
        tenant_id,
        "active",
        actor_id=actor_id,
        actor_role=actor_role,
        event="TenantReactivated",
        action="tenant.reactivate",
    )


async def archive_tenant(db, tenant_id, *, actor_id, actor_role):
    return await _set_status(
        db,
        tenant_id,
        "archived",
        actor_id=actor_id,
        actor_role=actor_role,
        event="TenantArchived",
        action="tenant.archive",
    )


async def delete_tenant(db, tenant_id, *, actor_id, actor_role):
    return await _set_status(
        db,
        tenant_id,
        "pending_delete",
        actor_id=actor_id,
        actor_role=actor_role,
        event="TenantDeleteScheduled",
        action="tenant.delete_schedule",
    )


async def clone_demo_tenant(
    db: AsyncSession,
    source_tenant_id: UUID,
    *,
    new_code: str,
    new_name: str,
    admin_email: str,
    actor_id: UUID,
    actor_role: str,
) -> Dict[str, Any]:
    source = await resolve_tenant(db, source_tenant_id)
    body = {
        "name": new_name,
        "code": new_code,
        "adminEmail": admin_email,
        "planCode": source.plan_code or "trial",
        "region": source.region,
        "timezone": source.timezone,
        "notes": f"Cloned from {source.code}",
    }
    created = await create_tenant(db, body, actor_id=actor_id, actor_role=actor_role)
    tenant_id = UUID(created["id"])

    # Optional structure clone (buildings only codes — anonymized, no PII)
    if source.society_id:
        buildings = (
            await db.execute(
                select(Building).where(
                    Building.society_id == source.society_id,
                    Building.is_active.is_(True),
                )
            )
        ).scalars().all()
        # provision first so society exists
        provisioned = await provision_tenant(
            db, tenant_id, actor_id=actor_id, actor_role=actor_role
        )
        tenant = await resolve_tenant(db, tenant_id)
        for b in buildings[:3]:
            clone = Building(
                society_id=tenant.society_id,
                name=f"Demo {b.name}",
                display_name=f"Demo {b.display_name or b.name}",
                code=f"D{b.code}"[:32],
                building_type=getattr(b, "building_type", "tower") or "tower",
                status="operational",
                total_floors=getattr(b, "total_floors", 1) or 1,
                metadata_json={},
                is_active=True,
            )
            apply_create_audit(clone, actor_id)
            db.add(clone)
        await db.commit()
        emit_platform_event(
            "DemoTenantCloned",
            tenant_id=tenant_id,
            society_id=tenant.society_id,
            entity_type="tenant",
            entity_id=tenant_id,
            actor_id=actor_id,
            payload={"sourceTenantId": str(source_tenant_id)},
        )
        return await get_tenant_detail(db, tenant_id)

    return await provision_tenant(
        db, tenant_id, actor_id=actor_id, actor_role=actor_role
    )


async def get_tenant_detail(db: AsyncSession, tenant_id: UUID) -> Dict[str, Any]:
    from Services.platform_feature_service import resolve_features_for_tenant
    from Services.platform_license_service import get_active_license
    from Services.platform_subscription_service import get_active_subscription

    tenant = await resolve_tenant(db, tenant_id)
    data = tenant_to_dict(tenant)
    data["subscription"] = await get_active_subscription(db, tenant_id)
    data["license"] = await get_active_license(db, tenant_id)
    data["features"] = await resolve_features_for_tenant(db, tenant)
    data["usage"] = await get_tenant_usage(db, tenant_id)
    data["health"] = await get_tenant_health(db, tenant_id)
    return data


async def get_tenant_usage(db: AsyncSession, tenant_id: UUID) -> Dict[str, Any]:
    tenant = await resolve_tenant(db, tenant_id)
    if not tenant.society_id:
        return {
            "users": 0,
            "buildings": 0,
            "flats": 0,
            "complaints": 0,
            "visitors": 0,
            "parkingSlots": 0,
            "bookings": 0,
        }
    sid = tenant.society_id

    async def _count(model, society_col="society_id"):
        col = getattr(model, society_col)
        return int(
            (await db.execute(select(func.count()).select_from(model).where(col == sid))).scalar()
            or 0
        )

    return {
        "users": await _count(User),
        "buildings": await _count(Building),
        "flats": await _count(Flat),
        "complaints": await _count(Complaint),
        "visitors": await _count(Visit),
        "parkingSlots": await _count(ParkingSlot),
        "bookings": await _count(FacilityBooking),
        "asOf": iso(utcnow()),
    }


async def get_tenant_health(db: AsyncSession, tenant_id: UUID) -> Dict[str, Any]:
    tenant = await resolve_tenant(db, tenant_id)
    checks = {
        "tenantStatus": tenant.status,
        "hasSociety": bool(tenant.society_id),
        "isolationMode": tenant.isolation_mode,
    }
    healthy = tenant.status == "active" and bool(tenant.society_id)
    return {
        "status": "healthy" if healthy else "degraded",
        "checks": checks,
        "asOf": iso(utcnow()),
    }
