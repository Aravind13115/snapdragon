"""Read-only process enumeration. OBSERVE-ONLY by design.

Phase-1 contract:
  * Only reads: pid, name, cpu%, mem%, status, username.
  * NEVER calls terminate/kill/suspend/nice/priority setters.
  * The safety engine (safety/engine.py) also blocks such calls if
    any future code path attempts them.

`enrich_with_classification()` attaches a label via the inference
layer. In Phase 1 that label is an explicit HEURISTIC stub
(see inference/onnx_stub.py) and is flagged simulated:true so the
dashboard can show it honestly.
"""
from __future__ import annotations

import psutil

from inference.onnx_stub import HeuristicClassifier

_classifier = HeuristicClassifier()

try:
    _NCPU = psutil.cpu_count(logical=True) or 1
except Exception:
    _NCPU = 1

_SAFE_ATTRS = ("pid", "name", "status", "username")


def top_processes(limit: int = 50, sort: str = "cpu") -> dict:
    procs: list[dict] = []
    for p in psutil.process_iter(["pid", "name", "memory_percent", "status", "username"]):
        try:
            info = p.info
            # cpu_percent per-process needs a prior call; first poll may be 0.0 — honest.
            try:
                cpu = p.cpu_percent(interval=None)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                cpu = 0.0
            # psutil reports per-process CPU against ONE core (can exceed
            # 100% on multicore). Normalize to % of total machine capacity
            # so the dashboard matches Task Manager-style readings.
            cpu = round((cpu or 0.0) / _NCPU, 1)
            row = {
                "pid": info.get("pid"),
                "name": info.get("name") or "?",
                "cpu_pct": round(cpu or 0.0, 1),
                "mem_pct": round(info.get("memory_percent") or 0.0, 2),
                "status": info.get("status") or "?",
                "username": info.get("username") or "?",
            }
            row["label"] = _classifier.classify(row["name"], row["cpu_pct"])
            procs.append(row)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    key = {"cpu": lambda r: r["cpu_pct"], "mem": lambda r: r["mem_pct"]}.get(sort, lambda r: r["cpu_pct"])
    procs.sort(key=key, reverse=True)
    return {
        "simulated": False,   # the process list itself is real
        "count": len(procs),
        "rows": procs[: max(1, min(limit, 200))],
        "note": "labels attached per-row are Phase-1 heuristics (simulated) until the Phase-2 ONNX model lands.",
    }
