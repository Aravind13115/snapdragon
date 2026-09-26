"""Phase-1 placeholder classifier: transparent HEURISTIC, flagged simulated.

Replaced in Phase 2 by `OnnxClassifier(ProcessClassifier)` loading a real
.onnx model (CPU EP on x86_64, QNN EP routed via qnn_backend on ARM).
The dashboard reads the `simulated` flag to label this column honestly.
"""
from __future__ import annotations

from .base import ProcessClassifier

_RULES = (
    (("chrome", "msedge", "firefox", "opera", "brave"), "browser"),
    (("code", "devenv", "pycharm", "idea"), "dev-tool"),
    (("python", "node", "java", "dotnet"), "runtime"),
    (("svchost", "services", "lsass", "csrss", "wininit", "smss"), "system"),
    (("teams", "slack", "discord", "zoom"), "comms"),
    (("spotify", "steam", "vlc", "netflix"), "media"),
)


class HeuristicClassifier(ProcessClassifier):
    backend = "heuristic-stub"
    simulated = True

    def classify(self, process_name: str, cpu_pct: float) -> dict:
        low = (process_name or "").lower()
        for tokens, cat in _RULES:
            if any(t in low for t in tokens):
                return {"category": cat, "confidence": 0.5,
                        "backend": self.backend, "simulated": True}
        if (cpu_pct or 0) >= 20.0:
            return {"category": "high-cpu", "confidence": 0.4,
                    "backend": self.backend, "simulated": True}
        return {"category": "other", "confidence": 0.3,
                "backend": self.backend, "simulated": True}

    def status(self) -> dict:
        return {
            "backend": self.backend,
            "simulated": True,
            "loaded": True,   # the stub itself is loaded; the ONNX model is not
            "model_loaded": False,
            "detail": "Phase-1 heuristic. Phase 2 plugs in OnnxClassifier here.",
        }
