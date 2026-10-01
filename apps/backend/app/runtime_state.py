"""In-memory runtime state that can change without restarting the backend.

Phase 1's config loader is cached from config/default.yaml + env vars and
is not meant to be mutated at runtime. Network mode, however, needs to be
switchable live from the UI (e.g. to allow a one-off model download) — this
module holds that single piece of mutable state. It does NOT persist across
restarts; real persisted settings land in Phase 8 (Settings panel + a
writable config store).
"""
from __future__ import annotations

import logging
import threading

from .config import get_config

logger = logging.getLogger("cicibyte.runtime_state")

VALID_MODES = ("offline", "lan", "internet")

_lock = threading.Lock()
_network_mode: str | None = None


def get_network_mode() -> str:
    global _network_mode
    with _lock:
        if _network_mode is None:
            _network_mode = get_config().get("network", {}).get("mode", "offline")
        return _network_mode


def set_network_mode(mode: str) -> str:
    global _network_mode
    if mode not in VALID_MODES:
        raise ValueError(f"Invalid network mode '{mode}', must be one of {VALID_MODES}")
    with _lock:
        _network_mode = mode
    logger.info("Network mode changed", extra={"extra_fields": {"network_mode": mode}})
    return mode
