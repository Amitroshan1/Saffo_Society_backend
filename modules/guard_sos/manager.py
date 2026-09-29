import asyncio

from fastapi import WebSocket


class SocietyConnectionManager:
    """In-memory rooms keyed by society. One API process only."""

    def __init__(self) -> None:
        self._rooms: dict[int, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, society_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._rooms.setdefault(society_id, set()).add(websocket)

    async def disconnect(self, society_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            room = self._rooms.get(society_id)
            if not room:
                return
            room.discard(websocket)
            if not room:
                self._rooms.pop(society_id, None)

    async def broadcast(self, society_id: int, payload: dict) -> None:
        async with self._lock:
            sockets = list(self._rooms.get(society_id, ()))
        dead: list[WebSocket] = []
        for websocket in sockets:
            try:
                await websocket.send_json(payload)
            except Exception:
                dead.append(websocket)
        for websocket in dead:
            await self.disconnect(society_id, websocket)


manager = SocietyConnectionManager()


async def broadcast_sos_created(society_id: int, data: dict) -> None:
    """Resident module calls this after it commits a new active SOS."""
    await manager.broadcast(society_id, {"type": "sos.created", "data": data})


async def broadcast_sos_resolved(society_id: int, data: dict) -> None:
    await manager.broadcast(society_id, {"type": "sos.resolved", "data": data})
