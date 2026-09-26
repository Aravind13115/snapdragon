"""Qualcomm QNN / Hexagon NPU backend probe. Phase-3 slot.

Phase 1 only answers: 'is QNN inference possible on this host?'
It performs a read-only eligibility check (ARM + Snapdragon evidence)
and reports unavailable with a reason everywhere else. No SDK import,
no driver calls, no fallback simulation of inference results.
"""
from __future__ import annotations


def probe(platform_report: dict) -> dict:
    is_arm = bool(platform_report.get("is_arm"))
    is_snap = bool(platform_report.get("is_snapdragon"))
    if is_arm and is_snap:
        state, reason = "ready-to-probe", (
            "Snapdragon ARM host detected. Phase 3 will enumerate QNN SDK / "
            "Hexagon DSP here.")
    elif is_arm:
        state, reason = "unavailable", "ARM host but no Snapdragon evidence; QNN not applicable."
    else:
        state, reason = "unavailable", (
            f"Host arch is {platform_report.get('arch_normalized')} "
            f"({platform_report.get('cpu_name')}); Hexagon NPU only exists on "
            "Snapdragon SoCs. Requires a Snapdragon X Elite/Plus (ARM) PC.")
    return {
        "backend": "qnn-hexagon",
        "simulated": False,   # this availability verdict is a real claim about the host
        "available": state == "ready-to-probe",
        "state": state,
        "reason": reason,
        "phase": 3,
    }
