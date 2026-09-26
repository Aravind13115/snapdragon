"""Prototype synthetic process dataset v2 — COMPETITION PROTOTYPE DATA.

WARNING: NOT production training data. Hand-designed, rule-based synthetic
workloads so the prototype can demonstrate:
    real telemetry -> features -> neural net -> ONNX -> classification.

v2 changes (Phase 2.5):
  * 11 features — `is_protected` REMOVED. It was label leakage: a
    deterministic safety fact the model could trivially memorize. Safety
    allowlisting stays in the deterministic safety layer (ai/safety.py),
    never in the model.
  * Diverse cross-archetypes per class so the model learns that CPU ALONE
    does not determine importance (low-CPU foreground, high-CPU
    background, disk-heavy, network-heavy, battery/AC, native/emulated).

Classes: 0=PROTECTED 1=USER_IMPORTANT 2=FLEXIBLE 3=DEFERRABLE.

Feature order (MUST match ai/features.py live builder):
    0  cpu_norm        5  is_foreground  9  is_emulated
    1  cpu_trend       6  on_battery     10 hist_cpu
    2  mem_norm        7  user_activity
    3  io_rate         8  arch_native
    4  net_level
"""
from __future__ import annotations

import numpy as np

DATASET_NAME = "prototype_synthetic_process_dataset"
DATASET_VERSION = "v2-diverse-noprotectflag"
N_FEATURES = 11
CLASS_NAMES = ["PROTECTED", "USER_IMPORTANT", "FLEXIBLE", "DEFERRABLE"]

FEATURES = [
    "cpu_norm", "cpu_trend", "mem_norm", "io_rate", "net_level",
    "is_foreground", "on_battery", "user_activity", "arch_native",
    "is_emulated", "hist_cpu",
]


def _clip(a):
    return np.clip(a, 0.0, 1.0)


def _bin(rng, n, p=0.5):
    return (rng.random(n) < p).astype(float)


def _arch(rng, n, native=0.8, emu=0.1):
    """(arch_native, is_emulated) with native/emu/unknown mix."""
    a = np.ones(n)
    e = np.zeros(n)
    r = rng.random(n)
    a[r > native + emu] = 0.0                       # unknown
    m = (r > native) & (r <= native + emu)
    a[m] = 0.5
    e[m] = 1.0
    return a, e


def generate(n_per_class: int = 1000, seed: int = 42):
    rng = np.random.default_rng(seed)
    n = n_per_class
    X = np.zeros((4 * n, N_FEATURES))
    y = np.zeros(4 * n, dtype=np.int64)

    def put(cls, i0, i1, col, vals):
        X[cls * n + i0:cls * n + i1, col] = vals

    # ---------------- CLASS 0: PROTECTED (system-shaped, no flag) ------
    # Mostly quiet + flat; a minority with cpu/io spikes so the model
    # cannot use "low cpu" as a protected shortcut either.
    nq, ns = int(n * 0.7), n - int(n * 0.7)
    for (a, b, cpu, io) in ((0, nq, (0.04, 0.04), (0.08, 0.08)),
                            (nq, n, (0.18, 0.10), (0.35, 0.15))):
        m = b - a
        put(0, a, b, 0, _clip(rng.normal(*cpu, m)))
        put(0, a, b, 1, _clip(rng.normal(0.5, 0.08, m)))
        put(0, a, b, 2, _clip(rng.normal(0.05, 0.04, m)))
        put(0, a, b, 3, _clip(rng.normal(*io, m)))
        put(0, a, b, 4, _clip(rng.normal(0.05, 0.06, m)))
        put(0, a, b, 10, _clip(rng.normal(cpu[0], 0.04, m)))
    put(0, 0, n, 5, np.zeros(n))
    put(0, 0, n, 6, _bin(rng, n))
    put(0, 0, n, 7, _clip(rng.normal(0.5, 0.3, n)))
    an, em = _arch(rng, n, 0.9, 0.05)
    put(0, 0, n, 8, an)
    put(0, 0, n, 9, em)
    y[0:n] = 0

    # ---------------- CLASS 1: USER_IMPORTANT ---------------------------
    # fg-highcpu 40% | fg-lowcpu 30% | bg-highcpu-interactive 15% | bg-net 15%
    segs = [(0.0, 0.40, True, (0.30, 0.12)), (0.40, 0.70, True, (0.05, 0.03)),
            (0.70, 0.85, False, (0.35, 0.12)), (0.85, 1.0, False, (0.12, 0.06))]
    for lo, hi, fg, (cm, cs) in segs:
        a, b = int(n * lo), int(n * hi)
        m = b - a
        put(1, a, b, 0, _clip(rng.normal(cm, cs, m)))
        put(1, a, b, 1, _clip(rng.normal(0.55, 0.15, m)))
        put(1, a, b, 2, _clip(rng.normal(0.20, 0.10, m)))
        put(1, a, b, 3, _clip(rng.normal(0.30, 0.18, m)))
        put(1, a, b, 4, _clip(rng.normal(0.45 if not fg else 0.35, 0.22, m)))
        put(1, a, b, 5, np.ones(m) if fg else _bin(rng, m, 0.1))
        put(1, a, b, 6, _bin(rng, m))
        put(1, a, b, 7, _clip(rng.normal(0.85, 0.15, m)))
        put(1, a, b, 10, _clip(rng.normal(cm, 0.10, m)))
    an, em = _arch(rng, n, 0.8, 0.12)
    put(1, 0, n, 8, an)
    put(1, 0, n, 9, em)
    y[n:2 * n] = 1

    # ---------------- CLASS 2: FLEXIBLE ---------------------------------
    # recurring-moderate 40% | burst-highcpu-bg 20% | net-heavy 20% |
    # dormant-quiet-bg 10% | emulated 10%
    segs = [(0.0, 0.4, (0.14, 0.08), 0.65, (0.45, 0.18), (0.55, 0.20), 0.30),
            (0.4, 0.6, (0.38, 0.10), 0.70, (0.50, 0.18), (0.55, 0.20), 0.30),
            (0.6, 0.8, (0.12, 0.06), 0.60, (0.45, 0.18), (0.70, 0.15), 0.35),
            (0.8, 0.9, (0.015, 0.012), 0.50, (0.05, 0.05), (0.20, 0.12), 0.70),
            (0.9, 1.0, (0.15, 0.08), 0.60, (0.40, 0.18), (0.50, 0.20), 0.30)]
    for lo, hi, (cm, cs), tr, (im, iss), (nm, ns), ua in segs:
        a, b = int(n * lo), int(n * hi)
        m = b - a
        put(2, a, b, 0, _clip(rng.normal(cm, cs, m)))
        put(2, a, b, 1, _clip(rng.normal(tr, 0.15, m)))
        put(2, a, b, 2, _clip(rng.normal(0.12, 0.07, m)))
        put(2, a, b, 3, _clip(rng.normal(im, iss, m)))
        put(2, a, b, 4, _clip(rng.normal(nm, ns, m)))
        put(2, a, b, 6, _bin(rng, m, 0.6))
        put(2, a, b, 7, _clip(rng.normal(ua, 0.20, m)))
        put(2, a, b, 10, _clip(rng.normal(cm, 0.07, m)))
    put(2, 0, n, 5, np.zeros(n))
    an, em = _arch(rng, n, 0.65, 0.20)
    put(2, 0, n, 8, an)
    put(2, 0, n, 9, em)
    y[2 * n:3 * n] = 2

    # ---------------- CLASS 3: DEFERRABLE -------------------------------
    # disk-heavy-idle 35% | quiet-bg-active-user 20% | quiet-unknown-arch 15%
    # tiny-telemetry 15% | low-cpu-bg 15%
    # The quiet segments mirror the most common LIVE region (near-zero
    # cpu/io) so the model meets real background processes in training
    # instead of extrapolating into them.
    segs = [(0.0, 0.35, (0.07, 0.05), (0.62, 0.18), 0.08, 0.15),
            (0.35, 0.55, (0.012, 0.010), (0.05, 0.05), 0.75, 0.05),
            (0.55, 0.70, (0.010, 0.008), (0.04, 0.04), 0.50, 0.04),
            (0.70, 0.85, (0.015, 0.010), (0.05, 0.05), 0.05, 0.10),
            (0.85, 1.0, (0.03, 0.02), (0.15, 0.10), 0.40, 0.12)]
    for lo, hi, (cm, cs), (im, iss), ua, nm in segs:
        a, b = int(n * lo), int(n * hi)
        m = b - a
        put(3, a, b, 0, _clip(rng.normal(cm, cs, m)))
        put(3, a, b, 1, _clip(rng.normal(0.50, 0.12, m)))
        put(3, a, b, 2, _clip(rng.normal(0.07, 0.05, m)))
        put(3, a, b, 3, _clip(rng.normal(im, iss, m)))
        put(3, a, b, 4, _clip(rng.normal(nm, 0.10, m)))
        put(3, a, b, 7, _clip(rng.normal(ua, 0.15, m)))
        put(3, a, b, 10, _clip(rng.normal(cm, 0.04, m)))
    put(3, 0, n, 5, np.zeros(n))
    put(3, 0, n, 6, _bin(rng, n, 0.5))
    an, em = _arch(rng, n, 0.65, 0.20)
    # quiet-unknown-arch segment: force arch_native=0 (OS-denied lookups)
    a, b = int(n * 0.55), int(n * 0.70)
    an[a:b] = 0.0
    em[a:b] = 0.0
    put(3, 0, n, 8, an)
    put(3, 0, n, 9, em)
    y[3 * n:4 * n] = 3

    idx = rng.permutation(len(y))
    return X[idx].astype(np.float32), y[idx]
