from __future__ import annotations

from fastapi import APIRouter

from ..config import get_config

router = APIRouter(prefix="/api", tags=["config"])

# Keys that are safe to expose to the frontend. Nothing secret lives in
# config/default.yaml today (Phase 10 adds the secret store, which never
# goes through this endpoint).
_EXPOSED_SECTIONS = ("app", "network", "autonomy")


@router.get("/config")
def get_public_config() -> dict:
    config = get_config()
    return {section: config.get(section, {}) for section in _EXPOSED_SECTIONS}
