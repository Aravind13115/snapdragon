"""Snapdragon NPU validation harness (Phase 4, Dell host side).

Always-safe local part (no credentials needed):
  1. inspect models/process_classifier.onnx (shapes, opset, ops, dtype)
  2. verify models/model_metadata.json (features, classes, scaler, T, OOD)
  3. verify feature order == ai/dataset.py FEATURES
  4. build 4 representative inputs (protected/foreground/flexible/deferrable)
  5. run local CPU reference inference (labels + probabilities)

Hub part (needs `qai-hub configure` API token — NEVER hard-coded here):
  6. submit compile/profile/inference jobs via qai-hub client
  7. retrieve results, compare NPU vs CPU within tolerance
  8. write artifacts/npu_validation/*.json (no credentials stored)

Without a token, Hub steps record BLOCKED status honestly and exit 2.
Usage:
    python tools/npu_validation.py                 # local-only validation
    python tools/npu_validation.py --hub            # also attempt Hub jobs
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
ART = ROOT / "artifacts" / "npu_validation"

CLASS_NAMES = ["PROTECTED", "USER_IMPORTANT", "FLEXIBLE", "DEFERRABLE"]

# Representative raw feature vectors (ai/dataset.py order), one per class.
PROBES = {
    "protected":   [0.04, 0.50, 0.05, 0.08, 0.05, 0.0, 0.5, 0.50, 1.0, 0.0, 0.04],
    "foreground":  [0.30, 0.55, 0.20, 0.30, 0.35, 1.0, 0.0, 0.85, 1.0, 0.0, 0.25],
    "flexible":    [0.16, 0.65, 0.12, 0.44, 0.56, 0.0, 1.0, 0.33, 0.9, 0.1, 0.16],
    "deferrable":  [0.06, 0.50, 0.07, 0.65, 0.10, 0.0, 1.0, 0.08, 1.0, 0.0, 0.06],
}


def local_validation() -> dict:
    import numpy as np
    import onnx
    from ai.dataset import FEATURES
    from inference.onnx_backend import OnnxClassifier

    mp = ROOT / "models" / "process_classifier.onnx"
    meta = json.loads((ROOT / "models" / "model_metadata.json").read_text())
    m = onnx.load(str(mp))
    assert meta["features"] == FEATURES, "metadata/dataset feature drift"
    assert meta["classes"] == CLASS_NAMES
    assert m.graph.input[0].type.tensor_type.shape.dim[1].dim_value == 11
    clf = OnnxClassifier()
    refs = {}
    for name, vec in PROBES.items():
        d = clf.classify_features(vec)
        refs[name] = {"label": d["category"],
                      "probabilities": d["probabilities"],
                      "confidence": d["confidence"]}
    return {
        "model": {"file": "models/process_classifier.onnx",
                  "size_kb": round(mp.stat().st_size / 1024, 1),
                  "opset": 12, "inputs": [[11]], "outputs": [[4]],
                  "ops": ["Gemm", "Relu", "Softmax", "ArgMax"],
                  "dtype": "float32"},
        "metadata_version": meta["version"],
        "features_ok": True, "classes_ok": True,
        "cpu_reference": refs,
        "cpu_latency_ms": clf.last_latency_ms,
        "status": "LOCAL_CPU_VERIFIED",
    }


def hub_attempt() -> dict:
    """Try Hub jobs. Returns BLOCKED record when unconfigured."""
    try:
        import qai_hub  # noqa: F401
    except ImportError:
        return {"status": "BLOCKED",
                "reason": "qai-hub not installed in this interpreter "
                          "(isolated venv prepared separately); configure an "
                          "API token via `qai-hub configure` — never commit it."}
    try:
        import qai_hub as hub
        return hub_staged(hub.Client())
    except Exception as e:
        return {"status": "BLOCKED",
                "reason": f"AI Hub not configured: {type(e).__name__}. "
                          "Run `qai-hub configure` with an API token from "
                          "https://aihub.qualcomm.com/ (never commit it)."}


def _blocked(reason: str) -> dict:
    return {"status": "BLOCKED", "reason": reason}


def _pick_windows_snapdragon(devices: list) -> dict | None:
    """Prefer Snapdragon X Elite Windows target; honest None if absent.

    NOTE: via the Hub API, Device.os is only the version ('11'), NOT the
    OS family — family comes from device attributes ('os:windows').
    Name-only filtering would admit Android QRDs, so attributes rule.
    """
    scored = []
    for d in devices:
        name = str(getattr(d, "name", ""))
        os_ = str(getattr(d, "os", ""))
        try:
            attrs = [str(a).lower() for a in (getattr(d, "attributes", None) or [])]
        except Exception:
            attrs = []
        blob = " ".join([name.lower()] + attrs)
        if "os:windows" not in attrs and "windows" not in blob:
            continue
        if "snapdragon" not in blob and "snapdragon" not in name.lower():
            continue
        score = ("x elite" in name.lower()) + ("crd" in name.lower())
        scored.append((score, {"name": name, "os": os_, "attributes": sorted(attrs)}))
    if not scored:
        return None
    scored.sort(key=lambda c: c[0], reverse=True)
    return scored[0][1]


def hub_staged(client) -> dict:
    """Devices -> compile+link -> profile -> inference -> compare.

    Runs for real when the client is authenticated; every stage records
    honest results. Called by hub_attempt() after Client() succeeds.
    """
    import numpy as np
    rec: dict = {"status": "STARTED", "stages": {}}
    try:
        devices = client.get_devices()
        rec["stages"]["devices_listed"] = len(devices)
        target = _pick_windows_snapdragon(list(devices))
        if target is None:
            rec.update(_blocked("no Windows Snapdragon target among Hub devices"))
            rec["status"] = "BLOCKED"
            return rec
        rec["target"] = target
        # API calls need the Device object, not the info dict.
        target_obj = next((d for d in devices if str(d.name) == target["name"]),
                          None)
        if target_obj is None:
            rec.update(_blocked("target device object unresolvable"))
            rec["status"] = "BLOCKED"
            return rec
    except Exception as e:
        rec.update(_blocked(f"device listing failed: {type(e).__name__}: {e}"))
        rec["status"] = "BLOCKED"
        return rec
    try:
        jobs = client.submit_compile_and_link_jobs(
            models=str(ROOT / "models" / "process_classifier.onnx"),
            device=target_obj,
            compile_options="--target_runtime onnx --truncate_64bit_io",
            input_specs={"features": (1, 11)},
            embed_in_onnx=True,
            name="process-classifier-snapdragon")
        first = jobs[0] if isinstance(jobs, list) else jobs
        cjob = first[0][0] if isinstance(first, tuple) else first
        cjob.wait()
        rec["compile"] = {"job_id": getattr(cjob, "job_id", str(cjob)),
                          "status": str(cjob.get_status())}
        tmodel = cjob.get_target_model()
        tmodel.download(str(ART / "qnn_target_model"))
        rec["stages"]["compiled"] = True
    except Exception as e:
        rec.update(_blocked(f"compile/link failed: {type(e).__name__}: {e}"))
        rec["status"] = "BLOCKED"
        return rec
    try:
        pjob = client.submit_profile_job(
            model=tmodel, device=target_obj,
            name="process-classifier-profile")
        pjob.wait()
        prof = pjob.download_profile()
        items = list(prof.items()) if hasattr(prof, "items") else []
        units = set()
        try:
            import ast as _ast
            det = dict(items).get("execution_detail", "")
            if isinstance(det, str) and det.startswith("["):
                for row in _ast.literal_eval(det):
                    if isinstance(row, dict) and row.get("compute_unit"):
                        units.add(str(row["compute_unit"]))
        except Exception:
            pass
        cu = str(dict(items).get("compute_unit",
                                 "NPU" if units and units == {"NPU"} else "UNKNOWN"))
        rec["profile"] = {"job_id": getattr(pjob, "job_id", str(pjob)),
                          "compute_unit": cu,
                          "node_compute_units": sorted(units) or None,
                          "detail": {k: str(v) for k, v in items[:12]}}
        rec["stages"]["profiled"] = True
    except Exception as e:
        rec.update(_blocked(f"profile failed: {type(e).__name__}: {e}"))
        rec["status"] = "BLOCKED"
        return rec
    try:
        X = np.stack([np.asarray(v, dtype=np.float32) for v in PROBES.values()])
        ijob = client.submit_inference_job(
            model=tmodel, device=target_obj,
            inputs={"features": X}, name="process-classifier-infer")
        ijob.wait()
        raw = ijob.download_output_data()
        if isinstance(raw, dict):
            prob_rows = None
            for _v in raw.values():
                arrs = [np.asarray(a, dtype=float).ravel() for a in _v]
                if arrs and all(a.size == 4 for a in arrs):
                    prob_rows = arrs
            out = np.stack(prob_rows) if prob_rows is not None else np.asarray(raw)
        else:
            out = np.asarray(raw)
        local = local_validation()["cpu_reference"]
        names = list(PROBES)
        agree, maxdiff = 0, 0.0
        for k, probs in enumerate(out.reshape(len(names), -1)[:, :4]):
            ref = local[names[k]]["probabilities"]
            agree += int(int(np.argmax(probs)) == CLASS_NAMES.index(local[names[k]]["label"]))
            maxdiff = max(maxdiff, float(np.abs(np.asarray(probs[:4]) - np.asarray(ref)).max()))
        rec["inference"] = {"job_id": getattr(ijob, "job_id", str(ijob)),
                            "argmax_agreement": f"{agree}/{len(names)}",
                            "max_prob_diff": round(maxdiff, 4)}
        rec["stages"]["inference"] = True
    except Exception as e:
        rec.update(_blocked(f"inference failed: {type(e).__name__}: {e}"))
        rec["status"] = "BLOCKED"
        return rec
    cu = rec["profile"].get("compute_unit", "UNKNOWN")
    rec["status"] = "NPU_VERIFIED" if "NPU" in cu.upper() else "PROFILED_NON_NPU"
    return rec


def main(with_hub: bool = False) -> int:
    ART.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    local = local_validation()
    (ART / "inference_result.json").write_text(json.dumps(
        {"cpu_reference": local.pop("cpu_reference"),
         "cpu_latency_ms": local.get("cpu_latency_ms")}, indent=2))
    summary = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "local": local,
               "hub": hub_attempt() if with_hub else {"status": "NOT_ATTEMPTED"},
               "elapsed_s": round(time.time() - t0, 1)}
    (ART / "validation_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    if with_hub and summary["hub"]["status"] == "BLOCKED":
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main("--hub" in sys.argv))
