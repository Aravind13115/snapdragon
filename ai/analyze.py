"""Batch analysis: enrich telemetry rows with real model predictions.

    rows (Phase-1 telemetry) -> features.build() -> ONNX batch inference
      -> recommend.decide() -> explain.explain()

Attaches per row:
    row["arch"]  e.g. "x64", "ARM64 Native", "x86 (WOW64)", "Unknown"
    row["ai"]    {ai_class, confidence, probabilities, recommendation,
                  high_confidence, overridden, backend, simulated, why[]}

Plus summary(): class counts, avg confidence, latency, backend.
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import numpy as np

from ai import explain as _explain
from ai import features as _feat
from ai import recommend as _rec
from ai import safety as _safety


def enrich(rows: list[dict], classifier, host_is_arm: bool = False) -> dict:
    """Run the full pipeline over rows. Returns {rows, summary}."""
    if not rows:
        return {"rows": [], "summary": _empty_summary()}
    ctx = _feat.build_context()
    vecs, metas, targets = [], [], []
    for r in rows:
        # pid 0 (System Idle) and pid 4 (System) are kernel pseudo-processes,
        # not schedulable workloads: always PROTECT, never sent to the model.
        if r.get("pid") in (0, 4):
            r["arch"] = "x64" if not host_is_arm else "ARM64 Native"
            r["ai"] = {
                "ai_class": "PROTECTED", "model_class": "n/a (system)",
                "raw_confidence": 1.0, "familiarity": 1.0,
                "familiarity_level": "HIGH", "ood": False, "distance": 0.0,
                "final_confidence": 1.0,
                "probabilities": [1.0, 0.0, 0.0, 0.0],
                "recommendation": "PROTECT", "safety_state": "PROTECT",
                "high_confidence": False,
                "overridden": True,
                "override_reason": "kernel pseudo-process, not a workload",
                "backend": "rule", "simulated": False,
                "why": ["Kernel pseudo-process, not a schedulable workload",
                        "AI classification: PROTECTED -> PROTECT"],
            }
            continue
        try:
            from ai.features import _QUERY
            io_arg = r.pop("_io_total", _QUERY)  # sampler-cached, else live query
            v, m = _feat.build(r, ctx, host_is_arm, io_arg)
        except Exception:
            v = [0.0] * 11
            v[1] = 0.5
            m = {"arch": "Unknown", "is_foreground": False,
                 "unavailable": ["feature-build-failed"]}
        vecs.append(v)
        metas.append(m)
        targets.append(r)
    if not targets:
        return {"rows": rows, "summary": _summarize(rows, 0.0)}
    X = np.asarray(vecs, dtype=np.float32)
    labels, probs, dt_ms = classifier.predict_batch(X)

    for r, v, m, lab, pr in zip(targets, vecs, metas, labels, probs):
        i = int(lab)
        dec = _safety.finalize(r.get("name") or "?", i, float(pr[i]), v,
                               is_foreground=m.get("is_foreground", False))
        r["arch"] = m["arch"]
        r["ai"] = {
            "ai_class": dec["ai_class"],       # FINAL safety decision
            "model_class": dec["model_class"],  # raw model vote (may differ)
            "confidence": dec["final_confidence"],
            "raw_confidence": dec["raw_confidence"],
            "final_confidence": dec["final_confidence"],
            "familiarity": dec["familiarity"],
            "familiarity_level": dec["familiarity_level"],
            "ood": dec["ood"],
            "distance": dec["distance"],
            "probabilities": [round(float(p), 4) for p in pr],
            "recommendation": dec["recommendation"],
            "safety_state": dec["safety_state"],
            "high_confidence": dec["high_confidence"],
            "overridden": dec["overridden"],
            "override_reason": dec.get("override_reason", ""),
            "backend": getattr(classifier, "backend", "unknown"),
            "simulated": False,   # real model prediction + real rules
            "why": _explain.explain(v, m, dec["model_class"], dec["recommendation"])
            + [_safety_why(dec)],
        }
    return {"rows": rows, "summary": _summarize(rows, dt_ms)}


def _safety_why(dec: dict) -> str:
    if dec.get("overridden") and dec.get("override_reason"):
        return f"Safety decision: {dec['safety_state']} — {dec['override_reason']}"
    return (f"Safety decision: {dec['safety_state']} "
            f"(model {dec['model_class']} @ {dec['raw_confidence']}, "
            f"familiarity {dec['familiarity']} -> final {dec['final_confidence']})")


def _empty_summary() -> dict:
    return {"analyzed": 0, "counts": {c: 0 for c in _rec.CLASSES},
            "avg_confidence": 0.0, "latency_ms": 0.0, "simulated": False,
            "safety_states": {}, "ood_count": 0}


def _summarize(rows: list[dict], dt_ms: float) -> dict:
    from collections import Counter
    counts = {c: 0 for c in _rec.CLASSES}
    confs = []
    for r in rows:
        ai = r.get("ai")
        if not ai:
            continue
        counts[ai["ai_class"]] = counts.get(ai["ai_class"], 0) + 1
        confs.append(ai.get("final_confidence", ai.get("confidence", 0.0)))
    states = dict(Counter(r["ai"]["safety_state"] for r in rows if r.get("ai")))
    ood_n = sum(1 for r in rows if r.get("ai", {}).get("ood"))
    return {"analyzed": len(confs), "counts": counts,
            "avg_confidence": round(sum(confs) / len(confs), 4) if confs else 0.0,
            "latency_ms": round(dt_ms, 3), "simulated": False,
            "safety_states": states, "ood_count": ood_n}


# ------------------------------------------------------- diagnostic CLI ----

def diagnostic(top_n: int = 60) -> None:
    """python ai/analyze.py — model + live-evaluation diagnostic report."""
    import json
    from collections import Counter
    from pathlib import Path as _P

    from ai.dataset import FEATURES as _FEATS
    from inference.onnx_backend import OnnxClassifier
    from telemetry import process_list

    meta = json.loads((_P(__file__).resolve().parent.parent
                       / "models" / "model_metadata.json").read_text())
    assert meta["features"] == list(_FEATS), "metadata/dataset feature drift!"
    print("=== model ===")
    print(f"version: {meta['version']}  file: {meta['model_file']} "
          f"({meta['model_size_kb']} KB, opset {meta['opset']})")
    print(f"arch: {meta['architecture']}  classes: {meta['classes']}")
    print(f"n_features: {len(meta['features'])}")
    print("features: " + ", ".join(meta["features"]))
    print(f"normalization mean: {[round(v,3) for v in meta['normalization']['mean']]}")
    print(f"normalization scale: {[round(v,3) for v in meta['normalization']['scale']]}")
    print(f"temperature: {meta['calibration']['temperature']}  "
          f"threshold: {meta['confidence_threshold']}  "
          f"ood_threshold: {meta['ood_reference']['ood_threshold']}  "
          f"d_ref: {meta['ood_reference'].get('d_ref')}")
    print(f"synthetic test acc: {meta['test_accuracy']} "
          f"({meta['test_samples']} samples) — SYNTHETIC ONLY, not real-world")

    clf = OnnxClassifier()
    print(f"\n=== live evaluation (top {top_n} by CPU, observation-only) ===")
    res = process_list.top_processes(limit=200, sort="cpu")
    out = enrich(res["rows"][:top_n], clf)
    rows = out["rows"]
    states = Counter(r["ai"]["safety_state"] for r in rows)
    votes = Counter(r["ai"]["model_class"] for r in rows)
    finals = [r["ai"]["final_confidence"] for r in rows]
    fams = [r["ai"]["familiarity"] for r in rows]
    print(f"analyzed: {len(rows)}  model votes: {dict(votes)}")
    print(f"safety states: {dict(states)}")
    print(f"final_conf: mean={sum(finals)/len(finals):.3f} "
          f"hi(>=.85)={sum(1 for x in finals if x >= .85)} "
          f"mid={sum(1 for x in finals if .5 <= x < .85)} "
          f"lo={sum(1 for x in finals if x < .5)}")
    print(f"familiarity: mean={sum(fams)/len(fams):.3f} "
          f"OOD={sum(1 for r in rows if r['ai']['ood'])}")
    print("\n=== feature validation (top 8) ===")
    for r in rows[:8]:
        a = r["ai"]
        print(f"- {r['name']} pid={r['pid']} arch={r.get('arch')} "
              f"cpu={r['cpu_pct']}% mem={r['mem_pct']}%")
        print(f"  model={a['model_class']} raw={a['raw_confidence']} "
              f"fam={a['familiarity']}({a['familiarity_level']}) "
              f"final={a['final_confidence']} ood={a['ood']}")
        print(f"  decision={a['ai_class']} state={a['safety_state']} "
              f"rec={a['recommendation']}")
        if a.get("override_reason"):
            print(f"  reason: {a['override_reason']}")


if __name__ == "__main__":
    import sys as _sys
    from pathlib import Path as _P
    _sys.path.insert(0, str(_P(__file__).resolve().parent.parent))
    diagnostic()
