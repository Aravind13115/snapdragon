# TEST REPORT — Phase 1 → 2.5 Full Integration
Snapdragon AI Smart Process & Task Manager (competition prototype)

- Date (UTC): 2026-09-25
- Host: Windows 11 (10.0.26200), Intel i5-1334U x64, 16 GB RAM — dev machine, NOT Snapdragon
- Prototype version: 0.2.5-phase2.5
- Backend under test: CPU FALLBACK (correct on this host)
- Total tests executed: **40** (10 phase2 + 10 phase2.5 + 20 integration), all stdlib unittest, live server, no mocks

## Executive Summary

**PASS with limitations. Ready for Phase 3 planning, not for optimization actions.**
Telemetry → features → ONNX → calibration → OOD → safety → API → dashboard
verified end-to-end against the live server. No process-modification path
exists (static audit + `guard()` + dry-run `executed: []`). The AI is
demonstrably conservative on live data (154/200 PROTECT, 46/200 REVIEW,
0 unwarranted candidates). All Snapdragon-dependent claims are correctly
gated behind hardware detection. Gaps: no persistent decision log, sampler
CPU footprint is noticeable, dashboard verified statically + over HTTP
(no browser-automation tool in this environment).

## Phase 1 — System Observation: PASS

- `/api/platform`: x86_64, is_arm=false, is_snapdragon=false, routing strings correct
- `/api/stats`: CPU 0–100, 12 per-core values, RAM 16.85 GB, disk C:, net up/down, battery % + plugged state, uptime — all sane ranges
- `/api/processes`: 260+ rows, unique PIDs ≥ 0, non-empty names, cpu 0–100, malformed `limit`/`sort` degrade gracefully
- Arch labels ∈ {x64, ARM64 Native, x86 (WOW64), x86/x64 (Emulated), Unknown}; Unknown used, never guessed; x86/x64 never blamed as a reason
- Foreground pid detected live (OpenCode.exe) → PROTECT
- 94 allowlisted processes incl. pid 0/4 → all PROTECT; 85 show model-vote ≠ final-decision separation
- `/api/plan`: `executed: []` always

## Phase 2 — AI Classification: PASS

- Model file: `models/process_classifier.onnx` (1.9 KB), graph input [batch,11], outputs {probabilities, label}; metadata v0.2.5 matches graph, classes ordered [PROTECTED, USER_IMPORTANT, FLEXIBLE, DEFERRABLE]
- Training (reproduced twice, deterministic): MLP 11→16→8→4, Adam, seed 42/7, 3200 train / 800 test, **train 93.22% / test 87.38% — SYNTHETIC ONLY, not real-world accuracy**
- Feature order identical across dataset.py / features.py / metadata / ONNX graph; scaler identical train↔inference (asserted); booleans 0/1; arch encoding native=1/WOW64=0.5/unknown=0
- Live batch inference valid: probs ∈ [0,1], rows sum ≈ 1
- Live model votes PROTECTED 67 / DEFERRABLE 131 — no collapse (<95% rule)
- Demo mode: marked, isolated from live rows, real model predictions

## Phase 2.5 — Calibration & Safety: PASS

- Temperature T=2.0 baked into ONNX (NLL-fit); verified `final = raw × familiarity` arithmetically on live rows
- OOD: centroid RBF familiarity, live range 0.38–1.00; synthetic extreme vector → OOD → UNKNOWN/PROTECT; tame vector → familiar
- Rule order enforced: allowlist → foreground → OOD → final<0.50 → REVIEW band → PROTECT/OBSERVE/CANDIDATE; 0.9999 votes cannot bypass any rule (tested ×4 vectors)
- Live safety states: PROTECT 154 / REVIEW 46 / OBSERVE 0 / CANDIDATE 0 — conservative as designed
- `python ai/analyze.py` diagnostic CLI works (model + live eval + feature validation)

## Integration: PASS

- All 8 endpoints HTTP 200, valid JSON: platform 49ms, stats 92ms, processes 48ms, plan 106ms, ai_status 158ms, backends 63ms, safety 48ms, demo 99ms
- Dashboard static check: every JS-referenced element ID exists in HTML; no "NPU ACTIVE" claim anywhere; refresh 5s/15s; all consumed API fields present in backend responses; `/` and `/app.js` serve 200
- Dead-code audit: 1 unused import + 1 stale docstring found and fixed; trivial unused constants (`SUPPORTED_ARCHES`, `REFRESH_MS`, `_SAFE_ATTRS`) left as documented anchors
- Retrain reproducibility: identical metrics across runs

## Safety: PASS (BLOCKED = intended)

- Repo-wide static audit for call-shaped destructive APIs (terminate/kill/os.kill/taskkill/Stop-Process/TerminateProcess/SuspendThread/set_priority/nice/subprocess): **zero hits** outside the safety blocklist literal, comments and docs
- `safety.engine.guard()` raises on all mutating actions (tested); localhost-only bind; GET-only API (no POST/PUT); no upload/cloud/remote-control code; no registry/service/startup/firmware writes

## Performance (measured, CPU backend — no NPU claims)

- Single-row ONNX: ~0.04ms; batch-8: 0.67ms; 200-process batch: ~0.17–1ms
- Background sampler: ~5s per full enumeration (Windows SID lookups), served from cache → API stays <160ms
- Footprint: server ~69 MB RSS, ~8% machine CPU during sampler bursts (spikes to ~1 core on 12-logical machine)

## AI metrics

- 1.9 KB MLP, 11→16→8→4, T=2.0, OOD thr 0.35, action thr 0.85, REVIEW floor 0.50
- Synthetic: 93.22% train / 87.38% test (800 held-out). Real-world precision/recall: unmeasured by design (no labelled real dataset)

## NPU

- QNN: UNAVAILABLE · NPU: UNAVAILABLE · ORT providers: [Azure, CPU] · Selected: CPU FALLBACK — expected and correct on Intel
- `inference/backend.py::select()` auto-selects HEXAGON NPU when probe available + QNNExecutionProvider present (code-reviewed, hardware-gated; untested — no hardware)

## Known limitations (honest)

1. Synthetic-trained model; live is OOD by construction → most live decisions are PROTECT/REVIEW (intended, but means candidates rarely appear on live data; demos show them)
2. Per-process disk/net best-effort (AccessDenied → safe defaults + notes)
3. Sampler CPU footprint (~8% bursts) is high for a tool meant to reduce load — sampling strategy is a Phase-3 concern
4. No persistent AI decision log (stdout diagnostics only) — needed before any action phase
5. Dashboard checked statically + over HTTP; no browser-automation run in this environment
6. ARM/emulation/QNN paths are architecture-complete but hardware-unvalidated

## Status table

| Component | Status |
|---|---|
| System telemetry | VERIFIED |
| Process enumeration | VERIFIED |
| Platform detection | VERIFIED |
| ARM awareness | VERIFIED WITH LIMITATION (x64 host; ARM paths code-complete, need hardware) |
| AI model | VERIFIED WITH LIMITATION (synthetic data only) |
| ONNX inference | VERIFIED |
| Confidence calibration | VERIFIED |
| OOD detection | VERIFIED |
| Safety engine | VERIFIED |
| API | VERIFIED |
| Dashboard | VERIFIED WITH LIMITATION (static + HTTP; no browser run) |
| Demo mode | VERIFIED |
| Process modification | BLOCKED (intended) |
| Decision logging | SIMULATED (absent; stdout only) |
| QNN integration | REQUIRES SNAPDRAGON HARDWARE (ready) |
| Hexagon NPU validation | REQUIRES SNAPDRAGON HARDWARE |

## Release readiness

Prototype is **observation/classification-complete and safe to demo**. No component FAILED. Nothing here authorizes process control — Phase 3 (QNN validation on Snapdragon HP PC) and any action phase both require the decision log + sampler-efficiency work noted above.
