"""Live feature engineering: Phase-1 telemetry -> 11-element model vector.

Order MUST match ai/dataset.py FEATURES (the ONNX graph consumes raw
features; normalization + temperature are folded into the model).
v2: `is_protected` was REMOVED (label leakage — safety facts belong to
the deterministic safety layer, ai/safety.py, not the model).
    0  cpu_norm       cpu_pct (machine %) / 100
    1  cpu_trend      (cur - prev) mapped [-1,1] -> [0,1]; 0.5 = flat/unknown
    2  mem_norm       memory_percent / 100
    3  io_rate        disk io bytes/s, log-scaled; 0 + unavailable flag if denied
    4  net_level      inet connections for pid / 32 clamped; 0 if unavailable
    5  is_foreground  1 if pid owns the foreground window (ctypes, real)
    6  on_battery     1 if discharging (psutil, real)
    7  user_activity  from GetLastInputInfo idle time (real); 0.5 if unavailable
    8  arch_native    1 native-64 / 0.5 emulated-WOW64 / 0 unknown
    9  is_emulated    1 under emulation (ARM x86/x64, or WOW64 x86 on x64? no:
                       WOW64 is native execution -> 0; see arch_of())
    10 hist_cpu       EMA of cpu_pct; falls back to current cpu

Unavailable signals use safe defaults and are reported in `meta` —
never invented as hardware measurements.
"""
from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

import psutil

_hist: dict[int, dict] = {}   # pid -> {cpu, io, t, ema}
_arch_cache: dict[int, str] = {}
_NET_DIV = 32.0
_QUERY = object()  # sentinel: query io_counters live (default, Phase-2 behavior)
_HOST_MACHINE: int | None = None  # IMAGE_FILE_MACHINE_* of this host


def _host_machine() -> int:
    """IMAGE_FILE_MACHINE value of the host (learned from our own process)."""
    global _HOST_MACHINE
    if _HOST_MACHINE is not None:
        return _HOST_MACHINE
    try:
        k32 = ctypes.windll.kernel32
        pm, um = wintypes.USHORT(), wintypes.USHORT()
        if k32.IsWow64Process2(k32.GetCurrentProcess(),
                               ctypes.byref(pm), ctypes.byref(um)):
            _HOST_MACHINE = int(um.value) or int(pm.value)
        else:
            _HOST_MACHINE = 0x8664
    except Exception:
        _HOST_MACHINE = 0x8664
    return _HOST_MACHINE


_MACHINE_LABEL = {0xAA64: "ARM64", 0x8664: "x64", 0x14C: "x86", 0xA641: "ARM"}


# ------------------------------------------------------------- win32 ----

def foreground_pid() -> int | None:
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return int(pid.value) or None
    except Exception:
        return None


def idle_seconds() -> float | None:
    try:
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
            return None
        return max(0.0, (ctypes.windll.kernel32.GetTickCount() - lii.dwTime) / 1000.0)
    except Exception:
        return None


def arch_of(pid: int) -> str:
    """Best-effort per-process arch. 'Unknown' when the OS won't tell us."""
    if pid in _arch_cache:
        return _arch_cache[pid]
    label = "Unknown"
    try:
        k32 = ctypes.windll.kernel32
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if h:
            try:
                # Prefer IsWow64Process2 (arch-aware, Win10 1511+).
                try:
                    pm, um = wintypes.USHORT(), wintypes.USHORT()
                    if k32.IsWow64Process2(h, ctypes.byref(pm), ctypes.byref(um)):
                        # Empirical semantics: um==0 or um==host => native;
                        # um!=host => emulated/WOW64 guest `um` on host `pm`.
                        host = _host_machine()
                        umv, pmv = int(um.value), int(pm.value)
                        guest = umv if umv not in (0, host) else host
                        if guest == host:
                            label = (f"{_MACHINE_LABEL.get(host, '?')} Native"
                                     if host == 0xAA64 else _MACHINE_LABEL.get(host, "Unknown"))
                        elif host == 0x8664 and guest == 0x14C:
                            label = "x86 (WOW64)"   # native execution, 32-bit
                        else:
                            label = f"{_MACHINE_LABEL.get(guest, '?')} (Emulated)"
                    else:
                        raise OSError("no IsWow64Process2")
                except Exception:
                    wow = wintypes.BOOL()
                    if k32.IsWow64Process(h, ctypes.byref(wow)):
                        label = "x86 (WOW64)" if wow.value else "x64"
            finally:
                k32.CloseHandle(h)
    except Exception:
        pass
    if len(_arch_cache) < 4096:
        _arch_cache[pid] = label
    return label


def arch_features(arch_label: str, host_is_arm: bool) -> tuple[float, float]:
    if arch_label in ("ARM64 Native", "x64"):
        return 1.0, 0.0
    if arch_label == "x86 (WOW64)":
        return 0.5, 0.0   # WOW64 executes natively; not emulation
    if arch_label.endswith("(Emulated)"):
        return 0.5, 1.0
    return 0.0, 0.0       # Unknown: honest zeros


# -------------------------------------------------------------- build ----

def build_context() -> dict:
    """Per-sample O(1)-ish context shared by all processes in one sample."""
    try:
        b = psutil.sensors_battery()
        on_batt = bool(b is not None and not b.power_plugged)
    except Exception:
        on_batt, b = False, None
    idle = idle_seconds()
    if idle is None:
        user_act = 0.5
    elif idle < 15:
        user_act = 1.0
    else:
        user_act = max(0.0, 1.0 - idle / 300.0)
    net_counts: dict[int, int] = {}
    try:
        for c in psutil.net_connections(kind="inet"):
            if c.pid:
                net_counts[c.pid] = net_counts.get(c.pid, 0) + 1
    except Exception:
        pass
    return {"on_battery": on_batt, "fg_pid": foreground_pid(),
            "idle_s": idle, "user_activity": user_act,
            "net_counts": net_counts, "t": time.time()}


def build(row: dict, ctx: dict, host_is_arm: bool = False,
          io_total=_QUERY) -> tuple[list[float], dict]:
    """Feature vector + honesty metadata for one telemetry row.

    io_total: pass a sampler-cached disk total to avoid an extra
    io_counters() syscall per process (Phase 2.7 fast loop). _QUERY keeps
    the original live query; None marks disk_io unavailable.
    """
    pid = row.get("pid")
    name = row.get("name") or "?"
    cpu = max(0.0, float(row.get("cpu_pct") or 0.0))
    mem = max(0.0, float(row.get("mem_pct") or 0.0))
    now = ctx["t"]

    prev = _hist.get(pid, {})
    p_cpu = prev.get("cpu")
    trend = 0.5 if p_cpu is None else float(max(-1.0, min(1.0, (cpu - p_cpu) / 20.0)) + 1.0) / 2.0
    ema = cpu if prev.get("ema") is None else 0.5 * prev["ema"] + 0.5 * cpu

    io_rate, io_ok = 0.0, False
    if io_total is _QUERY:
        try:
            io = psutil.Process(pid).io_counters()
            total = (io.read_bytes or 0) + (io.write_bytes or 0)
            io_ok = True
            prev_io = total
        except Exception:
            total, prev_io = None, prev.get("io")
    elif isinstance(io_total, (int, float)):
        total, prev_io, io_ok = io_total, io_total, True
    else:
        total, prev_io = None, prev.get("io")
    if total is not None and "io" in prev and prev["io"] is not None:
        dt = max(0.5, now - prev.get("t", now - 4.0))
        rate = max(0.0, (total - prev["io"]) / dt)
        import math
        io_rate = min(1.0, math.log10(1 + rate) / 7.0)  # 10MB/s -> ~1.0

    net_n = ctx["net_counts"].get(pid, 0)
    net_level = min(1.0, net_n / _NET_DIV)

    arch_label = arch_of(pid) if isinstance(pid, int) else "Unknown"
    arch_nat, emu = arch_features(arch_label, host_is_arm)
    fg = 1.0 if ctx["fg_pid"] == pid else 0.0

    vec = [cpu / 100.0, trend, mem / 100.0, io_rate, net_level, fg,
           1.0 if ctx["on_battery"] else 0.0,
           ctx["user_activity"], arch_nat, emu, ema / 100.0]
    vec = [max(0.0, min(1.0, float(v))) for v in vec]

    _hist[pid] = {"cpu": cpu, "io": prev_io, "t": now, "ema": ema}
    if len(_hist) > 2048:  # bounded; drop oldest-ish
        for k in list(_hist)[:512]:
            _hist.pop(k, None)

    meta = {"arch": arch_label,
            "is_foreground": bool(fg),
            "unavailable": [s for s, ok in (("disk_io", io_ok),) if not ok]
            + ([] if ctx["net_counts"] else ["per_process_net"])
            + ([] if ctx["idle_s"] is not None else ["user_idle"])
            + ([] if ctx["fg_pid"] is not None else ["foreground"])}
    return vec, meta
