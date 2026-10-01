"""Step executors — Phase 3 stub set only.

These exist to exercise the agent loop, persistence, and kill switch
without depending on Phase 4's Tool Registry/Execution Engine. Nothing
here touches the filesystem, network, or a real subprocess — that's
exactly the point: it lets us prove the state machine is correct in
isolation before wiring it to anything with real side effects.
"""
from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

StepExecutor = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


async def stub_echo(params: dict[str, Any]) -> dict[str, Any]:
    text = params.get("text", "")
    await asyncio.sleep(0.2)  # simulate minimal work so steps are observable live
    return {"echoed": text}


async def stub_sleep(params: dict[str, Any]) -> dict[str, Any]:
    seconds = float(params.get("seconds", 1))
    if seconds < 0 or seconds > 300:
        raise ValueError("stub_sleep seconds must be between 0 and 300")
    await asyncio.sleep(seconds)  # a cancel() during this raises CancelledError, as intended
    return {"slept_seconds": seconds}


EXECUTORS: dict[str, StepExecutor] = {
    "stub_echo": stub_echo,
    "stub_sleep": stub_sleep,
}
