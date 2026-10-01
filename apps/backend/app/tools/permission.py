"""Permission Engine (ARCHITECTURE.md Section 9, product brief Section 44).

Three independent gates are described in the architecture: risk
classification, Target Scope, and Autonomy Mode. Target Scope is Phase 6
(it only matters once there are network/security tools); this module
implements the other two for Phase 4's System/Development tools.

The decision here can only make confirmation MORE likely than the
registry's own `requires_confirmation` flag — a tool can ask to always be
confirmed, but it can never opt out of what the current Autonomy Mode and
risk level demand.
"""
from __future__ import annotations

_RISK_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


def needs_confirmation(risk_level: str, autonomy_mode: str, tool_requires_confirmation: bool) -> bool:
    # CRITICAL always confirms, even in FULL autonomy (product brief Section 14/44).
    if risk_level == "CRITICAL":
        return True

    if autonomy_mode == "SAFE":
        # Confirm every tool call, regardless of risk.
        return True

    if autonomy_mode == "AUTO":
        # Low-risk local operations run automatically; MEDIUM+ or an
        # explicit per-tool flag still confirms.
        return tool_requires_confirmation or _RISK_ORDER.get(risk_level, 0) >= _RISK_ORDER["MEDIUM"]

    if autonomy_mode == "FULL":
        # CRITICAL already handled above; everything else runs within the
        # workspace/scope boundary without asking.
        return False

    # Unknown mode: fail toward the safest behavior rather than guessing.
    return True
