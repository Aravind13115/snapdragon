"""Reversible-optimization planner. Phase 1 = dry-run suggestions ONLY.

`build_plan()` analyses live telemetry and returns human-readable
suggestions (e.g. 'Chrome uses 34% CPU'). It executes NOTHING and
returns `executed: []` always. Phase 4 will add real actions, each
gated by safety.engine.guard() + allowlist + user confirm + journal.
"""
from __future__ import annotations


def build_plan(stats: dict, processes: dict) -> dict:
    suggestions: list[dict] = []
    rows = processes.get("rows", [])
    for r in rows[:10]:
        if r["pid"] in (0, 4):  # System Idle / System pseudo-processes: never actionable
            continue
        if r["cpu_pct"] >= 10.0:
            suggestions.append({
                "pid": r["pid"], "name": r["name"],
                "reason": f"using {r['cpu_pct']}% CPU",
                "proposed": "none in Phase 1 (observe-only)",
            })
    return {
        "simulated": False,   # computed from real telemetry, honestly empty of actions
        "mode": "dry-run",
        "executed": [],
        "reversible": True,
        "suggestions": suggestions,
        "note": "Phase 1 never acts. Later phases require safety approval per suggestion.",
    }
