"""ToolManager — ties the Tool Registry, Permission Engine, and Execution
Engine together (ARCHITECTURE.md Section 7.2's "Universal Tool Adapter").

Two call shapes, both going through the exact same permission/execution
path (no separate "agent path" vs "human path" logic):

- `invoke_and_wait(...)`: used by the Agent's `tool_call` step — creates
  the invocation and awaits it to completion IN the caller's own task, so
  a kill-switch cancellation of the agent run directly cancels the tool
  run (and, for subprocess tools, kills the real OS process — see
  execution.py).
- `create_and_start(...)` / background task: used by the standalone
  `POST /api/tools/invoke` HTTP endpoint, which must return immediately
  rather than block an HTTP request on a human confirmation.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import db
from .execution import (
    PathNotAllowed,
    ToolExecutionError,
    _resolve_safe_path,
    fs_delete,
    fs_list,
    fs_read,
    fs_write,
    run_subprocess,
)
from .permission import needs_confirmation
from .registry import ToolDefinition, get_tool

logger = logging.getLogger("cicibyte.tools.manager")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ToolDenied(Exception):
    pass


class ToolManager:
    def __init__(
        self,
        repo_root: Path,
        workspace_dir: Path,
        filesystem_allowed_roots: list[str],
        subprocess_timeout_s: float,
    ) -> None:
        self.repo_root = repo_root
        self.workspace_dir = workspace_dir
        self.filesystem_allowed_roots = filesystem_allowed_roots
        self.subprocess_timeout_s = subprocess_timeout_s
        self._active_tasks: dict[str, asyncio.Task] = {}
        self._decision_events: dict[str, asyncio.Event] = {}

    # --- queries -------------------------------------------------------------

    async def get_invocation(self, invocation_id: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(db.get_invocation, invocation_id)

    async def list_invocations(self, limit: int = 100) -> list[dict[str, Any]]:
        return await asyncio.to_thread(db.list_invocations, limit)

    async def list_pending(self) -> list[dict[str, Any]]:
        return await asyncio.to_thread(db.list_pending_confirmations)

    def is_active(self, invocation_id: str) -> bool:
        task = self._active_tasks.get(invocation_id)
        return task is not None and not task.done()

    # --- entry points ----------------------------------------------------------

    async def invoke_and_wait(
        self,
        tool_name: str,
        args: dict[str, Any],
        requested_by: str,
        autonomy_mode: str,
        run_id: str | None = None,
        step_id: str | None = None,
    ) -> dict[str, Any]:
        """Run inline in the caller's task — used by the agent's tool_call
        step so kill-switch cancellation propagates correctly."""
        invocation = await self._create(tool_name, args, requested_by, autonomy_mode, run_id, step_id)
        return await self._run(invocation["id"])

    async def create_and_start(
        self,
        tool_name: str,
        args: dict[str, Any],
        requested_by: str,
        autonomy_mode: str,
    ) -> dict[str, Any]:
        """Create the invocation and run it as a background task — used by
        the standalone HTTP endpoint, which must not block on a human
        confirmation."""
        invocation = await self._create(tool_name, args, requested_by, autonomy_mode)
        task = asyncio.create_task(self._run(invocation["id"]))
        self._active_tasks[invocation["id"]] = task
        return invocation

    async def cancel_all(self) -> int:
        ids = [i for i, t in self._active_tasks.items() if not t.done()]
        for invocation_id in ids:
            await self.cancel(invocation_id)
        return len(ids)

    async def cancel(self, invocation_id: str) -> bool:
        task = self._active_tasks.get(invocation_id)
        if task is None or task.done():
            return False
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return True

    async def approve(self, invocation_id: str) -> dict[str, Any]:
        invocation = await self.get_invocation(invocation_id)
        if invocation is None:
            raise ValueError(f"No such invocation: {invocation_id}")
        if invocation["status"] != "pending_confirmation":
            raise ValueError(f"Invocation is '{invocation['status']}', not pending confirmation")
        await asyncio.to_thread(db.update_invocation, invocation_id, status="approved")
        self._decision_events.setdefault(invocation_id, asyncio.Event()).set()
        return await self.get_invocation(invocation_id)  # type: ignore[return-value]

    async def deny(self, invocation_id: str) -> dict[str, Any]:
        invocation = await self.get_invocation(invocation_id)
        if invocation is None:
            raise ValueError(f"No such invocation: {invocation_id}")
        if invocation["status"] != "pending_confirmation":
            raise ValueError(f"Invocation is '{invocation['status']}', not pending confirmation")
        await asyncio.to_thread(db.update_invocation, invocation_id, status="denied", finished_at=_now_iso())
        self._decision_events.setdefault(invocation_id, asyncio.Event()).set()
        return await self.get_invocation(invocation_id)  # type: ignore[return-value]

    # --- internals ---------------------------------------------------------------

    async def _create(
        self,
        tool_name: str,
        args: dict[str, Any],
        requested_by: str,
        autonomy_mode: str,
        run_id: str | None = None,
        step_id: str | None = None,
    ) -> dict[str, Any]:
        tool_def = get_tool(tool_name)
        if tool_def is None:
            raise ValueError(f"Unknown tool '{tool_name}' — not in config/tools.yaml")
        if not tool_def.enabled:
            raise ValueError(f"Tool '{tool_name}' is disabled in the registry")

        confirm = needs_confirmation(tool_def.risk_level, autonomy_mode, tool_def.requires_confirmation)
        status = "pending_confirmation" if confirm else "approved"
        return await asyncio.to_thread(
            db.create_invocation, tool_name, args, tool_def.risk_level, requested_by, status, run_id, step_id
        )

    async def _run(self, invocation_id: str) -> dict[str, Any]:
        invocation = await self.get_invocation(invocation_id)
        assert invocation is not None
        tool_def = get_tool(invocation["tool_name"])
        assert tool_def is not None

        try:
            if invocation["status"] == "pending_confirmation":
                event = self._decision_events.setdefault(invocation_id, asyncio.Event())
                await event.wait()
                invocation = await self.get_invocation(invocation_id)
                assert invocation is not None
                if invocation["status"] == "denied":
                    logger.info("Tool invocation denied", extra={"extra_fields": {"invocation_id": invocation_id}})
                    return invocation

            await asyncio.to_thread(db.update_invocation, invocation_id, status="running", started_at=_now_iso())

            result = await self._execute(tool_def, invocation["args"])

            await asyncio.to_thread(
                db.update_invocation,
                invocation_id,
                status="done",
                exit_code=result.get("exit_code"),
                stdout=result.get("stdout"),
                stderr=result.get("stderr"),
                output=result.get("output"),
                finished_at=_now_iso(),
            )
        except asyncio.CancelledError:
            await asyncio.to_thread(db.update_invocation, invocation_id, status="cancelled", finished_at=_now_iso())
            raise
        except (ToolExecutionError, PathNotAllowed) as exc:
            await asyncio.to_thread(
                db.update_invocation, invocation_id, status="failed", error=str(exc), finished_at=_now_iso()
            )
        except Exception as exc:  # noqa: BLE001 — surface any unexpected tool failure, never crash the manager
            logger.exception("Unexpected error running tool invocation")
            await asyncio.to_thread(
                db.update_invocation, invocation_id, status="failed", error=str(exc), finished_at=_now_iso()
            )
        finally:
            self._active_tasks.pop(invocation_id, None)
            self._decision_events.pop(invocation_id, None)

        final = await self.get_invocation(invocation_id)
        assert final is not None
        return final

    async def _execute(self, tool_def: ToolDefinition, args: dict[str, Any]) -> dict[str, Any]:
        if tool_def.kind == "subprocess":
            return await self._execute_subprocess(tool_def, args)
        if tool_def.kind == "filesystem":
            return await self._execute_filesystem(tool_def, args)
        raise ToolExecutionError(f"Unknown tool kind '{tool_def.kind}'")

    async def _execute_subprocess(self, tool_def: ToolDefinition, args: dict[str, Any]) -> dict[str, Any]:
        if tool_def.name == "python":
            if args.get("code"):
                arg_list = ["-c", args["code"]]
            elif args.get("script_path"):
                script = _resolve_safe_path(args["script_path"], self.filesystem_allowed_roots)
                arg_list = [str(script), *args.get("extra_args", [])]
            else:
                raise ToolExecutionError("python tool requires args.code or args.script_path")
            cwd = self.workspace_dir
        elif tool_def.name == "git":
            arg_list = args.get("args", [])
            if not arg_list:
                raise ToolExecutionError("git tool requires args.args (a list of git subcommand arguments)")
            cwd = self.repo_root
        else:
            raise ToolExecutionError(f"No subprocess handler for tool '{tool_def.name}'")

        timeout = args.get("timeout_s", self.subprocess_timeout_s)
        result = await run_subprocess(tool_def.executable, arg_list, cwd=cwd, timeout_s=timeout)
        return {"exit_code": result.exit_code, "stdout": result.stdout, "stderr": result.stderr, "output": None}

    async def _execute_filesystem(self, tool_def: ToolDefinition, args: dict[str, Any]) -> dict[str, Any]:
        path = args.get("path", ".")
        if tool_def.action == "list":
            output = await fs_list(path, self.filesystem_allowed_roots)
        elif tool_def.action == "read":
            output = {"content": await fs_read(path, self.filesystem_allowed_roots)}
        elif tool_def.action == "write":
            if "content" not in args:
                raise ToolExecutionError("filesystem_write requires args.content")
            output = await fs_write(path, args["content"], self.filesystem_allowed_roots)
        elif tool_def.action == "delete":
            output = await fs_delete(path, self.filesystem_allowed_roots)
        else:
            raise ToolExecutionError(f"Unknown filesystem action '{tool_def.action}'")
        return {"exit_code": 0, "stdout": None, "stderr": None, "output": output}


_tool_manager: ToolManager | None = None


def get_tool_manager() -> ToolManager:
    if _tool_manager is None:
        raise RuntimeError("ToolManager not initialized — call init_tool_manager() at startup")
    return _tool_manager


def init_tool_manager(
    repo_root: Path, workspace_dir: Path, filesystem_allowed_roots: list[str], subprocess_timeout_s: float
) -> ToolManager:
    global _tool_manager
    _tool_manager = ToolManager(repo_root, workspace_dir, filesystem_allowed_roots, subprocess_timeout_s)
    return _tool_manager
