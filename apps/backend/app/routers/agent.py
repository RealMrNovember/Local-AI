"""Agent run REST + WebSocket endpoints (ARCHITECTURE.md Sections 6/8).

POST /api/agent/runs            create + immediately start a run
GET  /api/agent/runs            list recent runs
GET  /api/agent/runs/{id}       run detail + steps
POST /api/agent/runs/{id}/stop  kill switch for one run
POST /api/agent/runs/{id}/resume
POST /api/agent/runs/{id}/discard
POST /api/agent/stop-all        global kill switch (product brief Section 15/45)
WS   /ws/agent/{id}             live step/run updates (Live Agent View)
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from ..agent.manager import get_agent_manager

router = APIRouter(prefix="/api/agent", tags=["agent"])


class CreateRunRequest(BaseModel):
    goal: str
    steps: list[dict] | None = None  # Phase 3: stub_echo/stub_sleep only — see planner.py


@router.post("/runs")
async def create_run(body: CreateRunRequest):
    manager = get_agent_manager()
    try:
        return await manager.create_and_start(body.goal, body.steps)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/runs")
async def list_runs(limit: int = 50):
    manager = get_agent_manager()
    runs = await manager.list_runs(limit)
    active = set(manager.active_run_ids())
    for r in runs:
        r["is_active"] = r["id"] in active
    return {"runs": runs}


@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    manager = get_agent_manager()
    detail = await manager.get_run_detail(run_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return detail


@router.post("/runs/{run_id}/stop")
async def stop_run(run_id: str):
    manager = get_agent_manager()
    stopped = await manager.stop_run(run_id)
    if not stopped:
        raise HTTPException(status_code=409, detail="Run is not active")
    return {"stopped": True}


@router.post("/runs/{run_id}/resume")
async def resume_run(run_id: str):
    manager = get_agent_manager()
    try:
        return await manager.resume_run(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/runs/{run_id}/discard")
async def discard_run(run_id: str):
    manager = get_agent_manager()
    try:
        return await manager.discard_run(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/stop-all")
async def stop_all():
    manager = get_agent_manager()
    count = await manager.stop_all()
    return {"stopped_count": count}


ws_router = APIRouter(tags=["agent"])


@ws_router.websocket("/ws/agent/{run_id}")
async def agent_ws(websocket: WebSocket, run_id: str) -> None:
    manager = get_agent_manager()
    detail = await manager.get_run_detail(run_id)
    if detail is None:
        await websocket.close(code=4404)
        return

    await websocket.accept()
    await websocket.send_json({"type": "snapshot", "run": detail["run"], "steps": detail["steps"]})

    queue = manager.subscribe(run_id)
    try:
        while True:
            event = await queue.get()
            await websocket.send_json(event)
            if event["type"] == "run_update" and event["run"]["status"] not in ("pending", "running"):
                break
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        manager.unsubscribe(run_id, queue)
