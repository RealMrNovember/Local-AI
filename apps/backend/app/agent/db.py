"""SQLite persistence for AgentRun/Step (ARCHITECTURE.md Section 8).

Plain sqlite3, not an ORM — the schema is small and this avoids pulling in
an async DB driver this early. Every public function is synchronous; the
manager calls them via `asyncio.to_thread` so the event loop never blocks
on disk I/O.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

_SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_runs (
    id TEXT PRIMARY KEY,
    goal TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    error TEXT
);

CREATE TABLE IF NOT EXISTS agent_steps (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES agent_runs(id),
    step_index INTEGER NOT NULL,
    type TEXT NOT NULL,
    params TEXT NOT NULL,
    status TEXT NOT NULL,
    output TEXT,
    error TEXT,
    started_at TEXT,
    finished_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_agent_steps_run_id ON agent_steps(run_id);
"""

_db_path: Path | None = None


def configure(db_path: Path) -> None:
    global _db_path
    _db_path = db_path
    _db_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.executescript(_SCHEMA)


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    if _db_path is None:
        raise RuntimeError("agent.db not configured — call configure() at startup")
    conn = sqlite3.connect(_db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex


# --- runs ----------------------------------------------------------------

def create_run(goal: str, status: str = "pending") -> dict[str, Any]:
    run_id = new_id()
    now = _now()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO agent_runs (id, goal, status, created_at, updated_at, error) VALUES (?, ?, ?, ?, ?, NULL)",
            (run_id, goal, status, now, now),
        )
    return get_run(run_id)  # type: ignore[return-value]


def update_run_status(run_id: str, status: str, error: str | None = None) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE agent_runs SET status = ?, updated_at = ?, error = COALESCE(?, error) WHERE id = ?",
            (status, _now(), error, run_id),
        )


def get_run(run_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM agent_runs WHERE id = ?", (run_id,)).fetchone()
        return dict(row) if row else None


def list_runs(limit: int = 50) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM agent_runs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def list_runs_by_status(status: str) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM agent_runs WHERE status = ?", (status,)).fetchall()
        return [dict(r) for r in rows]


# --- steps -----------------------------------------------------------------

def create_steps(run_id: str, steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    created = []
    with _connect() as conn:
        for idx, step in enumerate(steps):
            step_id = new_id()
            conn.execute(
                "INSERT INTO agent_steps (id, run_id, step_index, type, params, status, output, error, started_at, finished_at) "
                "VALUES (?, ?, ?, ?, ?, 'pending', NULL, NULL, NULL, NULL)",
                (step_id, run_id, idx, step["type"], json.dumps(step.get("params", {}))),
            )
            created.append(step_id)
    return get_steps(run_id)


def get_steps(run_id: str) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM agent_steps WHERE run_id = ? ORDER BY step_index ASC", (run_id,)
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["params"] = json.loads(d["params"]) if d["params"] else {}
            d["output"] = json.loads(d["output"]) if d["output"] else None
            result.append(d)
        return result


def update_step(
    step_id: str,
    status: str,
    output: dict[str, Any] | None = None,
    error: str | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE agent_steps SET status = ?, "
            "output = COALESCE(?, output), "
            "error = COALESCE(?, error), "
            "started_at = COALESCE(?, started_at), "
            "finished_at = COALESCE(?, finished_at) "
            "WHERE id = ?",
            (status, json.dumps(output) if output is not None else None, error, started_at, finished_at, step_id),
        )


def reset_step_to_pending(step_id: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE agent_steps SET status = 'pending', error = NULL WHERE id = ?",
            (step_id,),
        )
