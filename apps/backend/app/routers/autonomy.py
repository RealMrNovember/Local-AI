from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..runtime_state import VALID_AUTONOMY_MODES, get_autonomy_mode, set_autonomy_mode

router = APIRouter(prefix="/api/autonomy", tags=["autonomy"])


class SetModeRequest(BaseModel):
    mode: str


@router.get("/mode")
def get_mode() -> dict:
    return {"mode": get_autonomy_mode(), "valid_modes": list(VALID_AUTONOMY_MODES)}


@router.put("/mode")
def put_mode(body: SetModeRequest) -> dict:
    try:
        mode = set_autonomy_mode(body.mode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"mode": mode}
