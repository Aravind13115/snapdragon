"""Demo mode: controlled synthetic workloads through the REAL model.

The processes are synthetic, but every classification is a genuine ONNX
model prediction over the stated feature vector. Rows are ALWAYS marked
demo:true / DEMO DATA and must never be mixed with live telemetry.
"""
from __future__ import annotations

# name, arch label, cpu%, 11-feature vector (see ai/dataset.py order;
# is_protected was removed in v2 — the safety layer allowlists by name)
_SETS = {
    "presentation": [
        ("PowerPoint.exe", "x64", 12.0,
         [0.12, 0.55, 0.18, 0.20, 0.10, 1.0, 0.0, 0.95, 1.0, 0.0, 0.10]),
        ("CloudSync.exe", "x64", 8.0,
         [0.08, 0.65, 0.10, 0.40, 0.60, 0.0, 0.0, 0.30, 1.0, 0.0, 0.12]),
        ("SearchIndexer.exe", "x64", 5.0,
         [0.05, 0.50, 0.06, 0.65, 0.05, 0.0, 0.0, 0.10, 1.0, 0.0, 0.05]),
        ("Browser.exe", "x64", 14.0,
         [0.14, 0.55, 0.22, 0.25, 0.50, 0.0, 0.0, 0.80, 1.0, 0.0, 0.15]),
    ],
    "gaming": [
        ("Game.exe", "x64", 45.0,
         [0.45, 0.60, 0.35, 0.30, 0.40, 1.0, 0.0, 1.00, 1.0, 0.0, 0.40]),
        ("Overlay.exe", "x64", 6.0,
         [0.06, 0.55, 0.08, 0.10, 0.30, 0.0, 0.0, 0.90, 1.0, 0.0, 0.06]),
        ("Updater.exe", "x86 (WOW64)", 4.0,
         [0.04, 0.50, 0.05, 0.30, 0.50, 0.0, 0.0, 0.20, 0.5, 0.0, 0.04]),
        ("TelemetrySvc.exe", "x64", 3.0,
         [0.03, 0.50, 0.04, 0.55, 0.20, 0.0, 0.0, 0.05, 1.0, 0.0, 0.03]),
    ],
    "battery": [
        ("Editor.exe", "x64", 18.0,
         [0.18, 0.55, 0.20, 0.20, 0.20, 1.0, 1.0, 0.95, 1.0, 0.0, 0.15]),
        ("CloudSync.exe", "x64", 11.0,
         [0.11, 0.70, 0.10, 0.45, 0.65, 0.0, 1.0, 0.25, 1.0, 0.0, 0.14]),
        ("Indexer.exe", "x64", 7.0,
         [0.07, 0.55, 0.07, 0.70, 0.05, 0.0, 1.0, 0.05, 1.0, 0.0, 0.06]),
        ("services.exe", "x64", 1.0,
         [0.01, 0.50, 0.03, 0.05, 0.02, 0.0, 1.0, 0.50, 1.0, 0.0, 0.01]),
    ],
    "idle": [
        ("System Idle Process", "x64", 90.0,
         [0.90, 0.50, 0.00, 0.00, 0.00, 0.0, 0.0, 0.00, 1.0, 0.0, 0.90]),
        ("BackgroundTask.exe", "x64", 2.0,
         [0.02, 0.50, 0.03, 0.40, 0.10, 0.0, 0.0, 0.05, 1.0, 0.0, 0.02]),
    ],
    # SIMULATED DEMO workload: SyncClient uses the FLEXIBLE class centroid
    # (most typical flexible shape in training) — it honestly earns
    # OPTIMIZATION CANDIDATE (verified: raw 0.9893 x fam 1.0). Mystery uses
    # an off-distribution vector and lands UNKNOWN/PROTECT. Neither row is
    # forced: thresholds unchanged, predictions from the real model.
    "workload": [
        ("SyncClient.exe", "x64", 15.0,
         [0.175, 0.642, 0.124, 0.43, 0.554, 0.0, 0.579, 0.359, 0.744, 0.209, 0.178]),
        ("Mystery.exe", "Unknown", 42.0,
         [0.99, 1.0, 0.99, 1.0, 1.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.99]),
    ],
}

DESCRIBE = {
    "presentation": "Foreground slides + background sync/indexer",
    "gaming": "Foreground game + overlay/updater/telemetry",
    "battery": "Active editor on battery + background tasks",
    "idle": "Mostly-idle machine",
    "workload": "SIMULATED DEMO: class-centroid flexible workload + unfamiliar contrast",
    # Phase-3 scenario sets: each documents its EXPECTED safety outcome.
    # Vectors verified against the real model/safety layer (no forcing).
    "sync": "SIMULATED DEMO: background sync on battery, familiar + recurring -> candidate",
    "active": "SIMULATED DEMO: foreground game, user active -> PROTECT",
    "uncertain": "SIMULATED DEMO: off-distribution workload -> PROTECT",
    "critical": "SIMULATED DEMO: allowlisted system service -> PROTECT",
}


def _extra_sets():
    return {
        "sync": [
            ("SyncService.exe", "x64", 11.0,
             [0.16, 0.65, 0.12, 0.44, 0.56, 0.0, 1.0, 0.33, 0.9, 0.1, 0.16]),
        ],
        "active": [
            ("Game.exe", "x64", 45.0,
             [0.45, 0.60, 0.35, 0.30, 0.40, 1.0, 0.0, 1.0, 1.0, 0.0, 0.40]),
        ],
        "uncertain": [
            ("MysterySvc.exe", "Unknown", 38.0,
             [0.90, 0.90, 0.80, 0.90, 0.90, 0.0, 0.5, 0.5, 0.0, 0.0, 0.80]),
        ],
        "critical": [
            ("services.exe", "x64", 1.0,
             [0.01, 0.50, 0.03, 0.05, 0.02, 0.0, 1.0, 0.50, 1.0, 0.0, 0.01]),
        ],
    }


def sets() -> dict:
    return {k: v for k, v in DESCRIBE.items()}


def run_demo(name: str, classifier) -> dict:
    """Classify a demo set with the real ONNX model. Always marked demo."""
    import numpy as np

    from ai import explain as _explain
    from ai import safety as _safety

    if name not in _SETS:
        extra = _extra_sets()
        if name in extra:
            entries = [(n, a, c, v) for n, a, c, v in extra[name]]
        else:
            name = "presentation"
            entries = _SETS[name]
    else:
        entries = _SETS[name]
    X = np.asarray([e[3] for e in entries], dtype=np.float32)
    labels, probs, dt_ms = classifier.predict_batch(X)
    rows = []
    for (pname, arch, cpu, vec), lab, pr in zip(entries, labels, probs):
        i = int(lab)
        dec = _safety.finalize(pname, i, float(pr[i]), vec,
                               is_foreground=vec[5] >= 0.5)
        rows.append({
            "pid": None, "name": pname, "arch": arch,
            "cpu_pct": cpu, "mem_pct": None, "status": "demo",
            "demo": True,
            "ai": {
                "ai_class": dec["ai_class"], "model_class": dec["model_class"],
                "confidence": dec["final_confidence"],
                "raw_confidence": dec["raw_confidence"],
                "final_confidence": dec["final_confidence"],
                "familiarity": dec["familiarity"],
                "familiarity_level": dec["familiarity_level"],
                "ood": dec["ood"], "distance": dec["distance"],
                "probabilities": [round(float(p), 4) for p in pr],
                "recommendation": dec["recommendation"],
                "safety_state": dec["safety_state"],
                "high_confidence": dec["high_confidence"],
                "overridden": dec["overridden"],
                "backend": getattr(classifier, "backend", "unknown"),
                "simulated": False,  # prediction is real; the process is demo
                "why": _explain.explain(vec, {"arch": arch, "unavailable": []},
                                        dec["model_class"], dec["recommendation"]),
            }})
    from ai.analyze import _summarize
    summary = _summarize(rows, dt_ms)
    summary["demo"] = True
    summary["demo_set"] = name
    return {"demo": True, "demo_set": name, "description": DESCRIBE[name],
            "simulated_processes": True, "real_model_predictions": True,
            "rows": rows, "summary": summary}
