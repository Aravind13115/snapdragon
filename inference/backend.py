"""Inference-hardware selection: model vs. execution backend.

Preferred order:
    1. Snapdragon Hexagon NPU via Qualcomm QNN (QNNExecutionProvider)
    2. Other supported Windows ML / QNN paths (future)
    3. ONNX CPU fallback (development machines, e.g. this Intel PC)

On non-Snapdragon hardware this module reports CPU FALLBACK explicitly.
It NEVER presents the CPU backend as an NPU.
"""
from __future__ import annotations


def _ort_providers() -> list[str]:
    try:
        import onnxruntime as ort
        return list(ort.get_available_providers())
    except Exception:
        return []


def select(platform_report: dict, qnn_probe: dict) -> dict:
    providers = _ort_providers()
    if (qnn_probe.get("available") and "QNNExecutionProvider" in providers):
        selected, provider = "HEXAGON NPU", "QNNExecutionProvider"
    else:
        selected, provider = "CPU FALLBACK", "CPUExecutionProvider"
    if qnn_probe.get("available") and "QNNExecutionProvider" not in providers:
        note = ("Snapdragon host but onnxruntime has no QNNExecutionProvider; "
                "using CPU until a QNN EP build is installed.")
    elif selected == "CPU FALLBACK":
        note = ("No Snapdragon NPU on this host. CPU fallback is CORRECT here; "
                "the QNN/Hexagon path plugs in on Snapdragon hardware.")
    else:
        note = "Running on Hexagon NPU via QNN."
    return {
        "simulated": False,
        "selected_backend": selected,       # "CPU FALLBACK" | "HEXAGON NPU"
        "provider": provider,
        "inference": "LOCAL",
        "target_backend": "Qualcomm Hexagon NPU",
        "ort_providers": providers,
        "qnn_available": bool(qnn_probe.get("available")),
        "note": note,
    }
