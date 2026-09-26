# FINAL VERIFICATION — Phase 1 → 2.5 (independent run)
Snapdragon AI Smart Process & Task Manager (competition prototype)

# Executive Summary

Independently verified from the current repository on 2026-09-26, starting
from `pip install`, compile, fresh test runs, a self-started server, live
API calls, live model inference, and source audits. **40/40 tests pass
(10 + 10 + 20), deterministic across re-runs.** One live-data finding
(model-vote skew to 96% DEFERRABLE on an idle machine) was investigated and
determined to be population skew, not model collapse — the balanced-probe
check passes and every affected process still lands in PROTECT/REVIEW.
**No process-modification path exists. No Phase 3 work begun.**

# Environment

- Windows 11 Home 10.0.26200, Intel i5-1334U (x64), 16 GB RAM, Intel UHD, battery present
- Python 3.14.7; psutil 7.2.2, numpy 2.5.3, onnxruntime 1.30.0, onnx 1.23.0 (all from requirements.txt, installed clean)
- Server: self-started `python app.py`, pid 13156, 127.0.0.1:8099, `onnx-model`, CPU FALLBACK
- `python -m compileall`: NO SYNTAX ERRORS. `import app`: OK.

# Phase 1 Results

Telemetry, processes (260+, unique PIDs, sane ranges), platform
(x86_64 / is_arm=false / is_snapdragon=false with correct routing strings),
arch labels from the constrained set incl. honest Unknown, live foreground
pid → PROTECT, 94 allowlisted incl. pid 0/4 → PROTECT, plan dry-run
(`executed: []`). Malformed query params degrade gracefully.

# Phase 2 Results

ONNX 1.9 KB, graph 11-in / {probabilities, label}-out, metadata v0.2.5
consistent (features, classes, layers [11,16,8,4], T=2.0, centroids 4×11,
d_ref 2.58). Deterministic retrain: 93.22% train / 87.38% test (3200/800,
seed 42) — SYNTHETIC ONLY. Feature order/scaler identical train↔inference.
Live probs valid (sum≈1). Demo sets isolated, marked, real predictions.

# Phase 2.5 Results

`final = calibrated × familiarity` verified arithmetically on live rows and
3 synthetic cases. Temperature proven: ORT output ≡ manual softmax(T=2.0),
≠ T=1 (0.5154 vs 0.5411 on a soft vector). OOD: wild vector → UNKNOWN/PROTECT,
tame → familiar. Override order (allowlist → foreground → OOD → floors →
states) holds against 0.9999 adversarial votes. Live: 196 PROTECT / 4 REVIEW,
0 candidates, avg final 0.41.

# End-to-End Results

20/20 integration checks, twice, exit 0. API latencies: platform 332ms,
stats 172ms, processes 106ms, ai_status 305ms, backends 119ms, safety 82ms,
plan 169ms, demo 84ms, dashboard 557ms (warming values; steady-state <160ms
observed previously). Dependency chain app→telemetry→features→ORT→OOD→
safety→API→dashboard traced live per process (§16 chains recorded).

# AI Validation

Live chains (chrome/explorer/python/svchost): raw vectors plausible,
model genuinely uncertain on quiet procs (0.50–0.52 splits), svchost raw
0.9869 DEFERRABLE still forced PROTECTED by allowlist + low final.
No collapse on balanced probe (<0.90). Live skew to DEFERRABLE documented
as population effect with warning (not failure).

# OOD Validation

Familiarity range live 0.38–1.00; ood_count 1 observed live; extreme vector
fam 0.0 → final 0.0 → PROTECT. Standardization shared between train and
inference (asserted in tests).

# Safety Validation

Protected/foreground/low-conf/OOD → PROTECT(/REVIEW in band); familiar
archetypes earn OBSERVE/candidates only in demo sets; model_class vs
ai_class vs safety_state vs recommendation separate on every row;
`guard()` raises; allowlist enforced before thresholds.

# Security Audit

Localhost bind, GET-only (no POST/PUT handlers), no upload/cloud/socket
code, no registry/service/startup/firmware writes, no remote-control or
process-control endpoints. Static audit for call-shaped destructive APIs:
zero hits outside expected literals.

# Dashboard Validation

`/` + `/app.js` serve 200. HTML contains AI Engine / Workload Analysis /
AI Process Table / DEMO DATA banner. Every JS-referenced element ID exists.
Backend rendered from API (`selected_backend` = CPU FALLBACK); "Target:
Snapdragon Hexagon NPU" shown as target only; no NPU-ACTIVE claim anywhere.
Refresh 5s/15s. Limitation: verified over HTTP + statically; no
browser-automation tool exists in this environment, so a live rendered
screenshot was not captured.

# Performance Measurements

- ONNX: ~0.04ms/row, 0.67ms/batch-8, ~0.2–1ms per 200-proc batch (ORT <1% of pipeline)
- Sampler breakdown (264 procs): bare psutil enumeration 2.98s (bulk — Windows API iteration, NOT SID lookups as previously assumed; username adds ~0s), cpu_percent+rows ~1.3s, AI enrich 1.16s (~200 OpenProcess/io_counters syscalls), context ~0s
- Sampler runs 2 passes + 4s sleep ≈ 70% of one core ≈ 6–8% machine CPU; server ~69 MB RSS
- Overhead verdict: enumeration-dominated, expected given full-process polling design, but high for a load-reducing tool — sampling strategy is the top efficiency item for later phases. AI inference itself is negligible.

# Snapdragon/NPU Status

QNN UNAVAILABLE, NPU UNAVAILABLE, ORT providers [AzureExecutionProvider,
CPUExecutionProvider], selected CPU FALLBACK — correct on Intel.
`backend.select()` + `qnn_backend.probe()` + `ProcessClassifier` ABC form a
clean CPU/QNN abstraction; app layers consume `selected_backend`, never a
hard-coded provider. ARM64/emulated/unknown arch path and `is_emulated`
feature exist but are hardware-unvalidated.

# Bugs Found

1. Integration collapse test tripped on live skew (96% DEFERRABLE votes) —
   investigated: population skew on idle machine, model spread confirmed on
   balanced probe; test corrected to probe-spread (fail) + live-skew (warn).
2. Harness bugs (ordering dependency, lazy-load compare, self-matching
   security patterns, vacuous arch assertion) — fixed in tests only.
3. Trivial: unused `_FEATS` import (fixed), stale "12-feature" docstring (fixed),
   6 stale README lines (fixed: deps, endpoints, 11-arch, confidence language).

# Fixes Made

Test-harness corrections + docstring/import/README accuracy fixes only. No
product behavior changed except the collapse test's fail/warn semantics
(documented above). One README sentence added stating Snapdragon-HP intent
(documentation of existing architecture, not a feature).

# Known Limitations

1. Synthetic-trained model; live is OOD by construction → mostly PROTECT/REVIEW (intended conservatism, but live candidates essentially never occur; demos show them).
2. Sampler costs ~6–8% machine CPU (enumeration-dominated) — acceptable for prototype, must be addressed before any efficiency claim.
3. No persistent AI decision log (stdout diagnostics only).
4. Dashboard not screenshot-verified in a real browser (no automation tool available).
5. ARM/emulation/QNN paths hardware-unvalidated; real-world precision/recall unmeasured (no labelled real dataset, by design).

# Competition Claim Audit

- "Designed/intended for Snapdragon HP PCs": now stated in README AND reflected in architecture (QNN selection, Hexagon target labels, ARM/emulation awareness, ONNX model) — VERIFIED as intent + architecture, hardware validation pending.
- NPU/QNN: correctly reported unavailable; never claimed active — VERIFIED honest.
- Accuracy 87–93%: labelled synthetic-only wherever stated — VERIFIED honest.
- No battery/CPU-saving claims exist in README — nothing to correct.
- "Real" vs "simulated": telemetry/predictions real; training rows + demo processes marked — VERIFIED.

# Final Status

| Component | Status |
|---|---|
| System telemetry | VERIFIED |
| Process enumeration | VERIFIED |
| Platform detection | VERIFIED |
| ARM/x86/x64 awareness | VERIFIED WITH LIMITATION (x64 host; ARM paths need hardware) |
| AI model + ONNX inference | VERIFIED WITH LIMITATION (synthetic training) |
| Calibration + OOD + safety | VERIFIED |
| API + dashboard | VERIFIED WITH LIMITATION (no browser screenshot) |
| Demo mode | VERIFIED |
| Process modification | BLOCKED (intended — no path exists) |
| Decision logging | SIMULATED (absent) |
| QNN / Hexagon NPU | REQUIRES SNAPDRAGON HARDWARE (abstraction ready) |

No FAILED components. Phase 3 not begun.
