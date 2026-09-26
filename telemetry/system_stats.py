"""Real host telemetry via psutil. READ-ONLY.

Every value returned is sampled live from this machine.
Nothing here modifies any process or system setting.
"""
from __future__ import annotations

import time

import psutil

_boot_time = psutil.boot_time()


def _battery() -> dict:
    try:
        b = psutil.sensors_battery()
    except Exception:
        b = None
    if b is None:
        return {"present": False, "simulated": False}
    return {
        "present": True,
        "simulated": False,
        "percent": round(b.percent, 1),
        "plugged": bool(b.power_plugged),
        "secs_left": None if b.secsleft in (None, -1, -2) else int(b.secsleft),
    }


def snapshot() -> dict:
    """Single live sample. Callers poll this every few seconds."""
    # Non-blocking per-call sampling: interval=None compares against last call.
    cpu_total = psutil.cpu_percent(interval=None)
    per_core = psutil.cpu_percent(interval=None, percpu=True)
    vm = psutil.virtual_memory()
    du = psutil.disk_usage("C:\\")
    net = psutil.net_io_counters()
    freq = None
    try:
        f = psutil.cpu_freq()
        if f:
            freq = {"current_mhz": round(f.current, 1), "max_mhz": round(f.max or 0, 1)}
    except Exception:
        pass
    return {
        "simulated": False,
        "timestamp": time.time(),
        "cpu": {
            "total_pct": round(cpu_total, 1),
            "per_core_pct": [round(x, 1) for x in per_core],
            "logical": psutil.cpu_count(logical=True),
            "physical": psutil.cpu_count(logical=False),
            "freq": freq,
        },
        "memory": {
            "total_gb": round(vm.total / 1e9, 2),
            "used_gb": round(vm.used / 1e9, 2),
            "pct": round(vm.percent, 1),
        },
        "disk": {
            "total_gb": round(du.total / 1e9, 2),
            "used_gb": round(du.used / 1e9, 2),
            "pct": round(du.percent, 1),
        },
        "net": {
            "mb_sent": round(net.bytes_sent / 1e6, 2),
            "mb_recv": round(net.bytes_recv / 1e6, 2),
        },
        "battery": _battery(),
        "uptime_s": int(time.time() - _boot_time),
    }
