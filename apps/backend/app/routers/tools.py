from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..runtime_state import get_autonomy_mode
from ..tools.manager import get_tool_manager
from ..tools.registry import load_registry

router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.get("/registry")
async def get_registry() -> dict:
    return {"tools": [t.to_dict() for t in load_registry()]}


class InvokeRequest(BaseModel):
    tool: str
    args: dict = {}


@router.post("/invoke")
async def invoke_tool(body: InvokeRequest):
    manager = get_tool_manager()
    try:
        return await manager.create_and_start(body.tool, body.args, requested_by="user", autonomy_mode=get_autonomy_mode())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/invocations")
async def list_invocations(limit: int = 100):
    manager = get_tool_manager()
    return {"invocations": await manager.list_invocations(limit)}


@router.get("/invocations/pending")
async def list_pending():
    manager = get_tool_manager()
    return {"pending": await manager.list_pending()}


@router.get("/invocations/{invocation_id}")
async def get_invocation(invocation_id: str):
    manager = get_tool_manager()
    invocation = await manager.get_invocation(invocation_id)
    if invocation is None:
        raise HTTPException(status_code=404, detail="Invocation not found")
    return invocation


@router.post("/invocations/{invocation_id}/approve")
async def approve_invocation(invocation_id: str):
    manager = get_tool_manager()
    try:
        return await manager.approve(invocation_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/invocations/{invocation_id}/deny")
async def deny_invocation(invocation_id: str):
    manager = get_tool_manager()
    try:
        return await manager.deny(invocation_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/invocations/{invocation_id}/cancel")
async def cancel_invocation(invocation_id: str):
    manager = get_tool_manager()
    cancelled = await manager.cancel(invocation_id)
    if not cancelled:
        raise HTTPException(status_code=409, detail="Invocation is not active")
    return {"cancelled": True}
