"""CPU-side inference benchmark + NPU measurement scaffold (Phase 4).

On Snapdragon hardware this module's NPU functions would measure QNN
execution; here every NPU field is honestly marked REQUIRES_SNAPDRAGON.
CPU measurements below are VERIFIED on the dev machine.

Usage: python -m inference.bench
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def cpu_bench(repeats: int = 500, batch: int = 64) -> dict:
    import onnxruntime as ort

    from inference.onnx_backend import OnnxClassifier
    t0 = time.perf_counter()
    clf = OnnxClassifier()
    load_ms = (time.perf_counter() - t0) * 1000.0
    rng = np.random.default_rng(0)
    X1 = rng.random((1, 11)).astype(np.float32)
    XB = rng.random((batch, 11)).astype(np.float32)
    clf.predict_batch(X1)  # warmup
    t = time.perf_counter()
    for _ in range(repeats):
        clf.predict_batch(X1)
    single_ms = (time.perf_counter() - t) / repeats * 1000.0
    t = time.perf_counter()
    for _ in range(max(1, repeats // 10)):
        clf.predict_batch(XB)
    batch_ms = (time.perf_counter() - t) / max(1, repeats // 10) * 1000.0
    return {
        "backend": "CPUExecutionProvider",
        "model_load_ms": round(load_ms, 2),
        "single_row_ms": round(single_ms, 4),
        f"batch{batch}_ms": round(batch_ms, 3),
        "per_row_in_batch_ms": round(batch_ms / batch, 4),
        "providers": ort.get_available_providers(),
        "status": "VERIFIED_MEASUREMENT",
    }


def npu_scaffold() -> dict:
    """Shape of the NPU comparison. Values require Snapdragon hardware."""
    import onnxruntime as ort
    from inference import backend as B
    from inference import qnn_backend
    from telemetry import platform_info
    plat = platform_info.detection()
    qnn = qnn_backend.probe(plat)
    sel = B.select(plat, qnn)
    return {
        "qnn_available": qnn["available"],
        "qnn_in_ort": "QNNExecutionProvider" in ort.get_available_providers(),
        "selected": sel["selected_backend"],
        "npu_latency_ms": "REQUIRES_SNAPDRAGON_HARDWARE",
        "npu_vs_cpu": "REQUIRES_SNAPDRAGON_HARDWARE",
        "status": ("READY" if qnn["available"] else
                   "ARCHITECTED / HARDWARE VALIDATION REQUIRED"),
    }


if __name__ == "__main__":
    import json
    print(json.dumps({"cpu": cpu_bench(), "npu": npu_scaffold()}, indent=2))
