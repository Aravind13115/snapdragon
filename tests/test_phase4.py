"""Phase-4 tests: NPU/QNN abstraction without Snapdragon hardware.

Covers: backend abstraction, provider selection, unavailable fallback,
model loading, output consistency, truthful status, no false NPU claims.
NPU execution itself is NOT claimed (REQUIRES SNAPDRAGON HARDWARE).

Usage: python tests/test_phase4.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class Phase4(unittest.TestCase):
    def test_abstraction(self):
        # Both backends share the ProcessClassifier interface; app code
        # only uses predict_batch/classify_features/status + select().
        from inference.base import ProcessClassifier
        from inference.onnx_backend import OnnxClassifier
        self.assertTrue(issubclass(OnnxClassifier, ProcessClassifier))
        for m in ("predict_batch", "classify_features", "status"):
            self.assertTrue(hasattr(OnnxClassifier, m))

    def test_selection_cpu(self):
        from inference import backend as B
        plat = {"is_arm": False, "is_snapdragon": False,
                "arch_normalized": "x86_64", "cpu_name": "Intel"}
        qnn = {"available": False}
        sel = B.select(plat, qnn)
        self.assertEqual(sel["selected_backend"], "CPU FALLBACK")
        self.assertEqual(sel["provider"], "CPUExecutionProvider")

    def test_selection_qnn_path(self):
        # Logic path: Snapdragon + QNN EP present -> HEXAGON NPU.
        # (Hardware presence itself is NOT asserted here.)
        from inference import backend as B
        import onnxruntime as ort
        real = ort.get_available_providers
        try:
            ort.get_available_providers = lambda: ["QNNExecutionProvider",
                                                   "CPUExecutionProvider"]
            sel = B.select({}, {"available": True})
            self.assertEqual(sel["selected_backend"], "HEXAGON NPU")
            self.assertEqual(sel["provider"], "QNNExecutionProvider")
        finally:
            ort.get_available_providers = real

    def test_qnn_ep_missing_fallback(self):
        # Snapdragon host but no QNN EP build -> honest CPU fallback + note.
        from inference import backend as B
        sel = B.select({"is_arm": True}, {"available": True})
        import onnxruntime as ort
        if "QNNExecutionProvider" not in ort.get_available_providers():
            self.assertEqual(sel["selected_backend"], "CPU FALLBACK")
            self.assertIn("QNN", sel["note"])

    def test_output_consistency(self):
        # Same model + same input -> identical outputs (backend-agnostic
        # determinism; cross-backend agreement procedure is in the docs).
        from inference.onnx_backend import OnnxClassifier
        clf = OnnxClassifier()
        X = np.random.default_rng(11).random((16, 11)).astype(np.float32)
        l1, p1, _ = clf.predict_batch(X)
        l2, p2, _ = clf.predict_batch(X)
        self.assertTrue((l1 == l2).all() and np.allclose(p1, p2))

    def test_truthful_status(self):
        from inference import bench
        npu = bench.npu_scaffold()
        self.assertFalse(npu["qnn_available"])
        self.assertEqual(npu["selected"], "CPU FALLBACK")
        self.assertEqual(npu["npu_latency_ms"], "REQUIRES_SNAPDRAGON_HARDWARE")
        cpu = bench.cpu_bench(repeats=20, batch=8)
        self.assertEqual(cpu["status"], "VERIFIED_MEASUREMENT")
        self.assertGreater(cpu["single_row_ms"], 0)

    def test_no_false_npu_claims(self):
        import re
        rx = re.compile(r"NPU ACTIVE|running on (the )?npu|hexagon (active|in use)", re.I)
        for f in list((ROOT / "static").glob("*.js")) + \
                 list((ROOT / "static").glob("*.html")):
            self.assertFalse(rx.search(f.read_text(encoding="utf-8")), f.name)
        for f in list(ROOT.rglob("*.py")):
            if "__pycache__" in str(f) or "test_" in f.name:
                continue
            for i, ln in enumerate(f.read_text(errors="replace").splitlines(), 1):
                if rx.search(ln):
                    self.fail(f"{f.name}:{i}: {ln.strip()[:100]}")


    def test_harness_local(self):
        from tools import npu_validation as H
        out = H.local_validation()
        self.assertEqual(out['status'], 'LOCAL_CPU_VERIFIED')
        self.assertTrue(out['features_ok'] and out['classes_ok'])
        self.assertEqual(len(out['cpu_reference']), 4)

    def test_hub_blocked_honest(self):
        import re
        from tools import npu_validation as H
        res = H.hub_attempt()
        self.assertEqual(res['status'], 'BLOCKED')
        # no credential *value* may appear (guidance prose is fine)
        import json
        self.assertFalse(re.search(r"api[_-]?token['\"]?\s*[:=]\s*['\"]?\w{8,}",
                                  json.dumps(res), re.I))

    def test_artifacts_no_credentials(self):
        import json
        import re
        art = ROOT / 'artifacts' / 'npu_validation' / 'validation_summary.json'
        self.assertTrue(art.exists())
        blob = art.read_text()
        self.assertFalse(re.search(r"api[_-]?token['\"]?\s*[:=]\s*['\"]?\w{8,}", blob, re.I))
        self.assertNotIn('client.ini', blob)
        summ = json.loads(blob)
        self.assertEqual(summ['local']['status'], 'LOCAL_CPU_VERIFIED')

    def _mock_client(self, compute_unit='NPU'):
        import numpy as np

        class Dev:
            name = 'Snapdragon X Elite CRD'
            os = '11'
            attributes = ['os:windows', 'format:compute', 'framework:onnx',
                          'framework:qnn', 'abi:aarch64-windows',
                          'chipset:qualcomm-snapdragon-x-elite',
                          'chipset:sc8380xp', 'hexagon:v73']

        class CJob:
            job_id = 'jc_test'
            def wait(self): pass
            def get_status(self): return 'SUCCESS'

            def get_target_model(self):
                class T:
                    def download(self, p): Path(p).mkdir(parents=True, exist_ok=True)
                return T()

        class PJob:
            job_id = 'jp_test'
            def wait(self): pass

            def download_profile(self):
                return {'compute_unit': compute_unit, 'exec_time_ms': '0.42'}

        class IJob:
            job_id = 'ji_test'
            def wait(self): pass

            def download_output_data(self):
                from tools import npu_validation as H
                from inference.onnx_backend import OnnxClassifier
                clf = OnnxClassifier()
                X = np.stack([np.asarray(v, np.float32) for v in H.PROBES.values()])
                probs, _ = clf.session.run(None, {clf._input: X})
                return np.asarray(probs)

        class Client:
            def get_devices(self): return [Dev()]
            def submit_compile_and_link_jobs(self, **kw):
                self.seen_kw = kw
                return CJob()
            def submit_profile_job(self, **kw): return PJob()
            def submit_inference_job(self, **kw): return IJob()
        return Client()

    def test_staged_flow_npu_verified(self):
        from tools import npu_validation as H
        rec = H.hub_staged(self._mock_client('NPU'))
        self.assertEqual(rec['status'], 'NPU_VERIFIED')
        self.assertEqual(rec['target']['name'], 'Snapdragon X Elite CRD')
        self.assertIn('compiled', rec['stages'])
        self.assertEqual(rec['inference']['argmax_agreement'], '4/4')

    def test_staged_flow_no_windows_target(self):
        from tools import npu_validation as H

        class Client:
            def get_devices(self):
                class D:
                    name = 'Pixel 8'
                    os = 'Android 14'
                return [D()]
        rec = H.hub_staged(Client())
        self.assertEqual(rec['status'], 'BLOCKED')

    def test_staged_flow_non_npu_honest(self):
        from tools import npu_validation as H
        rec = H.hub_staged(self._mock_client('GPU'))
        self.assertEqual(rec['status'], 'PROFILED_NON_NPU')

if __name__ == "__main__":
    unittest.main(verbosity=2)
