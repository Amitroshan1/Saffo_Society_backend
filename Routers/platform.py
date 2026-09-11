"""Platform control-plane routes — /api/v1/platform/*."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from Constants.constants import UserRole
from Database.session import get_db
from Dependencies.auth import CurrentUser, get_current_user
from Dependencies.list_query import get_list_query
from Dependencies.platform_auth import (
    require_impersonate,
    require_platform_read,
    require_platform_write,
    require_super_admin,
)
from Schemas.common import ListQueryParams
from Schemas.platform import (
    AnnouncementCreate,
    AssignPlanRequest,
    CloneDemoRequest,
    FeatureFlagUpsert,
    ImpersonateRequest,
    LicenseIssueRequest,
    MaintenanceRequest,
    PlanUpsert,
    PlatformUserCreate,
    PlatformUserUpdate,
    SettingsPatch,
    TenantCreate,
    TenantFlagsRequest,
    TenantUpdate,
)
from Services import (
    platform_announcement_service as announcement_svc,
)
from Services import platform_dashboard_service as dashboard_svc
from Services import platform_feature_service as feature_svc
from Services import platform_impersonation_service as impersonation_svc
from Services import platform_license_service as license_svc
from Services import platform_settings_service as settings_svc
from Services import platform_subscription_service as subscription_svc
from Services import platform_tenant_service as tenant_svc
from Services import platform_user_service as user_svc
from Utils.responses import success_response

router = APIRouter(prefix="/api/v1/platform", tags=["platform"])


# ── Dashboard / health / analytics / jobs / audit ───────────────────────────


@router.get("/dashboard")
async def platform_dashboard(
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_platform_read),
):
    data = await dashboard_svc.get_platform_dashboard(db)
    return success_response(200, "Platform dashboard", data)


@router.get("/health")
async def platform_health(
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_platform_read),
):
    data = await dashboard_svc.get_platform_health(db)
    return success_response(200, "Platform health", data)


@router.get("/analytics/{key}")
async def platform_analytics(
    key: str,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_platform_read),
):
    data = await dashboard_svc.get_platform_analytics(db, key)
    return success_response(200, "Platform analytics", data)


@router.post("/metrics/rollup")
async def rollup_metrics(
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_platform_write),
):
    data = await dashboard_svc.rollup_platform_metrics(db)
    return success_response(200, "Metrics rolled up", data)


@router.get("/jobs")
async def list_jobs(
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_platform_read),
):
    data = {"items": await dashboard_svc.list_job_runs(db)}
    return success_response(200, "Job runs", data)


@router.get("/audit-logs")
async def audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100, alias="pageSize"),
    action: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_platform_read),
):
    data = await dashboard_svc.list_audit_logs(
        db, page=page, page_size=page_size, action=action
    )
    return success_response(200, "Audit logs", data)


# ── Tenants ─────────────────────────────────────────────────────────────────


@router.get("/tenants")
async def list_tenants(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    query: ListQueryParams = Depends(get_list_query),
    _: CurrentUser = Depends(require_platform_read),
):
    data = await tenant_svc.list_tenants(db, query, status=status)
    return success_response(200, "Tenants fetched", data)


@router.post("/tenants")
async def create_tenant(
    body: TenantCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_platform_write),
):
    data = await tenant_svc.create_tenant(
        db,
        body.model_dump(exclude_none=True),
        actor_id=current.user_id,
        actor_role=current.role,
    )
    return success_response(201, "Tenant created", data)


@router.get("/tenants/{tenant_id}")
async def get_tenant(
    tenant_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_platform_read),
):
    data = await tenant_svc.get_tenant_detail(db, tenant_id)
    return success_response(200, "Tenant fetched", data)


@router.patch("/tenants/{tenant_id}")
async def update_tenant(
    tenant_id: UUID,
    body: TenantUpdate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_platform_write),
):
    data = await tenant_svc.update_tenant(
        db,
        tenant_id,
        body.model_dump(exclude_none=True),
        actor_id=current.user_id,
        actor_role=current.role,
    )
    return success_response(200, "Tenant updated", data)


@router.post("/tenants/{tenant_id}/provision")
async def provision_tenant(
    tenant_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_platform_write),
):
    data = await tenant_svc.provision_tenant(
        db, tenant_id, actor_id=current.user_id, actor_role=current.role
    )
    return success_response(200, "Tenant provisioned", data)


@router.post("/tenants/{tenant_id}/activate")
async def activate_tenant(
    tenant_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_platform_write),
):
    data = await tenant_svc.activate_tenant(
        db, tenant_id, actor_id=current.user_id, actor_role=current.role
    )
    return success_response(200, "Tenant activated", data)


@router.post("/tenants/{tenant_id}/suspend")
async def suspend_tenant(
    tenant_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_platform_write),
):
    data = await tenant_svc.suspend_tenant(
        db, tenant_id, actor_id=current.user_id, actor_role=current.role
    )
    return success_response(200, "Tenant suspended", data)


@router.post("/tenants/{tenant_id}/reactivate")
async def reactivate_tenant(
    tenant_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_platform_write),
):
    data = await tenant_svc.reactivate_tenant(
        db, tenant_id, actor_id=current.user_id, actor_role=current.role
    )
    return success_response(200, "Tenant reactivated", data)


@router.post("/tenants/{tenant_id}/archive")
async def archive_tenant(
    tenant_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_platform_write),
):
    data = await tenant_svc.archive_tenant(
        db, tenant_id, actor_id=current.user_id, actor_role=current.role
    )
    return success_response(200, "Tenant archived", data)


@router.post("/tenants/{tenant_id}/delete")
async def delete_tenant(
    tenant_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_super_admin),
):
    data = await tenant_svc.delete_tenant(
        db, tenant_id, actor_id=current.user_id, actor_role=current.role
    )
    return success_response(200, "Tenant scheduled for deletion", data)


@router.post("/tenants/{tenant_id}/clone-demo")
async def clone_demo(
    tenant_id: UUID,
    body: CloneDemoRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_platform_write),
):
    data = await tenant_svc.clone_demo_tenant(
        db,
        tenant_id,
        new_code=body.code,
        new_name=body.name,
        admin_email=str(body.adminEmail),
        actor_id=current.user_id,
        actor_role=current.role,
    )
    return success_response(201, "Demo tenant cloned", data)


@router.get("/tenants/{tenant_id}/health")
async def tenant_health(
    tenant_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_platform_read),
):
    data = await tenant_svc.get_tenant_health(db, tenant_id)
    return success_response(200, "Tenant health", data)


@router.get("/tenants/{tenant_id}/usage")
async def tenant_usage(
    tenant_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_platform_read),
):
    data = await tenant_svc.get_tenant_usage(db, tenant_id)
    return success_response(200, "Tenant usage", data)


@router.post("/tenants/{tenant_id}/impersonate")
async def impersonate(
    tenant_id: UUID,
    body: ImpersonateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_impersonate),
):
    data = await impersonation_svc.start_impersonation(
        db,
        tenant_id,
        actor_id=current.user_id,
        actor_role=current.role,
        reason=body.reason,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return success_response(200, "Impersonation started", data)


@router.post("/impersonation/{session_id}/end")
async def end_impersonation(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_impersonate),
):
    data = await impersonation_svc.end_impersonation(
        db, session_id, actor_id=current.user_id, actor_role=current.role
    )
    return success_response(200, "Impersonation ended", data)


@router.put("/tenants/{tenant_id}/feature-flags")
async def set_tenant_flags(
    tenant_id: UUID,
    body: TenantFlagsRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_platform_write),
):
    data = await feature_svc.set_tenant_overrides(
        db,
        tenant_id,
        [o.model_dump() for o in body.overrides],
        actor_id=current.user_id,
        actor_role=current.role,
    )
    return success_response(200, "Tenant feature flags updated", {"overrides": data})


# ── Plans / subscriptions / licenses ────────────────────────────────────────


@router.get("/plans")
async def list_plans(
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_platform_read),
):
    return success_response(200, "Plans", {"items": await subscription_svc.list_plans(db)})


@router.post("/plans")
async def upsert_plan(
    body: PlanUpsert,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_super_admin),
):
    data = await subscription_svc.upsert_plan(
        db,
        body.model_dump(exclude_none=True),
        actor_id=current.user_id,
        actor_role=current.role,
    )
    return success_response(200, "Plan saved", data)


@router.get("/subscriptions")
async def list_subscriptions(
    tenant_id: UUID | None = Query(None, alias="tenantId"),
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_platform_read),
):
    items = await subscription_svc.list_subscriptions(db, tenant_id=tenant_id)
    return success_response(200, "Subscriptions", {"items": items})


@router.post("/tenants/{tenant_id}/subscription")
async def assign_subscription(
    tenant_id: UUID,
    body: AssignPlanRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_platform_write),
):
    data = await subscription_svc.assign_plan(
        db,
        tenant_id,
        body.planCode,
        actor_id=current.user_id,
        actor_role=current.role,
    )
    return success_response(200, "Subscription assigned", data)


@router.post("/subscriptions/{subscription_id}/renew")
async def renew_subscription(
    subscription_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_platform_write),
):
    data = await subscription_svc.renew_subscription(
        db, subscription_id, actor_id=current.user_id, actor_role=current.role
    )
    return success_response(200, "Subscription renewed", data)


@router.post("/subscriptions/{subscription_id}/cancel")
async def cancel_subscription(
    subscription_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_platform_write),
):
    data = await subscription_svc.cancel_subscription(
        db, subscription_id, actor_id=current.user_id, actor_role=current.role
    )
    return success_response(200, "Subscription cancelled", data)


@router.get("/licenses")
async def list_licenses(
    tenant_id: UUID | None = Query(None, alias="tenantId"),
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_platform_read),
):
    items = await license_svc.list_licenses(db, tenant_id=tenant_id)
    return success_response(200, "Licenses", {"items": items})


@router.post("/tenants/{tenant_id}/licenses")
async def issue_license(
    tenant_id: UUID,
    body: LicenseIssueRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_platform_write),
):
    data = await license_svc.issue_license(
        db,
        tenant_id,
        body.model_dump(exclude_none=True),
        actor_id=current.user_id,
        actor_role=current.role,
    )
    return success_response(201, "License issued", data)


@router.post("/licenses/{license_id}/renew")
async def renew_license(
    license_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_platform_write),
):
    data = await license_svc.renew_license(
        db, license_id, actor_id=current.user_id, actor_role=current.role
    )
    return success_response(200, "License renewed", data)


@router.post("/licenses/{license_id}/deactivate")
async def deactivate_license(
    license_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_platform_write),
):
    data = await license_svc.deactivate_license(
        db, license_id, actor_id=current.user_id, actor_role=current.role
    )
    return success_response(200, "License deactivated", data)


# ── Feature flags / settings / maintenance ──────────────────────────────────


@router.get("/feature-flags")
async def list_flags(
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_platform_read),
):
    return success_response(200, "Feature flags", {"items": await feature_svc.list_flags(db)})


@router.post("/feature-flags")
async def upsert_flag(
    body: FeatureFlagUpsert,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_super_admin),
):
    data = await feature_svc.upsert_flag(
        db,
        body.model_dump(exclude_none=True),
        actor_id=current.user_id,
        actor_role=current.role,
    )
    return success_response(200, "Feature flag saved", data)


@router.get("/settings")
async def list_settings(
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_platform_read),
):
    return success_response(200, "Settings", {"items": await settings_svc.list_settings(db)})


@router.get("/settings/{group}")
async def get_settings(
    group: str,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_platform_read),
):
    data = await settings_svc.get_settings_group(db, group)
    return success_response(200, "Settings group", data)


@router.patch("/settings/{group}")
async def patch_settings(
    group: str,
    body: SettingsPatch,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_super_admin),
):
    data = await settings_svc.patch_settings_group(
        db,
        group,
        body.model_dump(exclude_none=True),
        actor_id=current.user_id,
        actor_role=current.role,
    )
    return success_response(200, "Settings updated", data)


@router.get("/maintenance-mode")
async def get_maintenance(
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_platform_read),
):
    return success_response(200, "Maintenance mode", await settings_svc.get_maintenance(db))


@router.post("/maintenance-mode")
async def set_maintenance(
    body: MaintenanceRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_super_admin),
):
    data = await settings_svc.set_maintenance(
        db,
        enabled=body.enabled,
        message=body.message,
        actor_id=current.user_id,
        actor_role=current.role,
    )
    return success_response(200, "Maintenance mode updated", data)


# ── Announcements ───────────────────────────────────────────────────────────


@router.get("/announcements")
async def list_announcements(
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_platform_read),
):
    return success_response(
        200, "Announcements", {"items": await announcement_svc.list_announcements(db)}
    )


@router.post("/announcements")
async def create_announcement(
    body: AnnouncementCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_platform_write),
):
    data = await announcement_svc.create_announcement(
        db,
        body.model_dump(exclude_none=True),
        actor_id=current.user_id,
        actor_role=current.role,
    )
    return success_response(201, "Announcement created", data)


@router.post("/announcements/{announcement_id}/send")
async def send_announcement(
    announcement_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_platform_write),
):
    data = await announcement_svc.send_announcement(
        db, announcement_id, actor_id=current.user_id, actor_role=current.role
    )
    return success_response(200, "Announcement sent", data)


# ── Platform users / roles ──────────────────────────────────────────────────


@router.get("/users")
async def list_platform_users(
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_platform_read),
):
    return success_response(
        200, "Platform users", {"items": await user_svc.list_platform_users(db)}
    )


@router.post("/users")
async def create_platform_user(
    body: PlatformUserCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_super_admin),
):
    data = await user_svc.create_platform_user(
        db,
        body.model_dump(exclude_none=True),
        actor_id=current.user_id,
        actor_role=current.role,
    )
    return success_response(201, "Platform user created", data)


@router.patch("/users/{user_id}")
async def update_platform_user(
    user_id: UUID,
    body: PlatformUserUpdate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_super_admin),
):
    data = await user_svc.update_platform_user(
        db,
        user_id,
        body.model_dump(exclude_none=True),
        actor_id=current.user_id,
        actor_role=current.role,
    )
    return success_response(200, "Platform user updated", data)


@router.get("/roles")
async def global_roles(
    _: CurrentUser = Depends(require_platform_read),
):
    return success_response(200, "Global roles", {"items": user_svc.global_roles_catalog()})


# ── Society-facing feature bootstrap ────────────────────────────────────────


@router.get("/me/features")
async def my_features(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    """Also exposed for society users to gate navigation."""
    if current.society_id:
        feats = await feature_svc.resolve_features_for_society(db, current.society_id)
    else:
        feats = {f["key"]: f["defaultEnabled"] for f in await feature_svc.list_flags(db)}
    return success_response(
        200,
        "Features",
        {
            "features": feats,
            "impersonating": current.is_impersonating,
            "impersonationSessionId": str(current.impersonation_session_id)
            if current.impersonation_session_id
            else None,
        },
    )


# Alias under /api/v1 for society clients
features_router = APIRouter(prefix="/api/v1", tags=["platform-features"])


@features_router.get("/me/features")
async def me_features_alias(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    return await my_features(db=db, current=current)
