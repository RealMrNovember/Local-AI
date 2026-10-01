"""Planner — turns a goal (+ optional explicit steps) into an ordered step
list (ARCHITECTURE.md Section 6).

Still rule-free by design: a caller supplies the exact steps to run (now
including real `tool_call` steps as of Phase 4 — see app/tools/), or gets
a single trivial `stub_echo` step back. A model-backed decomposition step
(goal text -> a real plan) is a reasonable Phase 4+/5 addition once there
are enough real tools for a model-authored plan to meaningfully choose
between — intentionally not built yet.
"""
from __future__ import annotations

from typing import Any

KNOWN_STEP_TYPES = {"stub_echo", "stub_sleep", "tool_call"}


def plan_steps(goal: str, explicit_steps: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if explicit_steps:
        for step in explicit_steps:
            if step.get("type") not in KNOWN_STEP_TYPES:
                raise ValueError(
                    f"Unknown step type '{step.get('type')}' — Phase 3 only supports {sorted(KNOWN_STEP_TYPES)}"
                )
        return explicit_steps
    return [{"type": "stub_echo", "params": {"text": goal}}]
