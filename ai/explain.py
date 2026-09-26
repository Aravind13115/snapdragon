"""Deterministic explainable-AI: WHY lines derived from input signals.

Not a second model — a fixed mapping from feature values to human-readable
reasons, so every prediction can show its evidence on the dashboard.
"""
from __future__ import annotations


def explain(vec: list[float], meta: dict, ai_class: str,
            recommendation: str) -> list[str]:
    cpu, trend, mem, io, net, fg, batt, lact, anat, emu, hist = vec
    why: list[str] = []
    if fg >= 0.5:
        why.append("Owns the foreground window (user-facing)")
    else:
        why.append("Background process (no foreground window)")
    if cpu >= 0.20:
        why.append(f"High current CPU ({cpu*100:.0f}% of machine)")
    elif cpu >= 0.05:
        why.append(f"Moderate CPU ({cpu*100:.1f}%)")
    else:
        why.append("Low current CPU")
    if hist >= 0.10 and trend > 0.55:
        why.append("Recurring/rising CPU usage pattern")
    if io >= 0.4:
        why.append("Significant disk activity")
    if net >= 0.2:
        why.append("Active network connections")
    if batt >= 0.5:
        why.append("System on battery power")
    else:
        why.append("System on AC power")
    if lact >= 0.8:
        why.append("User recently active")
    elif lact <= 0.25:
        why.append("Low recent user interaction")
    if emu >= 0.5:
        why.append("Running under emulation (not native)")
    elif anat >= 1.0:
        why.append("Native 64-bit execution")
    if mem >= 0.25:
        why.append(f"Large memory footprint ({mem*100:.0f}%)")
    if meta.get("unavailable"):
        why.append("Note: unavailable signals: " + ", ".join(meta["unavailable"]))
    why.append(f"AI classification: {ai_class} -> {recommendation}")
    return why
