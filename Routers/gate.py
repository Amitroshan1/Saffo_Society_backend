"""Gate routes — /api/v1/gates."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from Database.session import get_db
from Dependencies.auth import CurrentUser, require_roles
from Dependencies.gate_list_query import get_gate_list_query
from Dependencies.shift_list_query import get_shift_list_query
from Schemas.gate import GateCreate, GateListQueryParams, GateUpdate
from Schemas.shift import ShiftListQueryParams
from Services import gate_service, shift_service
from Utils.responses import success_response

router = APIRouter(prefix="/api/v1/gates", tags=["gates"])


@router.get("/dashboard")
async def gate_ops_dashboard(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin", "guard")),
):
    data = await shift_service.gate_ops_dashboard(db, actor_society_id=current.society_id)
    return success_response(200, "Gate operations dashboard fetched", data)


@router.post("")
async def create_gate(
    body: GateCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await gate_service.create_gate(
        db, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(201, "Gate created successfully", data)


@router.get("")
async def list_gates(
    db: AsyncSession = Depends(get_db),
    query: GateListQueryParams = Depends(get_gate_list_query),
    current: CurrentUser = Depends(require_roles("admin", "guard")),
):
    data = await gate_service.list_gates(db, query, actor_society_id=current.society_id)
    return success_response(200, "Gates fetched", data)


@router.get("/{gate_id}")
async def get_gate(
    gate_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin", "guard")),
):
    data = await gate_service.get_gate(db, gate_id, actor_society_id=current.society_id)
    return success_response(200, "Gate fetched", data)


@router.patch("/{gate_id}")
async def update_gate(
    gate_id: UUID,
    body: GateUpdate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await gate_service.update_gate(
        db, gate_id, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Gate updated successfully", data)


@router.post("/{gate_id}/deactivate")
async def deactivate_gate(
    gate_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await gate_service.set_gate_active(
        db, gate_id, active=False, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, data.pop("message", "Gate deactivated"), data)


@router.post("/{gate_id}/activate")
async def activate_gate(
    gate_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await gate_service.set_gate_active(
        db, gate_id, active=True, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, data.pop("message", "Gate activated"), data)


@router.get("/{gate_id}/shifts")
async def gate_shifts(
    gate_id: UUID,
    db: AsyncSession = Depends(get_db),
    query: ShiftListQueryParams = Depends(get_shift_list_query),
    current: CurrentUser = Depends(require_roles("admin", "guard")),
):
    query.gate_id = gate_id
    data = await shift_service.list_shifts(db, query, actor_society_id=current.society_id)
    return success_response(200, "Gate shifts fetched", data)


@router.get("/{gate_id}/on-duty")
async def gate_on_duty(
    gate_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin", "guard")),
):
    data = await gate_service.gate_on_duty(db, gate_id, actor_society_id=current.society_id)
    return success_response(200, "On-duty staff fetched", data)
