"""Safety engine. Phase 1 = hard read-only mode.

Any future code path that wants to terminate, suspend, renice, or
otherwise mutate a process/system must call `guard()` first, which
raises in Phase 1. Later phases extend this with allowlists, user
confirmation, and reversible-action journals — but the default-deny
posture stays.
"""
from __future__ import annotations

FORBIDDEN_PHASE1 = (
    "terminate", "kill", "suspend", "resume-other", "set_priority",
    "renice", "set_affinity", "inject", "stop_service",
)

MODE = "observe-only"


def guard(action: str) -> None:
    """Raise for every mutating action in Phase 1. Read-only actions never reach here."""
    if action in FORBIDDEN_PHASE1:
        raise RuntimeError(
            f"[safety] blocked mutating action '{action}' — Phase 1 is observe-only. "
            "No process was touched.")
    raise RuntimeError(f"[safety] unknown action '{action}' denied by default-deny policy.")


def status() -> dict:
    return {
        "mode": MODE,
        "simulated": False,
        "mutations_allowed": False,
        "process_termination": "disabled (not implemented by design in Phase 1)",
        "blocked_actions": list(FORBIDDEN_PHASE1),
        "phase4_plan": "allowlist + confirm + reversible journal before any action executes",
    }
