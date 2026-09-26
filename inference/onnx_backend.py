"""Real ONNX inference backend (Phase 2).

Loads models/process_classifier.onnx in ONNX Runtime and classifies RAW
11-element feature vectors (normalization + temperature are folded into
the graph). ORT outputs calibrated probabilities; the safety layer
(ai/safety.py) multiplies by data familiarity — raw softmax is NEVER
treated as trustworthy confidence.

Conforms to inference/base.py::ProcessClassifier so Phase-1 call sites
and the dashboard keep working; `simulated` is False when the model is
loaded. If the model file is missing, construction raises — the app
then falls back to HeuristicClassifier with explicit "stub" marking
(see app.py), never pretending the stub is the model.
"""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from .base import ProcessClassifier

ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = ROOT / "models" / "process_classifier.onnx"

CLASSES = ["PROTECTED", "USER_IMPORTANT", "FLEXIBLE", "DEFERRABLE"]


class OnnxClassifier(ProcessClassifier):
    backend = "onnx-cpu"
    simulated = False

    def __init__(self, model_path: Path | str = MODEL_PATH):
        import onnxruntime as ort

        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(f"ONNX model not found: {self.model_path}")
        self.session = ort.InferenceSession(
            str(self.model_path), providers=["CPUExecutionProvider"])
        self._input = self.session.get_inputs()[0].name
        self.model_size_kb = round(self.model_path.stat().st_size / 1024, 1)
        self.last_latency_ms: float | None = None

    # -- batch API (preferred: one ORT call for N processes) --
    def predict_batch(self, X: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
        """Returns (labels[N], probabilities[N,4], latency_ms)."""
        X = np.ascontiguousarray(X, dtype=np.float32)
        t = time.perf_counter()
        probs, labels = self.session.run(None, {self._input: X})
        dt_ms = (time.perf_counter() - t) * 1000.0
        self.last_latency_ms = dt_ms
        return np.asarray(labels), np.asarray(probs, dtype=float), dt_ms

    def classify_features(self, vec) -> dict:
        labels, probs, dt = self.predict_batch(np.asarray(vec, dtype=np.float32).reshape(1, -1))
        i = int(labels[0])
        return {"category": CLASSES[i], "class_id": i,
                "confidence": round(float(probs[0, i]), 4),
                "probabilities": [round(float(p), 4) for p in probs[0]],
                "backend": self.backend, "simulated": False,
                "latency_ms": round(dt, 3)}

    # -- ProcessClassifier interface (heuristic-free; features unknown here) --
    def classify(self, process_name: str, cpu_pct: float) -> dict:
        raise NotImplementedError(
            "OnnxClassifier needs a full 11-feature vector; use "
            "classify_features() or ai.analyze.enrich().")

    def status(self) -> dict:
        return {
            "backend": self.backend,
            "simulated": False,
            "loaded": True,
            "model_loaded": True,
            "model_path": str(self.model_path),
            "model_size_kb": self.model_size_kb,
            "classes": CLASSES,
            "last_latency_ms": self.last_latency_ms,
            "detail": "Real ONNX model (prototype MLP). Predictions come from the model.",
        }
