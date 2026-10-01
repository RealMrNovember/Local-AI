"""SQLite persistence for tool invocations. This table IS the audit log
(product brief Section 31/32) — every invocation, confirmed or not, is
recorded here with timestamps, args, output, and exit code. A dedicated
Logs UI panel (searchable) is Phase 8; Phase 4 exposes this via
GET /api/tools/invocations.

Same plain-sqlite3-via-asyncio.to_thread pattern as app/agent/db.py —
deliberately not shared with it (separate concerns, separate file) even
though the approach is identical.
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
CREATE TABLE IF NOT EXISTS tool_invocations (
    id TEXT PRIMARY KEY,
    tool_name TEXT NOT NULL,
    args TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    status TEXT NOT NULL,
    requested_by TEXT NOT NULL,
    run_id TEXT,
    step_id TEXT,
    exit_code INTEGER,
    stdout TEXT,
    stderr TEXT,
    output TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    duration_s REAL
);

CREATE INDEX IF NOT EXISTS idx_tool_invocations_created_at ON tool_invocations(created_at);
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
        raise RuntimeError("tools.db not configured — call configure() at startup")
    conn = sqlite3.connect(_db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_invocation(
    tool_name: str,
    args: dict[str, Any],
    risk_level: str,
    requested_by: str,
    status: str,
    run_id: str | None = None,
    step_id: str | None = None,
) -> dict[str, Any]:
    invocation_id = uuid.uuid4().hex
    now = _now()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO tool_invocations "
            "(id, tool_name, args, risk_level, status, requested_by, run_id, step_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (invocation_id, tool_name, json.dumps(args), risk_level, status, requested_by, run_id, step_id, now),
        )
    return get_invocation(invocation_id)  # type: ignore[return-value]


def update_invocation(invocation_id: str, **fields: Any) -> None:
    if not fields:
        return
    if "output" in fields and fields["output"] is not None and not isinstance(fields["output"], str):
        fields["output"] = json.dumps(fields["output"])
    columns = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [invocation_id]
    with _connect() as conn:
        conn.execute(f"UPDATE tool_invocations SET {columns} WHERE id = ?", values)


def get_invocation(invocation_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM tool_invocations WHERE id = ?", (invocation_id,)).fetchone()
        return _deserialize(dict(row)) if row else None


def list_invocations(limit: int = 100) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM tool_invocations ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [_deserialize(dict(r)) for r in rows]


def list_pending_confirmations() -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM tool_invocations WHERE status = 'pending_confirmation' ORDER BY created_at ASC"
        ).fetchall()
        return [_deserialize(dict(r)) for r in rows]


def _deserialize(row: dict[str, Any]) -> dict[str, Any]:
    row["args"] = json.loads(row["args"]) if row["args"] else {}
    row["output"] = json.loads(row["output"]) if row["output"] else None
    return row
