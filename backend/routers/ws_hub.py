"""
Cortexium 2.0 — WebSocket Connection Manager & Event Hub
All backend routers push events here; all connected clients receive them.
This replaces the trivial echo implementation with a real broadcast hub.
"""
import json
import asyncio
import numpy as np
from datetime import datetime
from typing import List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/ws", tags=["websocket"])


class _NumpySafeEncoder(json.JSONEncoder):
    """
    Converts NumPy scalars and arrays to native Python types before JSON
    serialization. YOLO and DeepFace return float32/int64 values which
    Python's default encoder cannot handle.
    """
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return round(float(obj), 6)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


def _safe_dumps(obj: dict) -> str:
    return json.dumps(obj, cls=_NumpySafeEncoder)


class ConnectionManager:
    """Manages all active WebSocket client connections and broadcasts events."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"[WSHub] Client connected. Total: {len(self.active_connections)}")
        # Send a welcome handshake event
        await self._send_to(websocket, {
            "event_type": "system_handshake",
            "timestamp": datetime.utcnow().timestamp(),
            "data": {
                "message": "Connected to Cortexium 2.0 Event Hub",
                "clients": len(self.active_connections),
            }
        })

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        print(f"[WSHub] Client disconnected. Remaining: {len(self.active_connections)}")

    async def broadcast(self, event: dict):
        """Broadcast an event payload to ALL connected clients."""
        if not self.active_connections:
            return
        message = _safe_dumps(event)
        dead = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                dead.append(connection)
        for d in dead:
            self.disconnect(d)

    async def _send_to(self, websocket: WebSocket, event: dict):
        try:
            await websocket.send_text(_safe_dumps(event))
        except Exception:
            self.disconnect(websocket)

    @property
    def client_count(self) -> int:
        return len(self.active_connections)


# Module-level singleton used by all routers
connection_manager = ConnectionManager()


# ------------------------------------------------------------------
# WebSocket endpoint
# ------------------------------------------------------------------

@router.websocket("/events")
async def websocket_endpoint(websocket: WebSocket):
    """
    Primary WebSocket endpoint for the Cortexium event bus.
    Clients connect here to receive a real-time stream of CV, agent, and system events.
    """
    await connection_manager.connect(websocket)
    try:
        while True:
            # Keep the connection alive; handle any client-to-server messages
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                # Echo back acknowledgment with server timestamp
                await connection_manager._send_to(websocket, {
                    "event_type": "ack",
                    "timestamp": datetime.utcnow().timestamp(),
                    "original": msg,
                })
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
