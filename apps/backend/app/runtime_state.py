"""In-memory runtime state that can change without restarting the backend.

Phase 1's config loader is cached from config/default.yaml + env vars and
is not meant to be mutated at runtime. Network mode and Autonomy mode,
however, need to be switchable live from the UI — this module holds that
mutable state. It does NOT persist across restarts; real persisted
settings land in Phase 8 (Settings panel + a writable config store).
"""
from __future__ import annotations

import logging
import threading

from .config import get_config

logger = logging.getLogger("cicibyte.runtime_state")

VALID_NETWORK_MODES = ("offline", "lan", "internet")
VALID_AUTONOMY_MODES = ("SAFE", "AUTO", "FULL")

_lock = threading.Lock()
_network_mode: str | None = None
_autonomy_mode: str | None = None


def get_network_mode() -> str:
    global _network_mode
    with _lock:
        if _network_mode is None:
            _network_mode = get_config().get("network", {}).get("mode", "offline")
        return _network_mode


def set_network_mode(mode: str) -> str:
    global _network_mode
    if mode not in VALID_NETWORK_MODES:
        raise ValueError(f"Invalid network mode '{mode}', must be one of {VALID_NETWORK_MODES}")
    with _lock:
        _network_mode = mode
    logger.info("Network mode changed", extra={"extra_fields": {"network_mode": mode}})
    return mode


def get_autonomy_mode() -> str:
    global _autonomy_mode
    with _lock:
        if _autonomy_mode is None:
            _autonomy_mode = get_config().get("autonomy", {}).get("default_mode", "SAFE")
        return _autonomy_mode


def set_autonomy_mode(mode: str) -> str:
    global _autonomy_mode
    if mode not in VALID_AUTONOMY_MODES:
        raise ValueError(f"Invalid autonomy mode '{mode}', must be one of {VALID_AUTONOMY_MODES}")
    with _lock:
        _autonomy_mode = mode
    logger.info("Autonomy mode changed", extra={"extra_fields": {"autonomy_mode": mode}})
    return mode
