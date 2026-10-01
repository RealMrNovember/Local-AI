"""Planner — turns a goal (+ optional explicit steps) into an ordered step
list (ARCHITECTURE.md Section 6).

Phase 3 scope: this validates the Plan/Execute/Observe/Validate state
machine itself, not intelligent planning. Only two stub step types exist
(`stub_echo`, `stub_sleep`) — Phase 4 replaces these with real Tool
Registry calls and gives the Planner an actual model-backed decomposition
step. Until then, a caller either supplies the exact steps to run (how the
roadmap's Phase 3 exit test exercises the kill switch and persistence) or
gets a single trivial echo step back.
"""
from __future__ import annotations

from typing import Any

KNOWN_STEP_TYPES = {"stub_echo", "stub_sleep"}


def plan_steps(goal: str, explicit_steps: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if explicit_steps:
        for step in explicit_steps:
            if step.get("type") not in KNOWN_STEP_TYPES:
                raise ValueError(
                    f"Unknown step type '{step.get('type')}' — Phase 3 only supports {sorted(KNOWN_STEP_TYPES)}"
                )
        return explicit_steps
    return [{"type": "stub_echo", "params": {"text": goal}}]
