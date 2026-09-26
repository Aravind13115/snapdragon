"""Phase-2.5 safety/calibration tests (stdlib unittest).

 1. Low confidence -> PROTECT            6. Raw prob cannot bypass safety
 2. OOD -> PROTECT                       7. Missing features don't crash
 3. Foreground -> PROTECT                8. Train/inference normalization identical
 4. Protected -> PROTECT                 9. Class ordering correct
 5. Familiar high-conf -> eligible rec   10. No classification collapse

Usage:  python tests/test_phase25.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

AGGRESSIVE_STATES = ("OPTIMIZATION CANDIDATE",)


class Phase25(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from inference.onnx_backend import OnnxClassifier
        cls.clf = OnnxClassifier()

    def _vec(self, **kw):
        from ai.dataset import N_FEATURES
        v = [0.02, 0.5, 0.03, 0.05, 0.05, 0.0, 0.0, 0.5, 1.0, 0.0, 0.02]
        assert len(v) == N_FEATURES
        for k, val in kw.items():
            v[{"cpu": 0, "fg": 5, "user": 7}[k]] = val
        return v

    def _fin(self, name, vec):
        from ai import safety
        lab, prob, _ = self.clf.predict_batch(
            np.asarray(vec, dtype=np.float32).reshape(1, -1))
        return safety.finalize(name, int(lab[0]), float(prob[0, int(lab[0])]),
                               vec, is_foreground=vec[5] >= 0.5)

    def test_1_low_confidence_protect(self):
        from ai import safety
        d = safety.finalize("some.exe", 3, 0.30, self._vec())
        self.assertEqual(d["recommendation"], "PROTECT")
        self.assertNotIn(d["safety_state"], AGGRESSIVE_STATES)

    def test_2_ood_protect(self):
        from ai import ood, safety
        wild = [0.99, 1.0, 0.99, 1.0, 1.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.99]
        fam = ood.familiarity(wild)
        self.assertTrue(fam["ood"], f"expected OOD, got {fam}")
        d = self._fin("weird.exe", wild)
        self.assertTrue(d["ood"])
        self.assertEqual(d["safety_state"], "PROTECT")
        self.assertEqual(d["ai_class"], "UNKNOWN")

    def test_3_foreground_protect(self):
        d = self._fin("game.exe", self._vec(fg=1.0, cpu=0.45, user=1.0))
        self.assertEqual(d["safety_state"], "PROTECT")
        self.assertEqual(d["recommendation"], "PROTECT")

    def test_4_protected_protect(self):
        for name in ("svchost.exe", "csrss.exe", "services.exe"):
            d = self._fin(name, self._vec())
            self.assertEqual(d["safety_state"], "PROTECT")
            self.assertEqual(d["ai_class"], "PROTECTED")

    def test_5_familiar_highconf_eligible(self):
        from ai import demo
        out = demo.run_demo("presentation", self.clf)
        states = {r["ai"]["safety_state"] for r in out["rows"]}
        # Familiar archetypes must be able to earn more than PROTECT.
        self.assertTrue(states & {"OBSERVE", "REVIEW", "OPTIMIZATION CANDIDATE"},
                        f"demo states stuck at PROTECT: {states}")

    def test_6_raw_prob_cannot_bypass(self):
        from ai import safety
        # Even a 0.9999 DEFERRABLE vote on an allowlisted process: PROTECT.
        d = safety.finalize("svchost.exe", 3, 0.9999, self._vec())
        self.assertEqual(d["safety_state"], "PROTECT")
        # ... and on an OOD vector.
        wild = [0.99, 1.0, 0.99, 1.0, 1.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.99]
        d = safety.finalize("weird.exe", 3, 0.9999, wild)
        self.assertEqual(d["safety_state"], "PROTECT")

    def test_7_missing_features_ok(self):
        from ai import analyze
        rows = [{"pid": -1, "name": None, "cpu_pct": None, "mem_pct": None,
                 "status": "?"}]
        out = analyze.enrich(rows, self.clf)
        self.assertIn("safety_state", out["rows"][0]["ai"])

    def test_8_normalization_identical(self):
        import json
        from ai import ood
        meta = json.loads((ROOT / "models" / "model_metadata.json").read_text())
        self.assertTrue(np.allclose(ood._mean, meta["normalization"]["mean"]))
        self.assertTrue(np.allclose(ood._scale, meta["normalization"]["scale"]))
        # Standardizing the training mean must give ~zero vector.
        self.assertTrue(np.allclose(ood.standardize(ood._mean),
                                    np.zeros_like(ood._mean), atol=1e-9))

    def test_9_class_ordering(self):
        from ai.dataset import CLASS_NAMES
        self.assertEqual(CLASS_NAMES,
                         ["PROTECTED", "USER_IMPORTANT", "FLEXIBLE", "DEFERRABLE"])
        self.assertEqual(self.clf.status()["classes"], CLASS_NAMES)

    def test_10_no_collapse(self):
        from ai.dataset import generate
        X, _ = generate(n_per_class=100, seed=777)
        labs, _, _ = self.clf.predict_batch(X)
        frac = max((labs == c).mean() for c in range(4))
        self.assertLess(frac, 0.90, f"model collapsed: {frac:.2f} in one class")


if __name__ == "__main__":
    unittest.main(verbosity=2)
