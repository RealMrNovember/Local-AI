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


async def tool_call(params: dict[str, Any]) -> dict[str, Any]:
    """Phase 4: a real step type that goes through the Tool Registry /
    Permission Engine / Execution Engine (app.tools.manager), instead of
    the Phase 3 stubs. Imported lazily to avoid a hard import cycle risk
    between app.agent and app.tools at module-load time."""
    from ..runtime_state import get_autonomy_mode
    from ..tools.manager import get_tool_manager

    tool_name = params.get("tool")
    if not tool_name:
        raise ValueError("tool_call step requires params.tool")
    tool_args = params.get("args", {})

    manager = get_tool_manager()
    invocation = await manager.invoke_and_wait(
        tool_name, tool_args, requested_by="agent", autonomy_mode=get_autonomy_mode()
    )

    if invocation["status"] == "denied":
        raise RuntimeError(f"Tool call '{tool_name}' was denied by the user")
    if invocation["status"] in ("failed", "cancelled"):
        raise RuntimeError(invocation.get("error") or f"Tool call '{tool_name}' did not complete ({invocation['status']})")

    return {
        "invocation_id": invocation["id"],
        "exit_code": invocation.get("exit_code"),
        "stdout": invocation.get("stdout"),
        "stderr": invocation.get("stderr"),
        "output": invocation.get("output"),
    }


EXECUTORS: dict[str, StepExecutor] = {
    "stub_echo": stub_echo,
    "stub_sleep": stub_sleep,
    "tool_call": tool_call,
}
