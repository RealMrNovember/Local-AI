from __future__ import annotations

from fastapi import APIRouter

from .. import __version__
from ..config import get_config
from ..hardware import profile_hardware
from ..runtime_state import get_network_mode

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health() -> dict:
    config = get_config()
    hw = profile_hardware()
    return {
        "status": "ok",
        "app_name": config.get("app", {}).get("name", "CiciByte AI"),
        "version": __version__,
        "network_mode": get_network_mode(),
        "hardware": hw.to_dict(),
    }
