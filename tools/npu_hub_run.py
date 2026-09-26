"""Hub-side staged validation driver (runs under the qai-hub venv python).

Flow: devices -> compile+link (target_runtime onnx) -> profile ->
inference (4 probes) -> staged JSON artifacts. No credentials in code;
auth comes from ~/.qai_hub/client.ini (user-configured, never committed).
Writes only non-sensitive artifacts to artifacts/npu_validation/.

Usage (from repo root):
    <venv>/python tools/npu_hub_run.py [--skip-inference]
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
ART = ROOT / "artifacts" / "npu_validation"

from tools.npu_validation import PROBES  # noqa: E402 (constants only)


def save(name: str, obj: dict) -> None:
    ART.mkdir(parents=True, exist_ok=True)
    (ART / name).write_text(json.dumps(obj, indent=2, default=str))


def main() -> int:
    import qai_hub as hub

    rec: dict = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                 "stages": {}}
    client = hub.Client()
    devices = client.get_devices()
    cands = []
    for d in devices:
        name, os_ = str(d.name), str(d.os)
        try:
            attrs = [str(a).lower() for a in (d.attributes or [])]
        except Exception:
            attrs = []
        blob = " ".join([name.lower()] + attrs)
        # API os is version-only ('11'); family comes from attributes.
        if ("os:windows" not in attrs and "windows" not in blob):
            continue
        if "snapdragon" not in blob and "snapdragon" not in name.lower():
            continue
        score = ("x elite" in name.lower()) + ("crd" in name.lower())
        cands.append((score, d))
    cands.sort(key=lambda c: c[0], reverse=True)
    winsnap = [{"name": str(d.name), "os": str(d.os),
                "attributes": sorted(str(a).lower() for a in (d.attributes or []))}
               for _, d in cands]
    save("devices.json", {"windows_snapdragon": winsnap,
                          "total_devices": len(devices)})
    rec["stages"]["devices_listed"] = len(devices)
    if not winsnap:
        rec.update({"status": "BLOCKED",
                    "reason": "no Windows Snapdragon target among Hub devices"})
        save("hub_flow.json", rec)
        print(json.dumps(rec, indent=2))
        return 2
    target = next((d for d in winsnap if "x elite" in d["name"].lower()),
                  winsnap[0])
    target_obj = next((d for _, d in cands if str(d.name) == target["name"]),
                      cands[0][1])
    rec["target"] = target

    resume_id = next((a for a in sys.argv[1:] if a.startswith("j")), None)
    if resume_id:
        cjob = client.get_job(resume_id)
        rec["compile"] = {"job_id": resume_id, "resumed": True,
                          "device": target["name"]}
    else:
        jobs = client.submit_compile_and_link_jobs(
            models=str(ROOT / "models" / "process_classifier.onnx"),
            device=target_obj,
            # --truncate_64bit_io REQUIRED: ArgMax emits int64 `label`;
            # flag converts it to int32 at compile time (no retrain needed;
            # app consumes labels via int(), dtype-agnostic).
            compile_options="--target_runtime onnx --truncate_64bit_io",
            input_specs={"features": (1, 11)},
            embed_in_onnx=True,
            name="process-classifier-snapdragon")
        first = jobs[0] if isinstance(jobs, list) else jobs
        cjob = first[0][0] if isinstance(first, tuple) else first
        cjob.wait()
        rec["compile"] = {"job_id": getattr(cjob, "job_id", str(cjob)),
                          "status": str(cjob.get_status()),
                          "device": target["name"],
                          "runtime": "onnx",
                          "model": "models/process_classifier.onnx"}
        save("compile_result.json", rec["compile"])
    tmodel = cjob.get_target_model()
    tmodel.download(str(ART / "qnn_target_model"))
    rec["stages"]["compiled"] = True

    pjob = client.submit_profile_job(
        model=tmodel, device=target_obj,
        name="process-classifier-profile")
    pjob.wait()
    prof = pjob.download_profile()
    items = dict(prof.items()) if hasattr(prof, "items") else {}
    # Compute unit lives per-node in execution_detail (list of dicts);
    # all-NPU means NPU execution. Check top-level key first.
    units = set()
    try:
        import ast as _ast
        det = items.get("execution_detail", "")
        if isinstance(det, str) and det.startswith("["):
            for row in _ast.literal_eval(det):
                if isinstance(row, dict) and row.get("compute_unit"):
                    units.add(str(row["compute_unit"]))
    except Exception:
        pass
    cu = str(items.get("compute_unit",
                       "NPU" if units and units == {"NPU"} else "UNKNOWN"))
    rec["profile"] = {"job_id": getattr(pjob, "job_id", str(pjob)),
                      "status": str(pjob.get_status()),
                      "compute_unit": cu,
                      "node_compute_units": sorted(units) or None,
                      "detail": {k: str(v) for k, v in list(items.items())[:20]}}
    save("profile_result.json", rec["profile"])
    rec["stages"]["profiled"] = True

    import numpy as _np
    if "--infer-only" in sys.argv:
        # Reuse an already-compiled job's target model (no resubmission):
        #   npu_hub_run.py --infer-only <compile_job_id>
        jid = next(a for a in sys.argv[1:] if a.startswith("j"))
        tmodel = client.get_job(jid).get_target_model()
        try:
            saved = json.loads((ART / "profile_result.json").read_text())
            import ast as _ast2
            det = saved.get("detail", {}).get("execution_detail", "")
            units2 = set()
            if isinstance(det, str) and det.startswith("["):
                for row in _ast2.literal_eval(det):
                    if isinstance(row, dict) and row.get("compute_unit"):
                        units2.add(str(row["compute_unit"]))
            if units2 == {"NPU"}:
                saved["compute_unit"] = "NPU"
                saved["node_compute_units"] = ["NPU"]
            rec["profile"] = saved
        except (OSError, ValueError):
            pass
    if "--skip-inference" not in sys.argv:
        # Compiled graph fixes batch=1 (input spec (1,11)): send one
        # (1,11) batch per probe, not a single (4,11) batch.
        batches = [_np.asarray(v, dtype=_np.float32).reshape(1, 11)
                   for v in PROBES.values()]
        ijob = client.submit_inference_job(
            model=tmodel, device=target_obj,
            inputs={"features": batches}, name="process-classifier-infer")
        ijob.wait()
        raw = ijob.download_output_data()
        # Return shape varies: dict {output_0: [probs...], output_1: [labels...]}
        # or array. Disambiguate by element count (4-vectors are probs).
        if isinstance(raw, dict):
            prob_rows, lab_rows = None, None
            for _k, _v in raw.items():
                arrs = [_np.asarray(a, dtype=float).ravel() for a in _v]
                if arrs and all(a.size == 4 for a in arrs):
                    prob_rows = arrs
                else:
                    lab_rows = arrs
            rows = {}
            for n, pr in zip(PROBES, prob_rows or []):
                rows[n] = [round(float(x), 6) for x in pr[:4]]
            out_labels = [int(a[0]) for a in (lab_rows or [])]
        else:
            out = _np.asarray(raw)
            rows = {n: [round(float(x), 6) for x in row[:4]]
                    for n, row in zip(PROBES, out.reshape(len(PROBES), -1))}
            out_labels = None
        rec["inference"] = {"job_id": getattr(ijob, "job_id", str(ijob)),
                            "status": str(ijob.get_status()),
                            "output_shape": "per-probe [4] + label",
                            "rows": rows}
        if out_labels is not None:
            rec["inference"]["labels"] = out_labels
        save("inference_result_npu.json", rec["inference"])
        rec["stages"]["inference"] = True

    cu = rec.get("profile", {}).get("compute_unit", "UNKNOWN")
    rec["status"] = "NPU_VERIFIED" if "NPU" in cu.upper() else "PROFILED_NON_NPU"
    save("hub_flow.json", rec)
    print(json.dumps(rec, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
