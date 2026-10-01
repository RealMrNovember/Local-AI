"""Model Router (ARCHITECTURE.md Section 5.3) — rule-based task-type to
model-category mapping. Manual override always wins; this only decides
what to use when the caller doesn't specify a model.
"""
from __future__ import annotations

from ..models_registry import ModelEntry, load_registry

# task-type -> ordered category preference
TASK_TYPE_CATEGORY_PRIORITY: dict[str, list[str]] = {
    "coding": ["CODING", "GENERAL"],
    "reasoning": ["REASONING", "GENERAL"],
    "general": ["GENERAL", "CODING"],
    "experimental": ["EXPERIMENTAL"],
}


def pick_model(task_type: str | None = None, installed_only: bool = True) -> ModelEntry | None:
    entries = load_registry()
    if installed_only:
        entries = [e for e in entries if e.installed]
    if not entries:
        return None

    if task_type:
        for category in TASK_TYPE_CATEGORY_PRIORITY.get(task_type, []):
            for e in entries:
                if e.category == category:
                    return e

    for e in entries:
        if e.default:
            return e
    return entries[0]
