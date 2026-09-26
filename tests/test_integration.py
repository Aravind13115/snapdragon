"""Full integration + regression + safety test, Phase 1 -> 2.5.

End-to-end against the LIVE server (no mocks). Observation-only:
no test modifies any process; the "modification audit" is static.

Usage (server must be running):
    python app.py                # terminal 1
    python tests/test_integration.py   # terminal 2
    INTEGRATION_BASE=http://127.0.0.1:8099 python tests/test_integration.py

stdlib only.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import unittest
import urllib.request
import urllib.error

ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
BASE = os.environ.get("INTEGRATION_BASE", "http://127.0.0.1:8099")

PASS, FAIL, WARN = [], [], []


def get(path, timeout=30):
    t = time.perf_counter()
    with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
        body = r.read()
    return r.status, json.loads(body), (time.perf_counter() - t) * 1000


def note(kind, msg):
    (PASS if kind == "pass" else FAIL if kind == "fail" else WARN).append(msg)
    print(f"[{kind.upper():4s}] {msg}")


class Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        st, cls.ai_status, _ = get("/api/ai_status")
        assert st == 200
        _, cls.live, _ = get("/api/processes?limit=200&sort=cpu", timeout=60)
        from ai import ood
        ood.standardize([0.0] * 11)  # force centroid/scaler load

    # ---- 2/22. endpoints alive, valid JSON, latency ----
    def test_endpoints(self):
        for p in ("/api/platform", "/api/stats", "/api/processes",
                  "/api/plan", "/api/ai_status", "/api/backends",
                  "/api/safety", "/api/demo?set=presentation"):
            st, body, ms = get(p, timeout=60)
            self.assertEqual(st, 200, p)
            self.assertIsInstance(body, dict, p)
            note("pass" if ms < 15000 else "warn", f"{p} 200 in {ms:.0f}ms")

    # ---- 2/3. telemetry sanity ----
    def test_telemetry_sanity(self):
        _, s, _ = get("/api/stats")
        self.assertGreaterEqual(s["cpu"]["total_pct"], 0)
        self.assertLessEqual(s["cpu"]["total_pct"], 100)
        for v in s["cpu"]["per_core_pct"]:
            self.assertGreaterEqual(v, 0)
            self.assertLessEqual(v, 400)  # psutil per-core ceiling
        self.assertGreater(s["memory"]["total_gb"], 0)
        self.assertGreaterEqual(s["memory"]["pct"], 0)
        self.assertLessEqual(s["memory"]["pct"], 100)
        self.assertGreater(s["disk"]["total_gb"], 0)
        b = s["battery"]
        if b["present"]:
            self.assertGreaterEqual(b["percent"], 0)
            self.assertLessEqual(b["percent"], 100)
        _, p, _ = get("/api/processes?limit=200&sort=cpu", timeout=60)
        pids = [r["pid"] for r in p["rows"]]
        self.assertEqual(len(pids), len(set(pids)), "duplicate PIDs")
        for r in p["rows"]:
            self.assertIsInstance(r["pid"], int)
            self.assertGreaterEqual(r["pid"], 0)
            self.assertTrue(r["name"])
            self.assertGreaterEqual(r["cpu_pct"], 0)
            self.assertLessEqual(r["cpu_pct"], 100)
            self.assertGreaterEqual(r["mem_pct"], 0)
        note("pass", f"telemetry sane; {p['count']} procs, no dup/malformed")
        Integration.live = p

    # ---- 4. platform ----
    def test_platform(self):
        _, p, _ = get("/api/platform")
        self.assertFalse(p["is_arm"])
        self.assertFalse(p["is_snapdragon"])
        self.assertEqual(p["arch_normalized"], "x86_64")
        self.assertIn("not applicable", p["phase_routing"]["qnn_backend"])
        note("pass", "platform: x64 dev env distinguished from ARM target")

    # ---- 5. arch labels ----
    def test_arch(self):
        rows = Integration.live["rows"]
        allowed = {"x64", "ARM64 Native", "x86 (WOW64)", "x86 (Emulated)",
                   "x64 (Emulated)", "Unknown"}
        bad = {r.get("arch") for r in rows if r.get("arch") not in allowed}
        self.assertFalse(bad, f"unexpected arch labels: {bad}")
        # x86/x64 must never be blamed as a reason to act: only emulation
        # is ever mentioned, and only as an informational why-line.
        for r in rows:
            reason = (r.get("ai") or {}).get("override_reason") or ""
            self.assertNotIn("WOW64", reason)
            self.assertNotIn("x64", reason.replace("x64 (Emulated)", ""))
        note("pass", f"arch labels in {sorted(allowed)}; Unknown used, never guessed")

    # ---- 6. foreground ----
    def test_foreground(self):
        from ai import features as F
        fg = F.foreground_pid()
        rows = {r["pid"]: r for r in Integration.live["rows"]}
        if fg is None:
            note("warn", "no foreground window detected (headless?); rule tested in unit suite")
            return
        self.assertIn(fg, rows, "fg pid outside top-200 sample")
        st = rows[fg]["ai"]["safety_state"]
        self.assertEqual(st, "PROTECT", f"fg pid {fg} state={st}")
        note("pass", f"foreground pid {fg} ({rows[fg]['name']}) -> PROTECT")

    # ---- 7/8. protected + pid 0/4 ----
    def test_protected_and_pids(self):
        from safety.allowlist import is_protected
        rows = Integration.live["rows"]
        prot = [r for r in rows if is_protected(r["name"])]
        self.assertTrue(prot, "no allowlisted procs in sample")
        for r in prot:
            self.assertEqual(r["ai"]["safety_state"], "PROTECT", r["name"])
            self.assertNotEqual(r["ai"]["safety_state"], "OPTIMIZATION CANDIDATE")
        for pid in (0, 4):
            r = next(x for x in rows if x["pid"] == pid)
            self.assertEqual(r["ai"]["safety_state"], "PROTECT")
        # model-vs-safety separation on a protected row that the model likes
        sep = [r for r in prot if r["ai"]["model_class"] in ("FLEXIBLE", "DEFERRABLE")]
        note("pass", f"{len(prot)} allowlisted incl pid0/4 all PROTECT; "
                     f"{len(sep)} show model!=decision separation")

    # ---- 9. model file ----
    def test_model_file(self):
        import onnx
        m = onnx.load(str(ROOT / "models" / "process_classifier.onnx"))
        inp = m.graph.input[0]
        dim = inp.type.tensor_type.shape.dim[1].dim_value
        outs = {o.name for o in m.graph.output}
        self.assertEqual(dim, 11)
        self.assertEqual(outs, {"probabilities", "label"})
        meta = json.loads((ROOT / "models" / "model_metadata.json").read_text())
        self.assertEqual(meta["features"], __import__("ai.dataset", fromlist=["FEATURES"]).FEATURES)
        self.assertEqual(meta["classes"], ["PROTECTED", "USER_IMPORTANT", "FLEXIBLE", "DEFERRABLE"])
        self.assertEqual(meta["architecture"]["layers"], [11, 16, 8, 4])
        note("pass", f"onnx 11->4 verified; meta v{meta['version']} matches graph")

    # ---- 10. feature consistency ----
    def test_feature_consistency(self):
        from ai.dataset import FEATURES, N_FEATURES
        from ai import ood
        import json as j
        meta = j.loads((ROOT / "models" / "model_metadata.json").read_text())
        self.assertEqual(meta["features"], FEATURES)
        self.assertEqual(N_FEATURES, 11)
        self.assertTrue((__import__("numpy") .asarray(meta["normalization"]["mean"]) == ood._mean).all())
        note("pass", "train/inference/metadata feature order + scaler identical")

    # ---- 11. live inference validity ----
    def test_live_inference(self):
        import numpy as np
        from inference.onnx_backend import OnnxClassifier
        clf = OnnxClassifier()
        X = np.random.default_rng(0).random((8, 11)).astype(np.float32)
        labs, probs, ms = clf.predict_batch(X)
        self.assertTrue(((probs >= 0) & (probs <= 1)).all())
        self.assertTrue(np.allclose(probs.sum(1), 1, atol=1e-4))
        for r in Integration.live["rows"][:20]:
            ai = r.get("ai") or {}
            if "probabilities" in ai:
                ps = ai["probabilities"]
                self.assertAlmostEqual(sum(ps), 1.0, delta=0.01)
                self.assertGreaterEqual(ai["raw_confidence"], 0)
                self.assertLessEqual(ai["raw_confidence"], 1)
        note("pass", f"batch8 in {ms:.2f}ms; live probs valid, sum~=1")

    # ---- 13. collapse ----
    def test_no_collapse(self):
        from collections import Counter
        # (a) Model degeneracy check on a BALANCED probe: a collapsed model
        # votes one class no matter the input. Population skew in live data
        # is not model collapse.
        import numpy as np
        from ai.dataset import generate
        from inference.onnx_backend import OnnxClassifier
        X, _ = generate(n_per_class=100, seed=777)
        labs, _, _ = OnnxClassifier().predict_batch(X)
        frac = max((labs == c).mean() for c in range(4))
        self.assertLess(frac, 0.90, f"model collapsed on balanced probe: {frac:.2f}")
        # (b) Live skew is reported, not failed: an idle machine genuinely
        # hosts mostly quiet background processes.
        votes = Counter(r["ai"]["model_class"] for r in Integration.live["rows"]
                        if r["ai"].get("model_class", "").isupper()
                        and r["ai"]["model_class"] != "n/a (system)")
        top = max(votes.values()) / sum(votes.values())
        note("pass" if top < 0.9 else "warn",
             f"live model votes {dict(votes)} (probe spread OK; skew=population)")

    # ---- 14. calibration applied ----
    def test_calibration(self):
        r = next(x for x in Integration.live["rows"]
                 if x.get("ai", {}).get("familiarity") not in (None, 1.0))
        ai = r["ai"]
        self.assertAlmostEqual(ai["final_confidence"],
                               ai["raw_confidence"] * ai["familiarity"], delta=1e-3)
        self.assertNotEqual(ai["final_confidence"], ai["raw_confidence"])
        note("pass", f"final({ai['final_confidence']}) = raw x fam on {r['name']}")

    # ---- 15/16. OOD + familiarity ----
    def test_ood(self):
        from ai import ood
        fam_live = [r["ai"]["familiarity"] for r in Integration.live["rows"]
                    if "familiarity" in r.get("ai", {})]
        self.assertTrue(all(0 < f <= 1 for f in fam_live))
        wild = ood.familiarity([0.99, 1.0, 0.99, 1.0, 1.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.99])
        self.assertTrue(wild["ood"])
        tame = ood.familiarity([0.05, 0.5, 0.05, 0.1, 0.05, 0.0, 0.0, 0.3, 1.0, 0.0, 0.05])
        self.assertFalse(tame["ood"])
        note("pass", f"live fam range {min(fam_live):.2f}-{max(fam_live):.2f}; wild OOD, tame familiar")

    # ---- 17-20. safety matrix + no bypass ----
    def test_safety_matrix(self):
        from ai import safety
        fam_vec = [0.12, 0.55, 0.18, 0.2, 0.1, 0.0, 0.0, 0.9, 1.0, 0.0, 0.1]
        cases = [
            (safety.finalize("svchost.exe", 3, 0.9999, fam_vec), "PROTECT"),       # allowlist beats 0.9999
            (safety.finalize("app.exe", 2, 0.99, fam_vec, is_foreground=True), "PROTECT"),
            (safety.finalize("app.exe", 2, 0.20, fam_vec), "PROTECT"),              # low conf
            (safety.finalize("app.exe", 2, 0.99, [0.99]*11), "PROTECT"),            # wild -> OOD
        ]
        for d, want in cases:
            self.assertEqual(d["safety_state"], want, d)
            if d["model_class"] in ("FLEXIBLE", "DEFERRABLE"):
                self.assertNotEqual(d["safety_state"], "OPTIMIZATION CANDIDATE")
        note("pass", "no bypass: allowlist/fg/conf/OOD all override 0.99 votes")

    # ---- 21. modification audit ----
    def test_no_modification_path(self):
        # Call-shaped patterns only: bare words appear legitimately in the
        # safety blocklist (safety/engine.py), comments and docs.
        rx = re.compile(r"\.(terminate|kill)\s*\(|os\.kill\s*\(|taskkill|"
                        r"Stop-Process|TerminateProcess\s*\(|SuspendThread\s*\(|"
                        r"set_priority\s*\(|\.nice\s*\(|subprocess\.\w+\s*\(", re.I)
        hits = []
        for f in list(ROOT.rglob("*.py")) + list(ROOT.rglob("*.js")):
            if "__pycache__" in str(f) or "test_" in f.name:
                continue
            for i, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
                if rx.search(line):
                    hits.append(f"{f.name}:{i}: {line.strip()[:90]}")
        self.assertFalse(hits, f"destructive paths: {hits}")
        _, plan, _ = get("/api/plan")
        self.assertEqual(plan["executed"], [])
        note("pass", "static audit clean; /api/plan executed==[]")

    # ---- 22b. malformed params ----
    def test_malformed(self):
        st, b, _ = get("/api/processes?limit=abc&sort=bogus", timeout=60)
        self.assertEqual(st, 200)
        self.assertLessEqual(len(b["rows"]), 200)
        st, b, _ = get("/api/demo?set=nonexistent")
        self.assertEqual(st, 200)
        self.assertTrue(b["demo"])
        note("pass", "malformed limit/sort/demo-set degrade gracefully")

    # ---- 24. demo isolation ----
    def test_demo(self):
        _, d, _ = get("/api/demo?set=battery")
        self.assertTrue(d["demo"] and d["simulated_processes"]
                        and d["real_model_predictions"])
        _, live, _ = get("/api/processes?limit=5&sort=cpu", timeout=60)
        self.assertFalse(any(r.get("demo") for r in live["rows"]))
        note("pass", "demo marked, isolated from live telemetry")

    # ---- 25/26. backend ----
    def test_backend(self):
        _, b, _ = get("/api/backends")
        self.assertEqual(b["selected"]["selected_backend"], "CPU FALLBACK")
        self.assertFalse(b["qnn"]["available"])
        self.assertIn("CPUExecutionProvider", b["selected"]["ort_providers"])
        self.assertNotIn("QNNExecutionProvider", b["selected"]["ort_providers"])
        from inference.onnx_backend import OnnxClassifier
        for m in ("predict_batch", "classify_features", "status"):
            self.assertTrue(hasattr(OnnxClassifier, m))
        note("pass", "CPU FALLBACK honest; NPU not claimed; backend interface uniform")

    # ---- 28. error recovery ----
    def test_recovery(self):
        from inference.onnx_backend import OnnxClassifier
        with self.assertRaises(FileNotFoundError):
            OnnxClassifier(model_path=str(ROOT / "models" / "nope.onnx"))
        from ai import analyze
        out = analyze.enrich([{"pid": -5, "name": "ghost.exe",
                               "cpu_pct": 99.0, "mem_pct": 1.0}], OnnxClassifier())
        self.assertIn("safety_state", out["rows"][0]["ai"])
        note("pass", "missing model raises; dead-pid enrich degrades safe")

    # ---- 31. security ----
    def test_security(self):
        src = (ROOT / "app.py").read_text()
        self.assertIn('ThreadingHTTPServer(("127.0.0.1"', src)
        self.assertNotIn("do_POST", src)
        self.assertNotIn("do_PUT", src)
        tree = "".join(f.read_text(errors="replace")
                       for f in list(ROOT.rglob("*.py"))
                       if "__pycache__" not in str(f) and "test_" not in f.name)
        for pat in ("requests.post", "urlopen", "socket.connect",
                    "telemetry.azure", "upload"):
            self.assertNotIn(pat, tree)
        note("pass", "localhost-only, GET-only, no upload/remote-control paths")

    # ---- 32. stability ----
    def test_stability(self):
        tree = "".join(f.read_text(errors="replace")
                       for f in list(ROOT.rglob("*.py"))
                       if "__pycache__" not in str(f) and "test_" not in f.name)
        for pat in ("HKEY_", "winreg", "SetValueEx", "CreateService",
                    "SCHTASKS", "firmware"):
            self.assertNotIn(pat, tree)
        note("pass", "no registry/persistence/service/firmware writes")


if __name__ == "__main__":
    r = unittest.main(verbosity=1, exit=False).result
    print(f"\nINTEGRATION: ran={r.testsRun} failures={len(r.failures)} "
          f"errors={len(r.errors)} warnings={len(WARN)}")
    sys.exit(0 if r.wasSuccessful() else 1)
