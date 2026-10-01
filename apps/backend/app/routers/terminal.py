"""Terminal REST + WebSocket endpoints (ARCHITECTURE.md Phase 5 / product
brief Section 27).

POST   /api/terminal/sessions              create a PTY session
GET    /api/terminal/sessions              list sessions (process manager view)
GET    /api/terminal/sessions/{id}/history scrollback buffer (used by "Send output to AI")
DELETE /api/terminal/sessions/{id}         kill the shell process
WS     /ws/terminal/{id}                   bidirectional I/O: client sends
                                            {"type":"input"|"resize", ...},
                                            server streams {"type":"output","data":...}
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from ..config import resolve_path
from ..terminal.manager import get_terminal_manager

router = APIRouter(prefix="/api/terminal", tags=["terminal"])


class CreateSessionRequest(BaseModel):
    shell: str = "powershell"
    cwd: str | None = None  # relative to repo root; defaults to workspace/


def _default_cwd() -> str:
    return str(resolve_path("workspace"))


@router.post("/sessions")
async def create_session(body: CreateSessionRequest):
    manager = get_terminal_manager()
    cwd = str(resolve_path(body.cwd)) if body.cwd else _default_cwd()
    try:
        session = await manager.create_session(body.shell, cwd)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    info = session.info()
    return info.__dict__


@router.get("/sessions")
async def list_sessions():
    manager = get_terminal_manager()
    return {"sessions": [s.__dict__ for s in manager.list_sessions()]}


@router.get("/sessions/{session_id}/history")
async def get_history(session_id: str):
    manager = get_terminal_manager()
    session = manager.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"history": session.get_history()}


@router.delete("/sessions/{session_id}")
async def close_session(session_id: str):
    manager = get_terminal_manager()
    closed = await manager.close_session(session_id)
    if not closed:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"closed": True}


ws_router = APIRouter(tags=["terminal"])


@ws_router.websocket("/ws/terminal/{session_id}")
async def terminal_ws(websocket: WebSocket, session_id: str) -> None:
    manager = get_terminal_manager()
    session = manager.get_session(session_id)
    if session is None:
        await websocket.close(code=4404)
        return

    await websocket.accept()
    await websocket.send_json({"type": "backlog", "data": session.get_history()})

    queue = session.subscribe()

    async def _pump_output() -> None:
        while True:
            chunk = await queue.get()
            if chunk is None:  # session closed
                await websocket.send_json({"type": "closed"})
                return
            await websocket.send_json({"type": "output", "data": chunk})

    pump_task = asyncio.create_task(_pump_output())
    try:
        while True:
            msg = await websocket.receive_json()
            if msg.get("type") == "input":
                await session.write(msg.get("data", ""))
            elif msg.get("type") == "resize":
                await session.resize(int(msg.get("cols", 80)), int(msg.get("rows", 24)))
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        pump_task.cancel()
        session.unsubscribe(queue)
