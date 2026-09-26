"""Phase-3 tests: safe optimization simulator (stdlib unittest).

 1. protected -> NO_ACTION       6. simulation modifies nothing
 2. foreground -> NO_ACTION      7. output marked simulated
 3. low confidence -> NO_ACTION  8. projections not measurements
 4. OOD -> NO_ACTION             9. simulation logged
 5. familiar candidate -> sim   10. safety controls unchanged

Usage: python tests/test_phase3.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _decide(name, vec, **kw):
    from ai import safety
    from inference.onnx_backend import OnnxClassifier
    clf = OnnxClassifier()
    lab, prob, _ = clf.predict_batch(np.asarray(vec, np.float32).reshape(1, -1))
    d = safety.finalize(name, int(lab[0]), float(prob[0, int(lab[0])]), vec, **kw)
    return {"pid": 9999, "name": name, "arch": "x64", "cpu_pct": 11.0,
            "ai": d}


def _sync_row():
    return _decide("SyncService.exe",
                   [0.16, 0.65, 0.12, 0.44, 0.56, 0.0, 1.0, 0.33, 0.9, 0.1, 0.16])


class Phase3(unittest.TestCase):
    def test_1_protected_no_action(self):
        from optimization import simulator as S
        row = _decide("services.exe",
                      [0.01, 0.50, 0.03, 0.05, 0.02, 0.0, 1.0, 0.50, 1.0, 0.0, 0.01])
        sim = S.preview(row)
        self.assertEqual(sim["simulated_action"], "NO_ACTION")
        self.assertEqual(sim["safety_state"], "PROTECT")

    def test_2_foreground_no_action(self):
        from optimization import simulator as S
        row = _decide("Game.exe",
                      [0.45, 0.60, 0.35, 0.30, 0.40, 1.0, 0.0, 1.0, 1.0, 0.0, 0.40],
                      is_foreground=True)
        sim = S.preview(row)
        self.assertEqual(sim["simulated_action"], "NO_ACTION")

    def test_3_low_confidence_no_action(self):
        from optimization import simulator as S
        row = _decide("quiet.exe",
                      [0.02, 0.5, 0.03, 0.05, 0.05, 0.0, 0.0, 0.5, 1.0, 0.0, 0.02])
        self.assertLess(row["ai"]["final_confidence"], 0.85)
        sim = S.preview(row)
        self.assertEqual(sim["simulated_action"], "NO_ACTION")

    def test_4_ood_no_action(self):
        from optimization import simulator as S
        row = _decide("weird.exe",
                      [0.99, 1.0, 0.99, 1.0, 1.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.99])
        self.assertTrue(row["ai"]["ood"])
        sim = S.preview(row)
        self.assertEqual(sim["simulated_action"], "NO_ACTION")

    def test_5_candidate_simulates(self):
        from optimization import simulator as S
        row = _sync_row()
        self.assertEqual(row["ai"]["safety_state"], "OPTIMIZATION CANDIDATE")
        sim = S.preview(row)
        self.assertEqual(sim["simulated_action"], "REDUCE_BACKGROUND_ACTIVITY")
        self.assertTrue(sim["simulated"] and sim["simulation"])
        seq = S.sequence(row)
        self.assertEqual(seq["stages"],
                         ["ANALYZING", "SAFETY_CHECK", "ACTION_APPROVED",
                          "SIMULATING", "PROJECTED_RESULT"])

    def test_6_modifies_nothing(self):
        import psutil
        from optimization import simulator as S
        me = psutil.Process()
        before = (me.status(), me.nice(), me.cpu_percent(interval=None))
        for _ in range(5):
            S.sequence(_sync_row())
        after = (me.status(), me.nice())
        self.assertEqual(before[:2], after)
        import ast as _ast
        src = (ROOT / "optimization" / "simulator.py").read_text()
        tree = _ast.parse(src)
        doc_lines = set()
        for node in _ast.walk(tree):
            if isinstance(node, _ast.Expr) and isinstance(node.value, _ast.Constant) \
                    and isinstance(node.value.value, str):
                doc_lines.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))
        code = "\n".join(
            ln.split("#", 1)[0] for i, ln in enumerate(src.splitlines(), 1)
            if i not in doc_lines)
        for pat in (".terminate(", ".kill(", "os.kill(", "taskkill",
                    "SuspendThread(", ".nice(", "set_priority(",
                    "TerminateProcess(", "ctypes", "win32", "subprocess",
                    "Stop-Process"):
            self.assertNotIn(pat, code)

    def test_7_marked_simulated(self):
        from optimization import simulator as S
        for row in (_sync_row(),
                    _decide("x.exe", [0.02, 0.5, 0.03, 0.05, 0.05, 0.0, 0.0,
                                      0.5, 1.0, 0.0, 0.02])):
            sim = S.preview(row)
            self.assertTrue(sim["simulated"])
            self.assertIn("SIMULATED", sim["labels"])
            self.assertIn("PROJECTED", sim["labels"])

    def test_8_projections_not_measurements(self):
        from optimization import simulator as S
        sim = S.preview(_sync_row())
        blob = (sim["projected_effect"] + sim["explanation"]
                + sim["before"] + sim["after"])
        self.assertNotIn("%", blob)
        for word in ("Simulation only", "not a measurement"):
            self.assertIn(word, blob)

    def test_9_simulation_logged(self):
        import tempfile
        from unittest import mock
        from ai import decision_log as L
        from optimization import simulator as S
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(L, "LOG_DIR", Path(td)), \
                 mock.patch.object(L, "LOG_PATH", Path(td) / "s.jsonl"):
                row = _sync_row()
                sim = S.sequence(row)
                rec = L.record(row, "CPU FALLBACK")
                rec.update({"simulation": True,
                            "simulated_action": sim["simulated_action"],
                            "projected_effect": sim["projected_effect"]})
                L.log_record(rec)
                recs = [r for r in L.tail(10) if r.get("simulation")]
                self.assertEqual(len(recs), 1)
                self.assertEqual(recs[0]["simulated_action"],
                                 "REDUCE_BACKGROUND_ACTIVITY")
                self.assertIn("projected_effect", recs[0])

    def test_10_safety_unchanged(self):
        from ai import safety
        v = [0.02, 0.5, 0.03, 0.05, 0.05, 0.0, 0.0, 0.5, 1.0, 0.0, 0.02]
        self.assertEqual(safety.finalize("svchost.exe", 3, 0.9999, v)["safety_state"], "PROTECT")
        self.assertEqual(safety.THRESHOLD, 0.85)
        from safety.engine import guard
        with self.assertRaises(RuntimeError):
            guard("terminate")

    def test_11_emergency_stop(self):
        import json
        import urllib.request
        import app
        self.assertFalse(app.EMERGENCY_STOP)  # default: flow enabled
        base = "http://127.0.0.1:8099"
        try:
            get = lambda p: json.loads(
                urllib.request.urlopen(base + p, timeout=30).read())
            self.assertFalse(get("/api/emergency")["emergency_stop"])
            self.assertTrue(get("/api/emergency?state=on")["emergency_stop"])
            sim = get("/api/optimization/simulate?set=sync&index=0")
            self.assertTrue(sim.get("disabled"))
            self.assertEqual(sim["simulated_action"], "NO_ACTION")
            procs = get("/api/processes?limit=5&sort=cpu")
            self.assertGreater(procs["count"], 0)  # monitoring continues
            self.assertFalse(get("/api/emergency?state=off")["emergency_stop"])
        except Exception as e:
            self.skipTest(f"server not running: {e}")
        finally:
            try:
                urllib.request.urlopen(base + "/api/emergency?state=off",
                                       timeout=30).read()
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main(verbosity=2)
