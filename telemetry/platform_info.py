"""Real platform / architecture detection.

Phase 1: fully implemented for ARM-vs-x86 reporting.
Later phases use `detection` output to select ONNX vs QNN backends.
No simulation here — everything returned is read from the live host.
"""
from __future__ import annotations

import os
import platform
import sys


def _normalize_machine(machine: str) -> str:
    m = (machine or "").lower()
    if m in ("amd64", "x86_64", "x64", "em64t"):
        return "x86_64"
    if m in ("arm64", "aarch64"):
        return "ARM64"
    return machine or "unknown"


def _is_arm(normalized: str) -> bool:
    return normalized.upper() in ("ARM64", "AARCH64")


def _cpu_name() -> str:
    # Best-effort, no third-party deps. PROCESSOR_IDENTIFIER is reliable on Windows.
    ident = os.environ.get("PROCESSOR_IDENTIFIER", "").strip()
    if ident:
        return ident
    return platform.processor() or "unknown"


def _snapdragon_evidence(cpu_name: str) -> list[str]:
    hits: list[str] = []
    low = cpu_name.lower()
    for token in ("snapdragon", "qcom", "qualcomm", "hexagon", "x elite", "x plus",
                  "sc8280", "sc8180", "8cx"):
        if token in low:
            hits.append(f"cpu-name contains '{token}'")
    return hits


def detection() -> dict:
    """Return live host architecture facts. All fields are REAL telemetry."""
    uname = platform.uname()
    machine_raw = uname.machine or platform.machine()
    normalized = _normalize_machine(machine_raw)
    is_arm = _is_arm(normalized)
    cpu_name = _cpu_name()
    snap_evidence = _snapdragon_evidence(cpu_name)
    return {
        # raw facts (real)
        "source": "live-host",
        "simulated": False,
        "os": {"system": uname.system, "release": uname.release,
               "version": uname.version},
        "python": sys.version.split()[0],
        "machine_raw": machine_raw,
        # normalized classification
        "arch_normalized": normalized,          # "x86_64" | "ARM64" | other
        "is_arm": is_arm,
        "is_x86_64": normalized == "x86_64",
        "cpu_name": cpu_name,
        # Snapdragon readiness (real check, expected False on Intel/AMD PCs)
        "is_snapdragon": bool(is_arm and snap_evidence),
        "snapdragon_evidence": snap_evidence,
        "npu_note": (
            "Hexagon NPU presence check is a Phase-3 item (QNN SDK device "
            "enumeration). Phase 1 does not claim NPU presence."
            if not snap_evidence else
            "Possible Snapdragon SoC by CPU name; NPU still unconfirmed until "
            "Phase-3 QNN probe runs."
        ),
        # What later phases will do with this
        "phase_routing": {
            "onnx_backend": "ARM-optimized build" if is_arm else "x86_64 build",
            "qnn_backend": "eligible to probe" if is_arm else "not applicable (x86_64 host)",
        },
    }
