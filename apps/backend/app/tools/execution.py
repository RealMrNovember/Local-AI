"""Execution Engine (ARCHITECTURE.md Sections 7.2/12/18).

Two execution paths:
- `run_subprocess`: a real OS process. On cancel/timeout, kills the whole
  process tree via psutil — not just the top-level PID — per Section 8's
  kill-switch requirement, now that Phase 4 introduces real subprocesses.
- filesystem ops: no exec() at all, pure Python I/O scoped to
  execution.filesystem_allowed_roots (default: workspace/, projects/) so a
  path-traversal attempt (`../../etc/passwd`) is rejected before any I/O
  happens, not caught after the fact.
"""
from __future__ import annotations

import asyncio
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import psutil

from ..config import REPO_ROOT


class ToolExecutionError(Exception):
    pass


class PathNotAllowed(ToolExecutionError):
    pass


@dataclass
class SubprocessResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_s: float


def _kill_process_tree(pid: int) -> None:
    try:
        parent = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return
    children = parent.children(recursive=True)
    for child in children:
        try:
            child.kill()
        except psutil.NoSuchProcess:
            pass
    try:
        parent.kill()
    except psutil.NoSuchProcess:
        pass


async def run_subprocess(
    executable: str,
    args: list[str],
    cwd: Path | None = None,
    timeout_s: float = 60.0,
) -> SubprocessResult:
    resolved_executable = sys.executable if executable == "python" else executable
    start = time.monotonic()
    proc = await asyncio.create_subprocess_exec(
        resolved_executable,
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(cwd) if cwd else None,
    )
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except asyncio.TimeoutError:
        _kill_process_tree(proc.pid)
        raise ToolExecutionError(f"'{executable}' timed out after {timeout_s}s")
    except asyncio.CancelledError:
        # Kill switch / resume-on-crash path: a real process must actually
        # die here, not just be abandoned to run unsupervised in the
        # background after we stop awaiting it.
        _kill_process_tree(proc.pid)
        raise
    duration = time.monotonic() - start
    return SubprocessResult(
        exit_code=proc.returncode if proc.returncode is not None else -1,
        stdout=stdout_bytes.decode(errors="replace"),
        stderr=stderr_bytes.decode(errors="replace"),
        duration_s=duration,
    )


def _resolve_safe_path(relative_path: str, allowed_roots: list[str]) -> Path:
    if not relative_path or relative_path.startswith(("/", "\\")) or ":" in relative_path:
        raise PathNotAllowed(f"Path '{relative_path}' must be relative to an allowed root")
    candidate = (REPO_ROOT / relative_path).resolve()
    for root in allowed_roots:
        root_path = (REPO_ROOT / root).resolve()
        if candidate == root_path or root_path in candidate.parents:
            return candidate
    raise PathNotAllowed(
        f"Path '{relative_path}' resolves outside the allowed roots {allowed_roots} "
        "(ARCHITECTURE.md Section 18)"
    )


async def fs_list(relative_path: str, allowed_roots: list[str]) -> list[dict]:
    safe = _resolve_safe_path(relative_path or ".", allowed_roots)

    def _list() -> list[dict]:
        if not safe.exists():
            raise ToolExecutionError(f"'{relative_path}' does not exist")
        if not safe.is_dir():
            raise ToolExecutionError(f"'{relative_path}' is not a directory")
        return [
            {"name": p.name, "is_dir": p.is_dir(), "size": p.stat().st_size if p.is_file() else None}
            for p in sorted(safe.iterdir())
        ]

    return await asyncio.to_thread(_list)


async def fs_read(relative_path: str, allowed_roots: list[str], max_bytes: int = 200_000) -> str:
    safe = _resolve_safe_path(relative_path, allowed_roots)

    def _read() -> str:
        if not safe.exists() or not safe.is_file():
            raise ToolExecutionError(f"'{relative_path}' is not a readable file")
        data = safe.read_bytes()[:max_bytes]
        return data.decode("utf-8", errors="replace")

    return await asyncio.to_thread(_read)


async def fs_write(relative_path: str, content: str, allowed_roots: list[str]) -> dict:
    safe = _resolve_safe_path(relative_path, allowed_roots)

    def _write() -> dict:
        safe.parent.mkdir(parents=True, exist_ok=True)
        safe.write_text(content, encoding="utf-8")
        return {"bytes_written": len(content.encode("utf-8"))}

    return await asyncio.to_thread(_write)


async def fs_delete(relative_path: str, allowed_roots: list[str]) -> dict:
    safe = _resolve_safe_path(relative_path, allowed_roots)

    def _delete() -> dict:
        if not safe.exists():
            raise ToolExecutionError(f"'{relative_path}' does not exist")
        if safe.is_dir():
            shutil.rmtree(safe)
        else:
            safe.unlink()
        return {"deleted": relative_path}

    return await asyncio.to_thread(_delete)
