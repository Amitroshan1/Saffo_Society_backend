"""Offline sync engine — pull/push, cursors, conflicts (server-wins default)."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from Models.integration import SyncCursor, SyncMutationLog
from Services.integration_helpers import emit_integration_event, iso, utcnow
from Utils.errors import ApiError

# Class B queueable mutations (design §5.2)
ALLOWED_MUTATIONS = {
    "notices": {"mark_read"},
    "visits": {"approve", "reject", "check_in_draft"},
    "preferences": {"update"},
    "complaints": {"draft_create"},
}

SERVER_AUTHORITATIVE = {"payments", "bills", "licenses"}


async def get_or_create_cursor(
    db: AsyncSession,
    *,
    user_id: UUID,
    device_id: Optional[UUID],
    society_id: Optional[UUID],
    collection: str,
) -> SyncCursor:
    q = select(SyncCursor).where(
        SyncCursor.user_id == user_id,
        SyncCursor.collection == collection,
    )
    if device_id:
        q = q.where(SyncCursor.device_id == device_id)
    else:
        q = q.where(SyncCursor.device_id.is_(None))
    row = (await db.execute(q)).scalar_one_or_none()
    if row:
        return row
    row = SyncCursor(
        user_id=user_id,
        device_id=device_id,
        society_id=society_id,
        collection=collection,
        cursor_value="0",
    )
    db.add(row)
    await db.flush()
    return row


async def sync_pull(
    db: AsyncSession,
    *,
    user_id: UUID,
    device_id: Optional[UUID],
    society_id: Optional[UUID],
    cursor: Optional[str] = None,
    collections: Optional[list[str]] = None,
) -> dict[str, Any]:
    emit_integration_event(
        "SyncStarted",
        society_id=society_id,
        actor_id=user_id,
        payload={"direction": "pull", "cursor": cursor},
    )
    cols = collections or ["notices", "visits", "preferences"]
    deltas: list[dict[str, Any]] = []
    next_cursors: dict[str, str] = {}

    for collection in cols:
        cur = await get_or_create_cursor(
            db,
            user_id=user_id,
            device_id=device_id,
            society_id=society_id,
            collection=collection,
        )
        # Delta source: accepted mutations after cursor (and tombstones placeholder)
        q = (
            select(SyncMutationLog)
            .where(
                SyncMutationLog.user_id == user_id,
                SyncMutationLog.collection == collection,
                SyncMutationLog.status.in_(["accepted", "applied", "conflict"]),
            )
            .order_by(SyncMutationLog.created_at.asc())
            .limit(100)
        )
        if society_id:
            q = q.where(SyncMutationLog.society_id == society_id)
        rows = (await db.execute(q)).scalars().all()
        start = cursor or cur.cursor_value
        for row in rows:
            gen = str(int(row.created_at.timestamp() * 1000))
            if gen <= (start or "0"):
                continue
            deltas.append(
                {
                    "collection": collection,
                    "mutationType": row.mutation_type,
                    "clientMutationId": row.client_mutation_id,
                    "entityId": row.entity_id,
                    "payload": row.payload_json or {},
                    "status": row.status,
                    "conflict": row.conflict_json,
                    "serverResult": row.server_result_json,
                    "generation": gen,
                }
            )
        if rows:
            last_gen = str(int(rows[-1].created_at.timestamp() * 1000))
            cur.cursor_value = last_gen
            cur.last_synced_at = utcnow()
            next_cursors[collection] = last_gen
        else:
            next_cursors[collection] = cur.cursor_value

    emit_integration_event(
        "SyncCompleted",
        society_id=society_id,
        actor_id=user_id,
        payload={"direction": "pull", "deltaCount": len(deltas)},
    )
    return {
        "deltas": deltas,
        "cursors": next_cursors,
        "serverTime": iso(utcnow()),
        "policy": "server_wins",
    }


async def sync_push(
    db: AsyncSession,
    *,
    user_id: UUID,
    device_id: Optional[UUID],
    society_id: Optional[UUID],
    mutations: list[dict[str, Any]],
) -> dict[str, Any]:
    emit_integration_event(
        "SyncStarted",
        society_id=society_id,
        actor_id=user_id,
        payload={"direction": "push", "count": len(mutations)},
    )
    results: list[dict[str, Any]] = []
    conflicts = 0

    for m in mutations:
        collection = (m.get("collection") or "").strip()
        mutation_type = (m.get("mutationType") or "").strip()
        client_id = (m.get("clientMutationId") or "").strip()
        if not collection or not mutation_type or not client_id:
            raise ApiError(400, "Each mutation requires collection, mutationType, clientMutationId")

        if collection in SERVER_AUTHORITATIVE:
            results.append(
                {
                    "clientMutationId": client_id,
                    "status": "rejected",
                    "reason": "server_authoritative",
                }
            )
            continue

        allowed = ALLOWED_MUTATIONS.get(collection, set())
        if mutation_type not in allowed:
            results.append(
                {
                    "clientMutationId": client_id,
                    "status": "rejected",
                    "reason": "mutation_not_allowed_offline",
                }
            )
            continue

        existing = (
            await db.execute(
                select(SyncMutationLog).where(
                    SyncMutationLog.user_id == user_id,
                    SyncMutationLog.client_mutation_id == client_id,
                )
            )
        ).scalar_one_or_none()
        if existing:
            results.append(
                {
                    "clientMutationId": client_id,
                    "status": existing.status,
                    "serverResult": existing.server_result_json,
                    "idempotent": True,
                }
            )
            continue

        # Optimistic accept — domain application is deferred to existing services by callers;
        # here we record outbox and apply server-wins if conflict marker present.
        conflict = None
        status = "accepted"
        server_result = {"applied": True, "authority": "server"}
        if m.get("baseVersion") and m.get("serverVersion") and m["baseVersion"] != m["serverVersion"]:
            status = "conflict"
            conflicts += 1
            conflict = {
                "strategy": "server_wins",
                "clientPayload": m.get("payload") or {},
                "message": "Server version differs; client must reload",
            }
            emit_integration_event(
                "SyncConflict",
                society_id=society_id,
                actor_id=user_id,
                payload={"collection": collection, "clientMutationId": client_id},
            )

        log = SyncMutationLog(
            user_id=user_id,
            device_id=device_id,
            society_id=society_id,
            collection=collection,
            mutation_type=mutation_type,
            client_mutation_id=client_id,
            entity_id=str(m.get("entityId")) if m.get("entityId") else None,
            payload_json=m.get("payload") or {},
            status=status,
            conflict_json=conflict,
            server_result_json=server_result if status == "accepted" else None,
        )
        db.add(log)
        await db.flush()
        results.append(
            {
                "clientMutationId": client_id,
                "status": status,
                "conflict": conflict,
                "serverResult": log.server_result_json,
            }
        )

    emit_integration_event(
        "SyncCompleted",
        society_id=society_id,
        actor_id=user_id,
        payload={"direction": "push", "results": len(results), "conflicts": conflicts},
    )
    return {"results": results, "conflicts": conflicts, "serverTime": iso(utcnow())}


async def sync_status(
    db: AsyncSession, *, user_id: UUID, device_id: Optional[UUID] = None
) -> dict[str, Any]:
    q = select(SyncCursor).where(SyncCursor.user_id == user_id)
    if device_id:
        q = q.where(SyncCursor.device_id == device_id)
    cursors = (await db.execute(q)).scalars().all()
    pending = (
        await db.execute(
            select(SyncMutationLog).where(
                SyncMutationLog.user_id == user_id,
                SyncMutationLog.status == "accepted",
            )
        )
    ).scalars().all()
    return {
        "cursors": [
            {
                "collection": c.collection,
                "cursor": c.cursor_value,
                "lastSyncedAt": iso(c.last_synced_at),
            }
            for c in cursors
        ],
        "pendingMutations": len(pending),
    }
