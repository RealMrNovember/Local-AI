"""Structured logging: JSON lines to logs/app.jsonl + human-readable console."""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class JsonLineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        extra = getattr(record, "extra_fields", None)
        if extra:
            payload.update(extra)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(logs_dir: Path, level: str = "INFO", json_file: bool = True, console: bool = True) -> None:
    root = logging.getLogger()
    root.setLevel(level.upper())
    root.handlers.clear()

    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s", "%H:%M:%S")
        )
        root.addHandler(console_handler)

    if json_file:
        logs_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(logs_dir / "app.jsonl", encoding="utf-8")
        file_handler.setFormatter(JsonLineFormatter())
        root.addHandler(file_handler)
