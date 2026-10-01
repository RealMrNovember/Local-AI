"""Bounded retry policy for a single step (ARCHITECTURE.md Section 6).

Deliberately simple: fixed number of attempts, linear backoff. No
exponential/jitter tuning yet — add that only if a real failure mode
in Phase 4+ actually needs it.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

logger = logging.getLogger("cicibyte.agent.retry")


class StepFailed(Exception):
    def __init__(self, message: str, attempts: int):
        super().__init__(message)
        self.attempts = attempts


async def run_with_retry(
    fn: Callable[[], Awaitable[dict[str, Any]]],
    max_attempts: int,
    backoff_base_s: float,
    on_attempt_failed: Callable[[int, Exception], None] | None = None,
) -> dict[str, Any]:
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await fn()
        except asyncio.CancelledError:
            raise  # never swallow a kill-switch cancellation
        except Exception as exc:  # noqa: BLE001 — step bodies are untrusted/varied
            last_exc = exc
            if on_attempt_failed:
                on_attempt_failed(attempt, exc)
            if attempt < max_attempts:
                await asyncio.sleep(backoff_base_s * attempt)
    raise StepFailed(str(last_exc), max_attempts)
