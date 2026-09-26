"""Non-destructive optimization simulator (Phase 3).

Pipeline position:
    ... -> SAFETY DECISION -> SIMULATED ACTION -> PROJECTED EFFECT.

Contract:
  * Input: an enriched AI row (model_class, safety_state, cpu, why, ...).
  * Output: a SIMULATION record. Every output is flagged simulated:true
    and every effect string is labelled PROJECTED/ILLUSTRATIVE.
  * Only rows whose safety_state == "OPTIMIZATION CANDIDATE" receive an
    action proposal (REDUCE_BACKGROUND_ACTIVITY / DEFER_BACKGROUND_WORK).
    Everything else -> NO_ACTION (with the safety reason preserved).
  * Pure computation + text. No process, priority, service, registry,
    driver, or kernel interaction exists in this module — by design there
    is nothing here that *could* act; the action vocabulary is advisory.
  * Projected effects are qualitative levels (HIGH/MEDIUM/LOW), never fake
    measured percentages.
"""
from __future__ import annotations

SIMULATED = True

ACTIONS = ("NO_ACTION", "PROTECT",
           "REDUCE_BACKGROUND_ACTIVITY", "DEFER_BACKGROUND_WORK")

_ACTION_FOR = {
    "FLEXIBLE": "REDUCE_BACKGROUND_ACTIVITY",
    "DEFERRABLE": "DEFER_BACKGROUND_WORK",
}

_LEVELS = ("LOW", "MEDIUM", "HIGH")


def _pressure(cpu_pct) -> str:
    try:
        c = float(cpu_pct or 0.0)
    except (TypeError, ValueError):
        return "UNKNOWN"
    if c >= 10.0:
        return "HIGH"
    if c >= 2.0:
        return "MEDIUM"
    return "LOW"


def preview(row: dict) -> dict:
    """Simulate one decision. Never touches any process."""
    ai = row.get("ai") or {}
    name = row.get("name") or "?"
    arch = row.get("arch") or "Unknown"
    cpu = row.get("cpu_pct")
    before = _pressure(cpu)
    base = {
        "simulated": SIMULATED,
        "simulation": True,
        "process": name,
        "architecture": arch,
        "model_class": ai.get("model_class"),
        "raw_confidence": ai.get("raw_confidence"),
        "familiarity": ai.get("familiarity"),
        "final_confidence": ai.get("final_confidence"),
        "safety_state": ai.get("safety_state"),
        "why": list(ai.get("why") or []),
        "labels": ["SIMULATED", "PROJECTED", "ILLUSTRATIVE"],
    }
    if ai.get("safety_state") != "OPTIMIZATION CANDIDATE":
        reason = ai.get("override_reason") or (
            f"safety state is {ai.get('safety_state')}, not a candidate")
        return base | {
            "simulated_action": "NO_ACTION",
            "projected_effect": "NO_CHANGE_PROJECTED",
            "before": before, "after": before,
            "explanation": f"No action simulated for {name}: {reason}.",
        }
    action = _ACTION_FOR.get(ai.get("model_class"), "NO_ACTION")
    after = {"HIGH": "MEDIUM", "MEDIUM": "LOW", "LOW": "LOW",
             "UNKNOWN": "UNKNOWN"}[before]
    return base | {
        "simulated_action": action,
        "projected_effect": ("LOWER_BACKGROUND_CPU_PRESSURE"
                             if after != before else
                             "NEGLIGIBLE_CHANGE_PROJECTED"),
        "before": f"BACKGROUND_PRESSURE_{before}",
        "after": f"BACKGROUND_PRESSURE_{after}",
        "explanation": (
            f"Simulation only: deferring background work of {name} "
            f"is projected to move background CPU pressure from {before} "
            f"to {after}. Illustrative estimate, not a measurement. "
            f"Foreground and protected workloads are untouched."),
    }


def sequence(row: dict) -> dict:
    """Staged presentation pipeline for the SIMULATE animation.

    The frontend steps through `stages` with timed delays; the server
    computes the whole result instantly (GET-only, no process effect).
    """
    sim = preview(row)
    stages = ["ANALYZING", "SAFETY_CHECK",
              "ACTION_APPROVED" if sim["simulated_action"] != "NO_ACTION"
              else "ACTION_DENIED",
              "SIMULATING", "PROJECTED_RESULT"]
    sim["stages"] = stages
    return sim
