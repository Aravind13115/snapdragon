"""Phase-2.7 tests: sampler caching, decision log, overhead, no-regression.

 1. sampler caches metadata      6. record schema (+no private data)
 2. PID reuse re-fetch           7. dashboard decision history (static)
 3. disappearance drops pid      8. overhead (structural + enrich bound)
 4. decision log write           9. no destructive process calls
 5. decisions API (live server) 10. safety no-regression spot-checks

Usage: python tests/test_phase27.py  (test 5 needs the server running)
stdlib only (unittest.mock for deterministic sampler tests).
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class FakeIO:
    def __init__(self, total=1000):
        self.read_bytes = total // 2
        self.write_bytes = total // 2


class FakeProc:
    LIVE = {}

    def __init__(self, pid):
        if pid not in FakeProc.LIVE:
            raise FakeNoSuch(pid)
        self._pid = pid

    def create_time(self):
        return FakeProc.LIVE[self._pid]["ctime"]

    def name(self):
        return FakeProc.LIVE[self._pid]["name"]

    def cpu_percent(self, interval=None):
        return FakeProc.LIVE[self._pid]["cpu"]

    def memory_percent(self):
        return FakeProc.LIVE[self._pid]["mem"]

    def status(self):
        return "running"

    def username(self):
        return "user"

    def io_counters(self):
        return FakeIO()


class FakeNoSuch(Exception):
    pass


class FakePsutil:
    NoSuchProcess = FakeNoSuch
    AccessDenied = FakeNoSuch
    ZombieProcess = FakeNoSuch

    @staticmethod
    def pids():
        return list(FakeProc.LIVE)

    Process = FakeProc


def seed_live(n=10):
    FakeProc.LIVE = {1000 + i: {"ctime": 111.0, "name": f"p{i}.exe",
                                "cpu": 0.0, "mem": 1.0} for i in range(n)}


class Phase27(unittest.TestCase):
    def _sampler(self):
        import telemetry.sampler as S
        with mock.patch.object(S, "psutil", FakePsutil):
            s = S.Sampler(fast_interval=5, slow_interval=1000)
            s.fast_tick()
            return s, S

    def test_1_caching(self):
        import telemetry.sampler as S
        seed_live(6)
        with mock.patch.object(S, "psutil", FakePsutil):
            s = S.Sampler(fast_interval=5, slow_interval=1000)
            s.fast_tick()
            objs = {pid: e["proc"] for pid, e in s.entries.items()}
            names = {pid: e["name"] for pid, e in s.entries.items()}
            s.fast_tick()
            for pid, e in s.entries.items():
                self.assertIs(e["proc"], objs[pid])      # object reused
                self.assertEqual(e["name"], names[pid])  # metadata stable

    def test_2_pid_reuse(self):
        import telemetry.sampler as S
        seed_live(3)
        with mock.patch.object(S, "psutil", FakePsutil):
            s = S.Sampler(fast_interval=5, slow_interval=1000)
            s.fast_tick()
            # pid 1000 exits; a NEW process reuses pid 1000 (new create_time)
            FakeProc.LIVE[1000] = {"ctime": 999.0, "name": "new.exe",
                                   "cpu": 5.0, "mem": 2.0}
            s.fast_tick()
            self.assertEqual(s.entries[1000]["name"], "new.exe")
            self.assertEqual(s.entries[1000]["create_time"], 999.0)

    def test_3_disappearance(self):
        import telemetry.sampler as S
        seed_live(5)
        with mock.patch.object(S, "psutil", FakePsutil):
            s = S.Sampler(fast_interval=5, slow_interval=1000)
            s.fast_tick()
            self.assertEqual(len(s.entries), 5)
            del FakeProc.LIVE[1001]
            del FakeProc.LIVE[1003]
            s.fast_tick()
            self.assertNotIn(1001, s.entries)
            self.assertNotIn(1003, s.entries)
            self.assertEqual(len(s.entries), 3)
            self.assertEqual(s.rows(limit=200)["count"], 3)

    def test_4_log_write(self):
        from ai import decision_log as L
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(L, "LOG_DIR", Path(td)), \
                 mock.patch.object(L, "LOG_PATH", Path(td) / "t.jsonl"):
                rows = [{"pid": 1, "name": "a.exe", "arch": "x64",
                         "ai": {"model_class": "FLEXIBLE", "raw_confidence": 0.9,
                                "familiarity": 0.9, "familiarity_level": "HIGH",
                                "final_confidence": 0.81, "safety_state": "REVIEW",
                                "recommendation": "REVIEW / PROTECT",
                                "override_reason": "below threshold",
                                "why": ["Background process"]}}]
                n = L.append(rows, "CPU FALLBACK")
                self.assertEqual(n, 1)
                recs = L.tail(10)
                self.assertEqual(len(recs), 1)
                self.assertEqual(recs[0]["process"], "a.exe")

    def test_5_decisions_api(self):
        import urllib.request
        try:
            with urllib.request.urlopen(
                    "http://127.0.0.1:8099/api/decisions?limit=5",
                    timeout=30) as r:
                body = json.loads(r.read())
        except Exception as e:
            self.skipTest(f"server not running: {e}")
        self.assertIn("records", body)
        self.assertIsInstance(body["records"], list)

    def test_6_schema(self):
        from ai import decision_log as L
        rec = L.record({"pid": 7, "name": "x.exe", "arch": "x64",
                        "ai": {"model_class": "DEFERRABLE", "raw_confidence": 0.5,
                               "familiarity": 0.5, "familiarity_level": "MEDIUM",
                               "final_confidence": 0.25, "safety_state": "PROTECT",
                               "recommendation": "PROTECT",
                               "override_reason": "low", "why": ["w"]}},
                       "CPU FALLBACK")
        self.assertEqual(tuple(sorted(rec)), tuple(sorted(L.SCHEMA)))
        blob = json.dumps(rec).lower()
        self.assertNotIn("username", blob)
        self.assertNotIn("sid", blob)

    def test_7_dashboard_history(self):
        html = (ROOT / "static" / "dashboard.html").read_text(encoding="utf-8")
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="decisions"', html)
        self.assertIn("/api/decisions", js)
        self.assertIn("safety_state", js)
        self.assertIn("DEMO DATA", html)

    def test_8_overhead(self):
        import time
        import telemetry.sampler as S
        seed_live(40)
        with mock.patch.object(S, "psutil", FakePsutil):
            s = S.Sampler(fast_interval=5, slow_interval=1000)
            s.fast_tick()
            # idle tier needs 3 quiet observations, then skips 2 of 3 ticks
            st = {}
            for _ in range(6):
                st = s.fast_tick()
            self.assertLess(st["polled"], 40)
            self.assertGreater(st["skipped"], 0)
        # real enrich bound (generous): 200 rows well under one slow second
        import numpy as np
        from ai import analyze
        from inference.onnx_backend import OnnxClassifier
        t = time.perf_counter()
        analyze.enrich([{"pid": -100 - i, "name": "t.exe", "cpu_pct": 0.0,
                         "mem_pct": 0.1} for i in range(200)],
                       OnnxClassifier())
        self.assertLess(time.perf_counter() - t, 5.0)

    def test_9_no_destructive(self):
        import re
        rx = re.compile(r"\.(terminate|kill)\s*\(|os\.kill\s*\(|taskkill|"
                        r"Stop-Process|TerminateProcess\s*\(|SuspendThread\s*\(|"
                        r"set_priority\s*\(|\.nice\s*\(|subprocess\.\w+\s*\(", re.I)
        hits = []
        for f in list(ROOT.rglob("*.py")) + list(ROOT.rglob("*.js")):
            if "__pycache__" in str(f) or "test_" in f.name:
                continue
            for i, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
                if rx.search(line):
                    hits.append(f"{f.name}:{i}")
        self.assertFalse(hits, f"destructive: {hits}")

    def test_10_safety_no_regression(self):
        from ai import safety
        v = [0.02, 0.5, 0.03, 0.05, 0.05, 0.0, 0.0, 0.5, 1.0, 0.0, 0.02]
        self.assertEqual(safety.finalize("svchost.exe", 3, 0.9999, v)["safety_state"], "PROTECT")
        self.assertEqual(safety.finalize("a.exe", 2, 0.99, v, is_foreground=True)["safety_state"], "PROTECT")
        self.assertEqual(safety.finalize("a.exe", 2, 0.10, v)["safety_state"], "PROTECT")
        wild = [0.99, 1.0, 0.99, 1.0, 1.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.99]
        d = safety.finalize("a.exe", 2, 0.99, wild)
        self.assertEqual(d["safety_state"], "PROTECT")
        self.assertEqual(d["ai_class"], "UNKNOWN")
        # honest candidate path still exists (centroid, unchanged thresholds)
        import numpy as np
        from inference.onnx_backend import OnnxClassifier
        clf = OnnxClassifier()
        cv = [0.175, 0.642, 0.124, 0.43, 0.554, 0.0, 0.579, 0.359, 0.744, 0.209, 0.178]
        lab, prob, _ = clf.predict_batch(np.asarray(cv, np.float32).reshape(1, -1))
        d = safety.finalize("SyncClient.exe", int(lab[0]), float(prob[0, int(lab[0])]), cv)
        self.assertEqual(d["safety_state"], "OPTIMIZATION CANDIDATE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
