"""Classifier interface for later phases.

Phase 2 drops in an ONNX model behind this ABC without touching
telemetry/ or the dashboard. Phase 3 adds a QNN implementation
for Hexagon NPU inference.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class ProcessClassifier(ABC):
    backend: str = "undefined"
    simulated: bool = True

    @abstractmethod
    def classify(self, process_name: str, cpu_pct: float) -> dict:
        """Return {"category": str, "confidence": float, "backend": str, "simulated": bool}."""
        raise NotImplementedError

    def status(self) -> dict:
        return {"backend": self.backend, "simulated": self.simulated,
                "loaded": False, "detail": "base class"}
