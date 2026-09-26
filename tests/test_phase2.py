"""Phase-2 acceptance tests (stdlib unittest, no extra deps).

Covers the 10 required checks:
 1. ONNX model loads.                 6. Protected procs never get aggressive recs.
 2. Feature vector has 12 dims.       7. Missing telemetry does not crash inference.
 3. Class names match model output.   8. NPU-unavailable does not crash the app.
 4. Confidence in [0,1].              9. CPU fallback works.
 5. Low confidence -> REVIEW/PROTECT. 10. Demo mode is clearly marked.

Usage:
    python tests/test_phase2.py
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np

AGGRESSIVE = ("REDUCE BACKGROUND ACTIVITY", "DEFER WHEN APPROPRIATE")


class Phase2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from inference.onnx_backend import OnnxClassifier
        cls.clf = OnnxClassifier()
        cls.meta = json.loads((ROOT / "models" / "model_metadata.json").read_text())

    def test_01_model_loads(self):
        st = self.clf.status()
        self.assertTrue(st["loaded"] and st["model_loaded"])
        self.assertGreater(st["model_size_kb"], 0)

    def test_02_feature_dims(self):
        from ai.dataset import FEATURES, N_FEATURES
        from ai import features as F
        ctx = {"on_battery": False, "fg_pid": None, "idle_s": 5.0,
               "user_activity": 1.0, "net_counts": {}, "t": 1.0}
        vec, _ = F.build({"pid": -9999, "name": "test.exe",
                          "cpu_pct": 5.0, "mem_pct": 1.0}, ctx)
        self.assertEqual(len(vec), N_FEATURES)
        self.assertEqual(len(FEATURES), N_FEATURES)
        self.assertEqual(self.meta["features"], FEATURES)

    def test_03_class_names_match(self):
        from ai.dataset import CLASS_NAMES, N_FEATURES
        self.assertEqual(self.clf.status()["classes"], CLASS_NAMES)
        self.assertEqual(self.meta["classes"], CLASS_NAMES)
        labels, _, _ = self.clf.predict_batch(
            np.zeros((2, N_FEATURES), np.float32))
        for lab in labels:
            self.assertIn(int(lab), (0, 1, 2, 3))

    def test_04_confidence_range(self):
        from ai.dataset import generate
        X, _ = generate(n_per_class=25, seed=123)
        _, probs, _ = self.clf.predict_batch(X)
        self.assertTrue(((probs >= 0.0) & (probs <= 1.0)).all())
        self.assertTrue(np.allclose(probs.sum(axis=1), 1.0, atol=1e-4))

    def test_05_low_confidence_review(self):
        from ai import recommend
        d = recommend.decide("some.exe", 3, 0.40)
        self.assertEqual(d["recommendation"], "REVIEW / PROTECT")
        self.assertFalse(d["high_confidence"])

    def test_06_protected_never_aggressive(self):
        from ai import recommend
        for name in ("svchost.exe", "csrss.exe", "System", "lsass.exe"):
            d = recommend.decide(name, 3, 0.99, protected_flag=True)
            self.assertEqual(d["recommendation"], "PROTECT")
            self.assertNotIn(d["recommendation"], AGGRESSIVE)
        # Even if the model itself votes DEFERRABLE on an allowlisted name,
        # the safety override wins.
        d = recommend.decide("svchost.exe", 3, 0.99)
        self.assertEqual(d["ai_class"], "PROTECTED")
        self.assertEqual(d["recommendation"], "PROTECT")

    def test_07_missing_telemetry(self):
        from ai import analyze
        rows = [{"pid": -1, "name": None, "cpu_pct": None, "mem_pct": None,
                 "status": "?"}]
        out = analyze.enrich(rows, self.clf)
        self.assertIn("ai_class", out["rows"][0]["ai"])

    def test_08_npu_unavailable_ok(self):
        from inference import backend as B
        from inference import qnn_backend
        plat = {"is_arm": False, "is_snapdragon": False,
                "arch_normalized": "x86_64", "cpu_name": "test"}
        qnn = qnn_backend.probe(plat)
        self.assertFalse(qnn["available"])
        sel = B.select(plat, qnn)
        self.assertEqual(sel["selected_backend"], "CPU FALLBACK")

    def test_09_cpu_fallback(self):
        import onnxruntime as ort
        from ai.dataset import N_FEATURES
        self.assertIn("CPUExecutionProvider", ort.get_available_providers())
        d = self.clf.classify_features([0.0] * N_FEATURES)
        self.assertIn(d["category"], ("PROTECTED", "USER_IMPORTANT",
                                      "FLEXIBLE", "DEFERRABLE"))
        self.assertFalse(d["simulated"])  # real model output

    def test_10_demo_marked(self):
        from ai import demo
        out = demo.run_demo("presentation", self.clf)
        self.assertTrue(out["demo"] and out["simulated_processes"]
                        and out["real_model_predictions"])
        for r in out["rows"]:
            self.assertTrue(r["demo"])
            self.assertFalse(r["ai"]["simulated"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
