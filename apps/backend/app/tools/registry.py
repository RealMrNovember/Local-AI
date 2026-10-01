"""Tool Registry loader (ARCHITECTURE.md Section 7.1).

Tools are data, not code paths: every tool the agent or UI can call is
declared in config/tools.yaml and resolved generically here. Adding a tool
means adding a registry entry, not writing new agent logic.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ..config import REPO_ROOT

VALID_RISK_LEVELS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
VALID_KINDS = ("subprocess", "filesystem")


@dataclass
class ToolDefinition:
    name: str
    category: str
    kind: str  # "subprocess" | "filesystem"
    risk_level: str
    requires_confirmation: bool
    enabled: bool
    description: str
    executable: str | None = None  # subprocess only
    action: str | None = None  # filesystem only: "read" | "write" | "list" | "delete"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "kind": self.kind,
            "risk_level": self.risk_level,
            "requires_confirmation": self.requires_confirmation,
            "enabled": self.enabled,
            "description": self.description,
            "executable": self.executable,
            "action": self.action,
        }


def load_registry(registry_path: Path | None = None) -> list[ToolDefinition]:
    path = registry_path or (REPO_ROOT / "config" / "tools.yaml")
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    defs: list[ToolDefinition] = []
    for raw in data.get("tools", []):
        risk = raw["risk_level"]
        if risk not in VALID_RISK_LEVELS:
            raise ValueError(f"Tool '{raw['name']}' has invalid risk_level '{risk}'")
        kind = raw["kind"]
        if kind not in VALID_KINDS:
            raise ValueError(f"Tool '{raw['name']}' has invalid kind '{kind}'")
        defs.append(
            ToolDefinition(
                name=raw["name"],
                category=raw["category"],
                kind=kind,
                risk_level=risk,
                requires_confirmation=bool(raw.get("requires_confirmation", False)),
                enabled=bool(raw.get("enabled", True)),
                description=raw.get("description", ""),
                executable=raw.get("executable"),
                action=raw.get("action"),
            )
        )
    return defs


_cache: dict[str, ToolDefinition] | None = None


def get_tool(name: str) -> ToolDefinition | None:
    global _cache
    if _cache is None:
        _cache = {t.name: t for t in load_registry()}
    return _cache.get(name)


def reload_cache() -> None:
    global _cache
    _cache = None
