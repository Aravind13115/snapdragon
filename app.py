"""Phase-2 HTTP server: telemetry + AI classification API + dashboard.

READ-ONLY + RECOMMENDATION-ONLY endpoints. No endpoint modifies any
process; the AI produces classifications and suggestion text only.

  GET /                    dashboard
  GET /api/platform        live arch detection (real)
  GET /api/stats           live CPU/RAM/disk/net/battery (real, psutil)
  GET /api/processes       live process list + arch + AI predictions (real)
  GET /api/ai_status       model/backend/latency/size/threshold status
  GET /api/backends        ONNX backend + QNN probe + selected backend
  GET /api/demo?set=NAME   synthetic demo workloads via the REAL model (marked demo)
  GET /api/safety          safety engine status
  GET /api/plan            dry-run suggestions (executes nothing)

Stdlib HTTP only (no Flask) so `python app.py` just works.
Runtime ML deps: numpy, onnxruntime.
"""
from __future__ import annotations

import json
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import config
from ai import analyze as ai_analyze
from ai import decision_log as ai_log
from ai import demo as ai_demo
from inference import backend as backend_sel
from inference import qnn_backend
from inference.onnx_stub import HeuristicClassifier
from optimization import planner
from optimization import simulator as opt_sim
from safety import engine as safety_engine
from telemetry import platform_info, process_list, system_stats
from telemetry.sampler import Sampler

BASE = Path(__file__).resolve().parent

# Real ONNX model; honest stub fallback if the model file is absent.
try:
    from inference.onnx_backend import OnnxClassifier
    _classifier = OnnxClassifier()
    _ai_source = "onnx-model"
except Exception as e:  # model missing / ORT broken -> marked stub
    _classifier = HeuristicClassifier()
    _ai_source = f"heuristic-stub (ONNX unavailable: {e})"

_platform = platform_info.detection()  # stable per boot; computed once
_qnn = qnn_backend.probe(_platform)
_backend = backend_sel.select(_platform, _qnn)

# Emergency stop (Phase 5.4, prototype control): when ON, the simulation
# and recommendation flow is disabled server-side (preview/simulate return
# disabled:true and nothing is logged); monitoring + classification continue
# and Windows remains untouched in both states.
EMERGENCY_STOP = False


def _ood_ref() -> dict:
    try:
        from ai import ood as _ood
        return {"temperature": _ood_temp(), "ood_threshold": _ood.OOD_THRESHOLD}
    except Exception:
        return {}


def _ood_temp():
    try:
        import json as _j
        meta = _j.loads((BASE / "models" / "model_metadata.json").read_text())
        return meta.get("calibration", {}).get("temperature")
    except Exception:
        return None


def _ort_version():
    try:
        import onnxruntime as _ort
        return _ort.__version__
    except Exception:
        return None
# Prime psutil cpu_percent baselines so first poll is meaningful.
system_stats.snapshot()
_boot = time.time()

# Tiered sampler (Phase 2.7): fast cpu/mem ticks on cached entries +
# slow metadata refresh. Full-scan top_processes() retained for tests and
# as the sampler's cold-start prime.
_sampler = Sampler(fast_interval=5.0, slow_interval=20.0, idle_skip=2)
_proc_cache: dict = {"result": {"simulated": False, "count": 0, "rows": [],
                                "note": "warming up…"}, "ts": 0.0}


def _proc_sampler_loop() -> None:
    import time as _t
    # Cold start: one full scan primes cpu baselines + metadata.
    try:
        seed = process_list.top_processes(limit=200)
        for r in seed["rows"]:
            _sampler._add(r["pid"])
    except Exception:
        pass
    while True:
        try:
            tick = _sampler.fast_tick()
            res = _sampler.rows(limit=200, sort="cpu")
            if _ai_source == "onnx-model":
                try:
                    enriched = ai_analyze.enrich(
                        res["rows"], _classifier,
                        host_is_arm=_platform.get("is_arm", False))
                    res["rows"] = enriched["rows"]
                    res["ai_summary"] = enriched["summary"]
                    ai_log.append(res["rows"], _backend["selected_backend"])
                except Exception:
                    res["ai_error"] = "enrichment failed; raw telemetry kept"
            _proc_cache["result_cpu"] = res
            _proc_cache["result_mem"] = None  # re-sorted on demand
            _proc_cache["ts"] = _t.time()
            _proc_cache["tick"] = tick
        except Exception:
            pass
        _t.sleep(_sampler.fast_interval)


def _cached_processes(limit: int, sort: str) -> dict:
    import time as _t
    res = _proc_cache.get("result_cpu") or _proc_cache["result"]
    rows = list(res.get("rows", []))
    if sort == "cpu":
        rows.sort(key=lambda r: r["cpu_pct"], reverse=True)
    else:
        rows.sort(key=lambda r: r["mem_pct"], reverse=True)
    out = dict(res)
    out["rows"] = rows[:limit]
    out["cache_age_s"] = round(_t.time() - _proc_cache["ts"], 1)
    return out


_sampler_thread = threading.Thread(target=_proc_sampler_loop, daemon=True)
_sampler_thread.start()


def _send(handler: SimpleHTTPRequestHandler, obj: dict) -> None:
    body = json.dumps(obj).encode()
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json")
    # CORS: allow the static competition website (any origin, e.g. local
    # preview or Vercel deployment) to read these GET-only observation
    # endpoints. Server stays localhost-bound; no new endpoints or logic.
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(BASE / "static"), **kw)

    def log_message(self, *a):
        pass  # quiet

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            self.path = "/dashboard.html"
            return super().do_GET()
        if u.path == "/api/platform":
            return _send(self, _platform)
        if u.path == "/api/stats":
            return _send(self, system_stats.snapshot())
        if u.path == "/api/processes":
            q = parse_qs(u.query)
            try:
                limit = max(1, min(int(q.get("limit", ["50"])[0]), 200))
            except ValueError:
                limit = 50
            sort = q.get("sort", ["cpu"])[0]
            return _send(self, _cached_processes(limit=limit, sort=sort))
        if u.path == "/api/backends":
            return _send(self, {
                "simulated": False,
                "onnx": _classifier.status(),
                "qnn": _qnn,
                "selected": _backend,
            })
        if u.path == "/api/ai_status":
            from ai import recommend as _rec
            from ai.dataset import FEATURES as _FEATS
            st = _classifier.status()
            return _send(self, {
                "simulated": False,
                "model_loaded": bool(st.get("model_loaded")),
                "model_name": "process_priority_classifier",
                "model_format": "ONNX",                "model_size_kb": st.get("model_size_kb"),
                "onnx_inference": "AVAILABLE" if st.get("model_loaded") else "UNAVAILABLE",
                "qnn": "AVAILABLE" if _qnn.get("available") else "UNAVAILABLE",
                "npu": "AVAILABLE" if _backend["selected_backend"] == "HEXAGON NPU" else "UNAVAILABLE",
                "selected_backend": _backend["selected_backend"],
                "provider": _backend["provider"],
                "target_backend": "Qualcomm Hexagon NPU",
                "classes": st.get("classes"),
                "features": _FEATS,
                "confidence_threshold": _rec.THRESHOLD,
                "temperature": _ood_ref().get("temperature"),
                "ood_threshold": _ood_ref().get("ood_threshold"),
                "safety_states": ["PROTECT", "OBSERVE", "REVIEW",
                                  "OPTIMIZATION CANDIDATE"],
                "ort_version": _ort_version(),
                "philosophy": ("final = calibrated_model x familiarity; "
                               "uncertainty -> protect; model advises, "
                               "safety layer decides"),
                "last_latency_ms": st.get("last_latency_ms"),
                "ai_source": _ai_source,
            })
        if u.path == "/api/demo":
            q = parse_qs(u.query)
            name = q.get("set", ["presentation"])[0]
            if _ai_source != "onnx-model":
                return _send(self, {"demo": True, "error":
                                     "ONNX model unavailable; demo needs the real model."})
            return _send(self, ai_demo.run_demo(name, _classifier))
        if u.path == "/api/decisions":
            q = parse_qs(u.query)
            try:
                limit = max(1, min(int(q.get("limit", ["50"])[0]), 500))
            except ValueError:
                limit = 50
            return _send(self, {
                "simulated": False,
                "source": "logs/ai_decisions.jsonl",
                "note": "AI decisions/recommendations only — no process was modified.",
                "records": ai_log.tail(limit),
            })
        if u.path == "/api/emergency":
            global EMERGENCY_STOP
            q = parse_qs(u.query)
            state = q.get("state", [""])[0].lower()
            if state in ("on", "off"):
                EMERGENCY_STOP = (state == "on")
            return _send(self, {
                "simulated": False,
                "emergency_stop": EMERGENCY_STOP,
                "monitoring": "ACTIVE",
                "simulation_flow": "DISABLED" if EMERGENCY_STOP else "ENABLED",
                "note": "Prototype control: stops simulation/recommendations only. "
                        "Monitoring continues. Windows is untouched either way.",
            })
        if u.path == "/api/npu_validation":
            # Truthful validation status for the dashboard card. Prefers real
            # Hub evidence (hub_flow.json) when present; otherwise the local
            # harness summary; otherwise NOT VALIDATED.
            import json as _j2
            hub = {"status": "NOT_VALIDATED — ACCESS REQUIRED"}
            local = "UNKNOWN"
            try:
                flow = _j2.loads((BASE / "artifacts" / "npu_validation"
                                  / "hub_flow.json").read_text())
                if flow.get("status") in ("NPU_VERIFIED", "PROFILED_NON_NPU"):
                    hub = flow
            except (OSError, ValueError):
                pass
            try:
                summ = _j2.loads((BASE / "artifacts" / "npu_validation"
                                  / "validation_summary.json").read_text())
                local = summ.get("local", {}).get("status", "UNKNOWN")
            except (OSError, ValueError):
                pass
            verified = isinstance(hub, dict) and hub.get("status") == "NPU_VERIFIED"
            inferred = isinstance(hub, dict) and bool((hub.get("stages") or {}).get("inference"))
            return _send(self, {
                "simulated": False,
                # Four separate levels — never collapsed into one label.
                "local_dell_cpu": "VERIFIED" if local == "LOCAL_CPU_VERIFIED" else local,
                "snapdragon_model_npu": ("VERIFIED" if verified else
                                         "NOT VALIDATED — ACCESS REQUIRED"),
                "full_application_on_snapdragon": "NOT VERIFIED",
                "hp_full_application": "REQUIRES PHYSICAL HP SNAPDRAGON PC",
                "local_cpu": "VERIFIED" if local == "LOCAL_CPU_VERIFIED" else local,
                "snapdragon_npu": ("VERIFIED VIA QUALCOMM HOSTED DEVICE"
                                   if verified
                                   else "NOT VALIDATED — ACCESS REQUIRED"),
                "inference": ("VERIFIED" if inferred else "PENDING"),
                "hub_detail": hub,
                "note": "A hosted Snapdragon X Elite CRD validates NPU execution, "
                        "not HP-branded hardware. No result beyond the evidence.",
            })
        if u.path in ("/api/optimization/preview", "/api/optimization/simulate"):
            if EMERGENCY_STOP:
                return _send(self, {
                    "simulated": True, "disabled": True,
                    "simulated_action": "NO_ACTION",
                    "note": "STOP AI OPTIMIZATION is ON: simulation flow disabled. "
                            "Monitoring continues; nothing was modified.",
                })
            # GET-only by design (§17): pure computation over DEMO rows.
            # No endpoint here can touch a real process; simulator.py has
            # no process-control code path at all.
            q = parse_qs(u.query)
            name = q.get("set", ["presentation"])[0]
            try:
                index = max(0, int(q.get("index", ["0"])[0]))
            except ValueError:
                index = 0
            if _ai_source != "onnx-model":
                return _send(self, {"simulated": True, "error":
                                     "ONNX model unavailable."})
            demo = ai_demo.run_demo(name, _classifier)
            rows = demo.get("rows", [])
            if not rows:
                return _send(self, {"simulated": True, "error": "empty demo set"})
            row = rows[min(index, len(rows) - 1)]
            if u.path.endswith("/simulate"):
                sim = opt_sim.sequence(row)
                rec = ai_log.record(row, _backend["selected_backend"])
                rec.update({"simulation": True,
                            "simulated_action": sim["simulated_action"],
                            "projected_effect": sim["projected_effect"]})
                ai_log.log_record(rec)
                sim["logged"] = True
                return _send(self, sim)
            return _send(self, opt_sim.preview(row))
        if u.path == "/api/safety":
            return _send(self, safety_engine.status())
        if u.path == "/api/plan":
            return _send(self, planner.build_plan(
                system_stats.snapshot(),
                _cached_processes(limit=25, sort="cpu")))
        return super().do_GET()


def run(port: int = config.PORT) -> ThreadingHTTPServer:
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", config.PORT), Handler)
    print(f"{config.APP_NAME} {config.VERSION} — observe+classify only, no process modification",
          flush=True)
    print(f"Dashboard: http://127.0.0.1:{config.PORT}/", flush=True)
    print(f"Arch: {_platform['arch_normalized']} | CPU: {_platform['cpu_name']}", flush=True)
    print(f"AI: {_ai_source} | backend: {_backend['selected_backend']}", flush=True)
    srv.serve_forever()
