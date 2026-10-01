from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..runtime_state import VALID_MODES, get_network_mode, set_network_mode

router = APIRouter(prefix="/api/network", tags=["network"])


class SetModeRequest(BaseModel):
    mode: str


@router.get("/mode")
def get_mode() -> dict:
    return {"mode": get_network_mode(), "valid_modes": list(VALID_MODES)}


@router.put("/mode")
def put_mode(body: SetModeRequest) -> dict:
    try:
        mode = set_network_mode(body.mode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"mode": mode}
