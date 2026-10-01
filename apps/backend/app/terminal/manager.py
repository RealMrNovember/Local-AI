"""Terminal sessions backed by a real PTY (ARCHITECTURE.md Section 5
PHASE 5 / product brief Section 27).

Windows-only for now, via pywinpty (ConPTY). Verified against a real
spawned powershell.exe before writing this module — `read()` blocks until
output is available and returns it with full ANSI/VT100 sequences intact,
which is exactly what a terminal emulator (xterm.js) wants to render.
POSIX support (the `ptyprocess` package has a near-identical API) is
Phase 9b's Linux boot environment work — not added speculatively here
since it can't be exercised or verified on this dev machine.

winpty's PtyProcess.read() is a blocking native call, so each session runs
its own background OS thread doing the blocking reads, and hands chunks
back to the asyncio side via `loop.call_soon_threadsafe` — the asyncio
event loop is never blocked waiting on terminal I/O.
"""
from __future__ import annotations

import asyncio
import logging
import platform
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger("cicibyte.terminal")

IS_WINDOWS = platform.system() == "Windows"

if IS_WINDOWS:
    import winpty
else:
    winpty = None  # see module docstring — POSIX is Phase 9b

MAX_HISTORY_CHARS = 200_000
DEFAULT_SHELLS: dict[str, list[str]] = {
    "powershell": ["powershell.exe", "-NoLogo"],
    "cmd": ["cmd.exe"],
}


@dataclass
class TerminalSessionInfo:
    id: str
    shell: str
    created_at: str
    alive: bool
    pid: int | None
    cols: int
    rows: int


class TerminalSession:
    def __init__(
        self, session_id: str, shell_key: str, cwd: str, cols: int, rows: int, loop: asyncio.AbstractEventLoop
    ) -> None:
        if not IS_WINDOWS:
            raise RuntimeError(
                "Real terminal sessions are only implemented for Windows (pywinpty) in Phase 5. "
                "POSIX support is Phase 9b (Linux boot environment) work."
            )
        argv = DEFAULT_SHELLS.get(shell_key)
        if argv is None:
            raise ValueError(f"Unknown shell '{shell_key}', must be one of {list(DEFAULT_SHELLS)}")

        self.id = session_id
        self.shell = shell_key
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.cols = cols
        self.rows = rows
        self.alive = True

        # Captured on the event-loop thread by the caller (create_session) and
        # passed in explicitly -- __init__ itself runs inside asyncio.to_thread,
        # i.e. a worker thread, where asyncio.get_event_loop() is not reliable.
        self._loop = loop
        self._subscribers: list[asyncio.Queue] = []
        self._history: list[str] = []
        self._history_len = 0
        self._lock = threading.Lock()

        self._pty = winpty.PtyProcess.spawn(argv, cwd=cwd or None, dimensions=(rows, cols))
        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()

    # --- reader thread (runs OFF the asyncio loop) ----------------------------

    def _reader_loop(self) -> None:
        while True:
            try:
                chunk = self._pty.read(4096)
            except EOFError:
                break
            except Exception as exc:  # noqa: BLE001 — a dead/killed PTY can raise various native errors
                logger.info("Terminal reader loop ending", extra={"extra_fields": {"session_id": self.id, "error": str(exc)}})
                break
            if not chunk:
                continue
            self._append_history(chunk)
            self._loop.call_soon_threadsafe(self._broadcast, chunk)
        self.alive = False
        self._loop.call_soon_threadsafe(self._broadcast, None)  # sentinel: session closed

    def _append_history(self, chunk: str) -> None:
        with self._lock:
            self._history.append(chunk)
            self._history_len += len(chunk)
            while self._history_len > MAX_HISTORY_CHARS and len(self._history) > 1:
                dropped = self._history.pop(0)
                self._history_len -= len(dropped)

    def get_history(self) -> str:
        with self._lock:
            return "".join(self._history)

    # --- asyncio-side API --------------------------------------------------------

    def _broadcast(self, chunk: str | None) -> None:
        for q in self._subscribers:
            q.put_nowait(chunk)

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self._subscribers:
            self._subscribers.remove(q)

    async def write(self, data: str) -> None:
        await asyncio.to_thread(self._pty.write, data)

    async def resize(self, cols: int, rows: int) -> None:
        self.cols, self.rows = cols, rows
        await asyncio.to_thread(self._pty.setwinsize, rows, cols)

    async def terminate(self) -> None:
        await asyncio.to_thread(self._pty.terminate, True)

    def info(self) -> TerminalSessionInfo:
        pid = None
        try:
            pid = self._pty.pid  # may not exist on every backend version
        except AttributeError:
            pass
        return TerminalSessionInfo(
            id=self.id, shell=self.shell, created_at=self.created_at,
            alive=self.alive, pid=pid, cols=self.cols, rows=self.rows,
        )


class TerminalManager:
    def __init__(self) -> None:
        self._sessions: dict[str, TerminalSession] = {}

    async def create_session(self, shell: str, cwd: str, cols: int = 80, rows: int = 24) -> TerminalSession:
        session_id = uuid.uuid4().hex
        loop = asyncio.get_running_loop()
        session = await asyncio.to_thread(TerminalSession, session_id, shell, cwd, cols, rows, loop)
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> TerminalSession | None:
        return self._sessions.get(session_id)

    def list_sessions(self) -> list[TerminalSessionInfo]:
        return [s.info() for s in self._sessions.values()]

    async def close_session(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if session is None:
            return False
        await session.terminate()
        self._sessions.pop(session_id, None)
        return True

    async def close_all(self) -> int:
        ids = list(self._sessions.keys())
        for session_id in ids:
            await self.close_session(session_id)
        return len(ids)


_terminal_manager: TerminalManager | None = None


def get_terminal_manager() -> TerminalManager:
    if _terminal_manager is None:
        raise RuntimeError("TerminalManager not initialized — call init_terminal_manager() at startup")
    return _terminal_manager


def init_terminal_manager() -> TerminalManager:
    global _terminal_manager
    _terminal_manager = TerminalManager()
    return _terminal_manager
