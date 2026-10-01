"""AgentManager — owns the Plan/Execute/Observe/Validate/Retry loop, the
in-memory task registry backing the kill switch, and live-update fan-out
for the UI's Live Agent View (ARCHITECTURE.md Sections 6/8).

Every DB call goes through `asyncio.to_thread` (db.py is plain sqlite3,
synchronous) so the event loop is never blocked by disk I/O.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from . import db
from .executors import EXECUTORS
from .planner import plan_steps
from .retry import StepFailed, run_with_retry

logger = logging.getLogger("cicibyte.agent.manager")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AgentManager:
    def __init__(self, max_step_retries: int, retry_backoff_base_s: float, max_steps_per_run: int) -> None:
        self.max_step_retries = max_step_retries
        self.retry_backoff_base_s = retry_backoff_base_s
        self.max_steps_per_run = max_steps_per_run
        self._active_tasks: dict[str, asyncio.Task] = {}
        self._subscribers: dict[str, list[asyncio.Queue]] = {}

    # --- live view pub/sub --------------------------------------------------

    def subscribe(self, run_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.setdefault(run_id, []).append(queue)
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue) -> None:
        subs = self._subscribers.get(run_id)
        if subs and queue in subs:
            subs.remove(queue)

    def _publish(self, run_id: str, event: dict[str, Any]) -> None:
        for queue in self._subscribers.get(run_id, []):
            queue.put_nowait(event)

    # --- queries -------------------------------------------------------------

    async def get_run_detail(self, run_id: str) -> dict[str, Any] | None:
        run = await asyncio.to_thread(db.get_run, run_id)
        if run is None:
            return None
        steps = await asyncio.to_thread(db.get_steps, run_id)
        return {"run": run, "steps": steps}

    async def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        return await asyncio.to_thread(db.list_runs, limit)

    def is_active(self, run_id: str) -> bool:
        task = self._active_tasks.get(run_id)
        return task is not None and not task.done()

    def active_run_ids(self) -> list[str]:
        return [rid for rid, t in self._active_tasks.items() if not t.done()]

    # --- lifecycle -------------------------------------------------------------

    async def create_and_start(self, goal: str, explicit_steps: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        steps_plan = plan_steps(goal, explicit_steps)
        if len(steps_plan) > self.max_steps_per_run:
            raise ValueError(
                f"Plan has {len(steps_plan)} steps, exceeds agent.max_steps_per_run={self.max_steps_per_run}"
            )
        run = await asyncio.to_thread(db.create_run, goal)
        await asyncio.to_thread(db.create_steps, run["id"], steps_plan)
        self.start_run(run["id"])
        detail = await self.get_run_detail(run["id"])
        assert detail is not None
        return detail

    def start_run(self, run_id: str) -> None:
        if self.is_active(run_id):
            return
        task = asyncio.create_task(self._execute_run(run_id))
        self._active_tasks[run_id] = task

    async def stop_run(self, run_id: str) -> bool:
        task = self._active_tasks.get(run_id)
        if task is None or task.done():
            return False
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return True

    async def stop_all(self) -> int:
        run_ids = self.active_run_ids()
        for run_id in run_ids:
            await self.stop_run(run_id)
        return len(run_ids)

    async def resume_run(self, run_id: str) -> dict[str, Any]:
        run = await asyncio.to_thread(db.get_run, run_id)
        if run is None:
            raise ValueError(f"No such run: {run_id}")
        if run["status"] not in ("interrupted", "stopped", "failed"):
            raise ValueError(f"Cannot resume a run in status '{run['status']}'")
        steps = await asyncio.to_thread(db.get_steps, run_id)
        for step in steps:
            if step["status"] in ("running", "failed"):
                await asyncio.to_thread(db.reset_step_to_pending, step["id"])
        await asyncio.to_thread(db.update_run_status, run_id, "pending")
        self.start_run(run_id)
        detail = await self.get_run_detail(run_id)
        assert detail is not None
        return detail

    async def discard_run(self, run_id: str) -> dict[str, Any]:
        run = await asyncio.to_thread(db.get_run, run_id)
        if run is None:
            raise ValueError(f"No such run: {run_id}")
        await asyncio.to_thread(db.update_run_status, run_id, "discarded")
        detail = await self.get_run_detail(run_id)
        assert detail is not None
        return detail

    async def recover_interrupted_runs(self) -> int:
        """Call once at backend startup. Any run still 'running' in the DB
        means the previous process died mid-run (crash recovery,
        ARCHITECTURE.md Section 8) — there's no in-memory task for it any
        more, so mark it interrupted and let the user decide to Resume or
        Discard rather than silently continuing or losing it."""
        stuck_runs = await asyncio.to_thread(db.list_runs_by_status, "running")
        for run in stuck_runs:
            steps = await asyncio.to_thread(db.get_steps, run["id"])
            for step in steps:
                if step["status"] == "running":
                    await asyncio.to_thread(db.reset_step_to_pending, step["id"])
            await asyncio.to_thread(db.update_run_status, run["id"], "interrupted")
        return len(stuck_runs)

    # --- the loop itself -------------------------------------------------------

    async def _execute_run(self, run_id: str) -> None:
        await asyncio.to_thread(db.update_run_status, run_id, "running")
        self._publish(run_id, {"type": "run_update", "run": await asyncio.to_thread(db.get_run, run_id)})

        final_status = "completed"
        error_msg: str | None = None
        current_step_id: str | None = None

        try:
            steps = await asyncio.to_thread(db.get_steps, run_id)
            for step in steps:
                if step["status"] == "done":
                    continue  # resume support: don't re-run already-validated steps

                current_step_id = step["id"]
                await asyncio.to_thread(db.update_step, step["id"], "running", started_at=_now_iso())
                await self._publish_step(run_id, step["id"])

                executor = EXECUTORS.get(step["type"])
                if executor is None:
                    final_status = "failed"
                    error_msg = f"No executor registered for step type '{step['type']}'"
                    await asyncio.to_thread(db.update_step, step["id"], "failed", error=error_msg, finished_at=_now_iso())
                    await self._publish_step(run_id, step["id"])
                    break

                params = step["params"]

                async def _attempt(executor=executor, params=params) -> dict[str, Any]:
                    return await executor(params)

                def _on_attempt_failed(attempt: int, exc: Exception) -> None:
                    logger.warning(
                        "Step attempt failed",
                        extra={"extra_fields": {"run_id": run_id, "step_id": step["id"], "attempt": attempt, "error": str(exc)}},
                    )

                try:
                    result = await run_with_retry(
                        _attempt, self.max_step_retries, self.retry_backoff_base_s, _on_attempt_failed
                    )
                except StepFailed as exc:
                    await asyncio.to_thread(db.update_step, step["id"], "failed", error=str(exc), finished_at=_now_iso())
                    await self._publish_step(run_id, step["id"])
                    final_status = "failed"
                    error_msg = str(exc)
                    break

                # Validator (Phase 3 stub): a step that returned without
                # raising and produced a dict is considered valid. Phase 6+
                # findings get a real validation pass; this loop already
                # has the hook point (right here) to add one.
                await asyncio.to_thread(db.update_step, step["id"], "done", output=result, finished_at=_now_iso())
                await self._publish_step(run_id, step["id"])
                current_step_id = None
        except asyncio.CancelledError:
            final_status = "stopped"
            if current_step_id:
                await asyncio.to_thread(db.update_step, current_step_id, "stopped", finished_at=_now_iso())
                await self._publish_step(run_id, current_step_id)
            raise
        finally:
            await asyncio.to_thread(db.update_run_status, run_id, final_status, error=error_msg)
            run = await asyncio.to_thread(db.get_run, run_id)
            self._publish(run_id, {"type": "run_update", "run": run})
            self._active_tasks.pop(run_id, None)

    async def _publish_step(self, run_id: str, step_id: str) -> None:
        steps = await asyncio.to_thread(db.get_steps, run_id)
        step = next((s for s in steps if s["id"] == step_id), None)
        if step:
            self._publish(run_id, {"type": "step_update", "step": step})


agent_manager: AgentManager | None = None


def get_agent_manager() -> AgentManager:
    if agent_manager is None:
        raise RuntimeError("AgentManager not initialized — call init_agent_manager() at startup")
    return agent_manager


def init_agent_manager(max_step_retries: int, retry_backoff_base_s: float, max_steps_per_run: int) -> AgentManager:
    global agent_manager
    agent_manager = AgentManager(max_step_retries, retry_backoff_base_s, max_steps_per_run)
    return agent_manager
